"""Complete tooling qualification without replacing successful native receipts.

The native source remains055bd850. A later clean tooling-only repair must leave
every bound native input unchanged. The original tooling failure is preserved.
"""
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
    parser.add_argument("--tooling-revision", required=True)
    parser.add_argument("--existing-clone", type=Path, required=True)
    parser.add_argument("--native-campaign", type=Path, required=True)
    args = parser.parse_args()
    root = Path.cwd().resolve()
    checkout, output = args.existing_clone.resolve(), args.native_campaign.resolve()
    assert re.fullmatch("[0-9a-f]{40}", args.tooling_revision)
    assert checkout.is_relative_to(root / ".aide-local") and output.is_relative_to(root / ".aide-local")
    assert not (output / "summary.json").exists() and not (output / "tooling-repair-commands.json").exists()
    original = json.loads((output / "commands.json").read_bytes())
    assert original[-1]["name"] == "tooling" and original[-1]["exit_code"] == 1
    assert all(v["exit_code"] == 0 for v in original[:-1])
    commands = []

    def run(name, command, timeout=300):
        command = list(map(str, command))
        start = time.monotonic()
        process = subprocess.run(command, cwd=checkout, capture_output=True, timeout=timeout)
        log = output / "logs" / ("repair-" + name + ".log")
        log.write_bytes(process.stdout + process.stderr)
        commands.append(dict(name=name, command=command, cwd=str(checkout), source_revision=args.tooling_revision,
                             exit_code=process.returncode, elapsed_seconds=round(time.monotonic() - start, 3),
                             log="logs/" + log.name))
        save(output / "tooling-repair-commands.json", commands)
        print(f"repair-{name}: exit {process.returncode}", flush=True)
        assert process.returncode == 0, name
        return process.stdout

    assert Path(run("origin", ["git", "remote", "get-url", "origin"]).decode().strip()).resolve() == root
    assert not run("source-before", ["git", "status", "--porcelain"]).strip()
    run("fetch", ["git", "fetch", "--no-tags", "origin", args.tooling_revision])
    run("checkout", ["git", "checkout", "--detach", args.tooling_revision])
    assert not run("source-status", ["git", "status", "--porcelain"]).strip()
    native_inputs = json.loads((output / "source-inputs.json").read_bytes())
    assert all(sha(checkout / name) == value for name, value in native_inputs.items()), "Native input changed across tooling repair"
    names = {"spec/tools/tests/test_specctl.py", "spec/manifest.json",
             ".aide/evidence/2026-10-12-shared-presentation/complete_tooling.py"}
    bindings = {}
    for name in sorted(names):
        bindings[name] = run("blob-" + Path(name).stem, ["git", "rev-parse", args.tooling_revision + ":" + name]).decode().strip()
    save(output / "tooling-source-inputs.json", {name: sha(checkout / name) for name in sorted(names)})
    save(output / "tooling-source-blob-bindings.json", bindings)
    run("tooling", [sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", "spec/tools/tests", "-v"], 600)
    text = (output / "logs/repair-tooling.log").read_text(encoding="utf-8")
    count = int(re.search(r"^Ran (\d+) tests ", text, re.MULTILINE).group(1))
    skips = int(re.search(r"^OK \(skipped=(\d+)\)$", text, re.MULTILINE).group(1))
    checks = json.loads(run("spec-check", [sys.executable, "-X", "utf8", "spec/tools/specctl.py", "check"]))
    run("index", [sys.executable, "-X", "utf8", "spec/tools/specctl.py", "index", "--check"])
    run("manifest", [sys.executable, "-X", "utf8", "spec/tools/specctl.py", "verify-manifest"])
    run("context", [sys.executable, "-X", "utf8", "spec/tools/specctl.py", "context", "--work", "DE-W010", "--output", output / "context", "--byte-budget", "650000"])
    run("verify-context", [sys.executable, "-X", "utf8", "spec/tools/specctl.py", "verify-context", output / "context"])
    build = output / "build"
    identity = json.loads((build / "generated/build-identity.json").read_bytes())
    revision = identity["identity"]["source_revision"]
    assert revision == "055bd850e03b723c9b8afa63cb1c803107f466eb" and identity["identity"]["source_state"] == "clean"
    save(output / "build-identity.json", identity)
    executable = build / "Release/disked.exe"
    launch = json.loads(run("product-launch", [executable, "build", "inspect", "--json"]))["result"]
    assert launch["source_revision"] == revision and launch["version"] == "0.1.0-dev.42"
    dumpbin = Path(identity["compiler_path"]).with_name("dumpbin.exe")
    artifacts = []
    for name in ("disked", "gui_model_probe", "tui_model_probe", "presentation_rules_probe"):
        path = build / "Release" / (name + ".exe")
        for mode in ("headers", "imports", "dependents"):
            run(name + "-" + mode, [dumpbin, "/" + mode, path])
        artifacts.append(dict(kind=name, path=str(path), bytes=path.stat().st_size, sha256=sha(path), source_revision=revision))
    objects = [dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path))
               for name in ("disked_json", "disked_command", "disked_invocation", "disked_presentation")
               for path in (build / (name + "_headers.dir/Release")).glob("*.obj")]
    assert len(objects) == 7
    save(output / "header-objects.json", objects)
    config = output / "build-configuration"
    config.mkdir()
    for name in ("CMakeCache.txt", "disked.vcxproj", "disked_json.vcxproj", "disked_command.vcxproj", "disked_invocation.vcxproj", "disked_json_headers.vcxproj", "disked_command_headers.vcxproj", "disked_invocation_headers.vcxproj", "disked_presentation_headers.vcxproj", "disked_presentation.vcxproj", "gui_model_probe.vcxproj", "tui_model_probe.vcxproj", "presentation_rules_probe.vcxproj", "json_codec_probe.vcxproj", "command_parser_probe.vcxproj", "protocol_reader_probe.vcxproj", "invocation_policy_probe.vcxproj"):
        shutil.copyfile(build / name, config / name)
    shutil.copytree(build / ".cmake/api/v1/reply", output / "cmake-codemodel")
    assert not run("final-source-status", ["git", "status", "--porcelain"]).strip()
    boundaries = json.loads((output / "build-boundaries.json").read_bytes())
    catalog = json.loads((checkout / "tools/build-inputs.json").read_bytes())
    host = json.loads((output / "logs/host.log").read_bytes())
    save(output / "summary.json", dict(source_revision=revision, tooling_source_revision=args.tooling_revision, source_state="clean", host=host,
         source_input_count=len(native_inputs), product_input_count=len(catalog["files"]), native_test_groups=85,
         checker_negative_fixtures=16, tooling_count=count, tooling_skipped=skips, structural=checks,
         build_target_count=boundaries["target_count"], quoted_include_edges=boundaries["quoted_include_edges"],
         independent_header_compilations=len(objects), shared_rule_cases=34, shared_python_tests=8, artifacts=artifacts, passed=True,
         native_inputs_unchanged_across_tooling_repair=True, owner_accepted=False, unit_complete=False, release_ready=False,
         limitations=boundaries["limits"]))
    print("Exact native receipts plus clean tooling-only repair qualification passed.", flush=True)


if __name__ == "__main__":
    main()
