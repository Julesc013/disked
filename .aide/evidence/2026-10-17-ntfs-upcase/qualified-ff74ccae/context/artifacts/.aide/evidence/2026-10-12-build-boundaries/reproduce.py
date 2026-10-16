"""Reproduce the private core build-boundary checkpoint at an exact clean revision."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-revision", required=True)
    parser.add_argument("--existing-clone", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    checkout, output = args.existing_clone.resolve(), args.output.resolve()
    local = root / ".aide-local"
    assert re.fullmatch("[0-9a-f]{40}", args.source_revision)
    assert checkout.is_relative_to(local) and output.is_relative_to(local)
    output.mkdir()
    logs = output / "logs"
    logs.mkdir()
    commands = []

    def run(name, command, timeout=300):
        command = list(map(str, command))
        start = time.monotonic()
        process = subprocess.run(command, cwd=checkout, capture_output=True, timeout=timeout)
        log = logs / (name + ".log")
        log.write_bytes(process.stdout + process.stderr)
        commands.append({"name": name, "command": command, "cwd": str(checkout),
                         "exit_code": process.returncode, "elapsed_seconds": round(time.monotonic() - start, 3),
                         "log": "logs/" + log.name})
        save(output / "commands.json", commands)
        print(f"{name}: exit {process.returncode}", flush=True)
        assert process.returncode == 0, name
        return process.stdout

    assert Path(run("origin", ["git", "remote", "get-url", "origin"]).decode().strip()).resolve() == root
    assert not run("existing-status", ["git", "status", "--porcelain"]).strip()
    run("fetch", ["git", "fetch", "--no-tags", "origin", args.source_revision])
    run("checkout", ["git", "checkout", "--detach", args.source_revision])
    assert not run("source-status", ["git", "status", "--porcelain"]).strip()
    host = json.loads(run("host", ["powershell", "-NoProfile", "-Command",
        "$diskedIdentity=[System.Security.Principal.WindowsIdentity]::GetCurrent();"
        "$diskedPrincipal=[System.Security.Principal.WindowsPrincipal]::new($diskedIdentity);"
        "$diskedOS=Get-CimInstance Win32_OperatingSystem;"
        "[ordered]@{identity=$diskedIdentity.Name;elevated=$diskedPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);"
        "os=$diskedOS.Caption;version=$diskedOS.Version;architecture=$diskedOS.OSArchitecture}|ConvertTo-Json -Compress"]))
    assert host["identity"] == "BLACKGLASS-WIN1\\Jules" and not host["elevated"]
    run("source-map", [sys.executable, "tools/check-source-map.py"])
    catalog = json.loads((checkout / "tools/build-inputs.json").read_bytes())
    names = set(catalog["files"]) | {
        "AGENTS.md", "docs/code-structure.md", "docs/source-map.md", ".clang-format", ".editorconfig",
        "spec/work/units.json", "spec/catalog/input-dependencies.json", "spec/tools/specctl.py",
        "tools/check-source-map.py", ".aide/evidence/2026-10-12-build-boundaries/reproduce.py",
    }
    inputs = {name: sha(checkout / name) for name in sorted(names)}
    save(output / "source-inputs.json", inputs)
    tree = run("source-tree", ["git", "ls-tree", "-r", "-z", args.source_revision])
    blobs = {}
    for row in tree.split(b"\0"):
        if row:
            header, path = row.split(b"\t", 1)
            name = path.decode()
            if name in inputs:
                blobs[name] = header.split()[2].decode()
    assert set(blobs) == set(inputs)
    for name, blob in blobs.items():
        data = (checkout / name).read_bytes()
        assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == blob
    save(output / "source-blob-bindings.json", blobs)
    run("cmake-version", ["cmake", "--version"])
    run("python-environment", [sys.executable, "-c", "import sys,importlib.metadata as m;print(sys.version);print('PyYAML='+m.version('PyYAML'));print('jsonschema='+m.version('jsonschema'))"])
    build = output / "build"
    run("configure", ["cmake", "--preset", "windows-bootstrap", "-B", build, "-DPython3_EXECUTABLE=" + sys.executable])
    run("build", ["cmake", "--build", build, "--config", "Release", "--parallel", "4"], 1200)
    identity = json.loads((build / "generated/build-identity.json").read_bytes())
    assert identity["identity"]["source_revision"] == args.source_revision and identity["identity"]["source_state"] == "clean"
    assert identity["inputs"] == {name: inputs[name] for name in catalog["files"]}
    save(output / "build-identity.json", identity)
    run("boundaries", [sys.executable, "tools/check-build-boundaries.py", "--build", build, "--output", output / "build-boundaries.json"])
    boundaries = json.loads((output / "build-boundaries.json").read_bytes())
    assert boundaries["status"] == "PASS" and not boundaries["violations"]
    tests = json.loads(run("test-catalog", ["ctest", "--test-dir", build, "-C", "Release", "--show-only=json-v1"]))
    assert len(tests["tests"]) == 84
    run("native-tests", ["ctest", "--test-dir", build, "-C", "Release", "--parallel", "4", "--output-on-failure"], 2400)
    shutil.copyfile(build / "Testing/Temporary/LastTest.log", output / "native-details.log")
    run("checker-negative-fixtures", [sys.executable, "-m", "unittest", "discover", "-s", "tests/tools", "-v"])
    run("tooling", [sys.executable, "-m", "unittest", "discover", "-s", "spec/tools/tests", "-v"], 600)
    tooling = (logs / "tooling.log").read_text(encoding="utf-8")
    tooling_count = int(re.search(r"^Ran (\d+) tests ", tooling, re.MULTILINE).group(1))
    tooling_skips = int(re.search(r"^OK \(skipped=(\d+)\)$", tooling, re.MULTILINE).group(1))
    checks = json.loads(run("spec-check", [sys.executable, "spec/tools/specctl.py", "check"]))
    run("index", [sys.executable, "spec/tools/specctl.py", "index", "--check"])
    run("manifest", [sys.executable, "spec/tools/specctl.py", "verify-manifest"])
    run("context", [sys.executable, "spec/tools/specctl.py", "context", "--work", "DE-W010", "--output", output / "context", "--byte-budget", "650000"])
    run("verify-context", [sys.executable, "spec/tools/specctl.py", "verify-context", output / "context"])
    executable = build / "Release/disked.exe"
    launch = json.loads(run("product-launch", [executable, "build", "inspect", "--json"]))["result"]
    assert launch["source_revision"] == args.source_revision and launch["version"] == "0.1.0-dev.42"
    dumpbin = Path(identity["compiler_path"]).with_name("dumpbin.exe")
    artifacts = []
    for name in ("disked", "json_codec_probe", "command_parser_probe", "protocol_reader_probe", "invocation_policy_probe"):
        path = build / "Release" / (name + ".exe")
        for mode in ("headers", "imports", "dependents"):
            run(name + "-" + mode, [dumpbin, "/" + mode, path])
        artifacts.append({"kind": name, "path": str(path), "bytes": path.stat().st_size, "sha256": sha(path), "source_revision": args.source_revision})
    header_objects = []
    for name in ("disked_json", "disked_command", "disked_invocation"):
        for path in (build / (name + "_headers.dir/Release")).glob("*.obj"):
            header_objects.append({"path": str(path), "sha256": sha(path), "bytes": path.stat().st_size})
    assert len(header_objects) == 5
    save(output / "header-objects.json", header_objects)
    config = output / "build-configuration"
    config.mkdir()
    for name in ("CMakeCache.txt", "disked.vcxproj", "disked_json.vcxproj", "disked_command.vcxproj", "disked_invocation.vcxproj", "disked_json_headers.vcxproj", "disked_command_headers.vcxproj", "disked_invocation_headers.vcxproj", "json_codec_probe.vcxproj", "command_parser_probe.vcxproj", "protocol_reader_probe.vcxproj", "invocation_policy_probe.vcxproj"):
        shutil.copyfile(build / name, config / name)
    shutil.copytree(build / ".cmake/api/v1/reply", output / "cmake-codemodel")
    assert not run("final-source-status", ["git", "status", "--porcelain"]).strip()
    save(output / "summary.json", {
        "source_revision": args.source_revision, "source_state": "clean", "host": host,
        "source_input_count": len(inputs), "product_input_count": len(catalog["files"]),
        "native_test_groups": len(tests["tests"]), "checker_negative_fixtures": 16,
        "tooling_count": tooling_count, "tooling_skipped": tooling_skips, "structural": checks,
        "build_target_count": boundaries["target_count"], "quoted_include_edges": boundaries["quoted_include_edges"],
        "independent_core_header_compilations": len(header_objects), "artifacts": artifacts,
        "passed": True, "owner_accepted": False, "unit_complete": False, "release_ready": False,
        "limitations": boundaries["limits"],
    })
    print("Exact-source native build-boundary checkpoint passed.", flush=True)


if __name__ == "__main__":
    main()
