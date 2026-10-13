"""Exact clean-source full native DE-W056 campaign; retains real terminal results."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time

ROOT = Path.cwd().resolve()
REV = "243f748e6a6af62469b184614d4d623b8ad239ea"
CLONE = ROOT / ".aide-local/fat-recursive-clean-243f748e"
OUT = ROOT / ".aide-local/fat-recursive-qualification-243f748e"


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


assert CLONE.is_relative_to(ROOT / ".aide-local") and OUT.is_relative_to(ROOT / ".aide-local")
assert not CLONE.exists() and not OUT.exists()
OUT.mkdir()
(OUT / "logs").mkdir()
commands = []


def run(name, argv, cwd=CLONE, data=None, timeout=600):
    started = time.monotonic()
    argv = [str(a) for a in argv]
    try:
        result = subprocess.run(argv, cwd=cwd, capture_output=True, input=data, timeout=timeout)
    except subprocess.TimeoutExpired as e:
        # A subprocess deadline is not a verified contained-child retirement.
        (OUT / "logs" / (name + ".log")).write_bytes((e.stdout or b"") + (e.stderr or b""))
        save(OUT / "failure.json", dict(stage=name, status="deadline", owned_child_exit_unverified=True))
        raise
    (OUT / "logs" / (name + ".log")).write_bytes(result.stdout + result.stderr)
    commands.append(dict(name=name, command=argv, cwd=str(cwd), exit_code=result.returncode,
                         elapsed_seconds=round(time.monotonic() - started, 3), log="logs/" + name + ".log"))
    if data is not None:
        commands[-1]["stdin_sha256"] = sha(data)
    save(OUT / "commands.json", commands)
    print(name + ": exit " + str(result.returncode), flush=True)
    if result.returncode:
        save(OUT / "failure.json", dict(stage=name, exit_code=result.returncode, source_revision=REV))
        raise RuntimeError(name)
    return result.stdout


run("clone", ["git", "clone", "--local", "--no-hardlinks", "--no-checkout", ROOT, CLONE], cwd=ROOT)
run("checkout", ["git", "checkout", "--detach", REV])
assert not run("source-status", ["git", "status", "--porcelain"]).strip()
host = json.loads(run("host", ["powershell", "-NoProfile", "-Command",
    "$fatIdentity=[System.Security.Principal.WindowsIdentity]::GetCurrent();"
    "$fatPrincipal=[System.Security.Principal.WindowsPrincipal]::new($fatIdentity);"
    "$fatOS=Get-CimInstance Win32_OperatingSystem;"
    "[ordered]@{identity=$fatIdentity.Name;elevated=$fatPrincipal.IsInRole("
    "[System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$fatOS.Caption;"
    "version=$fatOS.Version;architecture=$fatOS.OSArchitecture}|ConvertTo-Json -Compress"]))
assert host["identity"] == "BLACKGLASS-WIN1\\Jules" and not host["elevated"]
catalog = json.loads((CLONE / "tools/build-inputs.json").read_bytes())
names = set(catalog["files"]) | {p.relative_to(CLONE).as_posix() for p in (CLONE / "source").rglob("*") if p.is_file()}
names |= {"AGENTS.md", "spec/work/units.json", "spec/catalog/input-dependencies.json",
          "spec/tools/specctl.py", "tools/check-source-map.py", "tools/check-build-boundaries.py"}
inputs = {p: sha((CLONE / p).read_bytes()) for p in sorted(names)}
save(OUT / "source-inputs.json", inputs)
refs = ("\n".join(REV + ":" + p for p in inputs) + "\n").encode()
rows = run("source-tree", ["git", "cat-file", "--batch-check"], data=refs).splitlines()
assert len(rows) == len(inputs)
blobs = {}
for path, row in zip(inputs, rows, strict=True):
    blob, kind, size = row.split()
    assert kind == b"blob"
    data = (CLONE / path).read_bytes()
    assert str(len(data)).encode() == size
    assert hashlib.sha1(b"blob " + size + b"\0" + data).hexdigest() == blob.decode()
    blobs[path] = blob.decode()
save(OUT / "source-blob-bindings.json", blobs)
run("source-map", [sys.executable, "-X", "utf8", "tools/check-source-map.py"])
run("python-environment", [sys.executable, "-c",
    "import sys,importlib.metadata as m;print(sys.version);print('PyYAML='+m.version('PyYAML'));print('jsonschema='+m.version('jsonschema'))"])
run("cmake-version", ["cmake", "--version"])
gcc = Path(json.loads((ROOT / ".aide/evidence/2026-10-13-fat-tree-sessions/gcc-identity.json").read_bytes())["path"])
run("gcc-version", [gcc, "--version"])
run("gcc-c90", [gcc, "-std=c90", "-pedantic-errors", "-Wall", "-Wextra", "-Werror", "-I", "source", "-fsyntax-only", "source/portable/fat/allocation.c"])
save(OUT / "gcc-identity.json", dict(path=str(gcc), sha256=sha(gcc.read_bytes()), scope="C90 syntax only; no GCC runtime/ABI qualification"))
build = OUT / "build"
run("configure", ["cmake", "--preset", "windows-bootstrap", "-B", build, "-DPython3_EXECUTABLE=" + sys.executable])
run("build", ["cmake", "--build", build, "--config", "Release", "--parallel", "4"], timeout=1800)
identity = json.loads((build / "generated/build-identity.json").read_bytes())
assert identity["identity"]["source_revision"] == REV and identity["identity"]["source_state"] == "clean"
assert identity["inputs"] == {p: inputs[p] for p in catalog["files"]}
save(OUT / "build-identity.json", identity)
run("boundaries", [sys.executable, "-X", "utf8", "tools/check-build-boundaries.py", "--build", build, "--output", OUT / "build-boundaries.json"])
tests = json.loads(run("test-catalog", ["ctest", "--test-dir", build, "-C", "Release", "--show-only=json-v1"]))
assert len(tests["tests"]) == 120
registered = {t["name"] for t in tests["tests"]}
assert {"evidence.fat_tree_history", "image.fat_tree_extraction", "image.fat_tree_extraction_worker",
        "image.fat_tree_metadata", "image.fat_tree_content", "capture.fat_content_stream",
        "acquisition.fat_metadata", "frontend.fat_tree_sessions"}.issubset(registered)
save(OUT / "test-catalog.json", tests)
run("native-tests", ["ctest", "--test-dir", build, "-C", "Release", "--parallel", "4", "--output-on-failure"], timeout=3000)
shutil.copyfile(build / "Testing/Temporary/LastTest.log", OUT / "native-details.log")
counts = {}
for filename, methods, cases in (("fat-tree-history-cases.json", 13, 78),
                                 ("fat-tree-extraction-cases.json", 11, 46),
                                 ("fat-tree-extraction-worker-cases.json", 11, 29)):
    value = json.loads((build / filename).read_bytes())
    assert value["passed"] and value["methods"] == methods and value["cases"] == cases, filename
    save(OUT / filename, value)
    counts[filename] = dict(methods=methods, cases=cases)
for filename in ("fat-content-stream-cases.json", "fat-tree-content-cases.json",
                 "fat-metadata-cases.json", "fat-tree-metadata-cases.json"):
    source = build / filename
    if source.exists():
        shutil.copyfile(source, OUT / filename)
run("tooling", [sys.executable, "-X", "utf8", "-m", "unittest", "discover", "-s", "spec/tools/tests", "-v"], timeout=900)
tooling = (OUT / "logs/tooling.log").read_text(encoding="utf-8")
assert re.search(r"^Ran 238 tests ", tooling, re.M) and re.search(r"^OK \(skipped=2\)$", tooling, re.M)
structure = json.loads(run("spec-check", [sys.executable, "-X", "utf8", "spec/tools/specctl.py", "check"]))
run("index", [sys.executable, "-X", "utf8", "spec/tools/specctl.py", "index", "--check"])
run("manifest", [sys.executable, "-X", "utf8", "spec/tools/specctl.py", "verify-manifest"])
run("context", [sys.executable, "-X", "utf8", "spec/tools/specctl.py", "context", "--work", "DE-W056",
                "--output", OUT / "context", "--byte-budget", "950000"])
run("verify-context", [sys.executable, "-X", "utf8", "spec/tools/specctl.py", "verify-context", OUT / "context"])
shutil.copyfile(OUT / "context/manifest.json", OUT / "context-manifest.json")
launch = json.loads(run("product-launch", [build / "Release/disked.exe", "build", "inspect", "--json"]))["result"]
assert launch["source_revision"] == REV and launch["version"] == identity["identity"]["version"]
dumpbin = Path(identity["compiler_path"]).with_name("dumpbin.exe")
artifacts = []
for name in ("disked", "fat_tree_history_probe", "fat_tree_extraction_probe",
             "fat_tree_extraction_worker_probe", "fat_tree_extraction_worker_fault"):
    path = build / "Release" / (name + ".exe")
    for mode in ("headers", "imports", "dependents"):
        run(name + "-" + mode, [dumpbin, "/" + mode, path])
    artifacts.append(dict(kind=name, path=str(path), bytes=path.stat().st_size,
                          sha256=sha(path.read_bytes()), source_revision=REV))
objects = [dict(path=str(p), bytes=p.stat().st_size, sha256=sha(p.read_bytes()))
           for p in sorted(build.glob("*_headers.dir/Release/*.obj"))]
expected_headers = sum(len(row.split()) - 1 for row in re.findall(r"^  private_header_check\(([^)]+)\)",
                                                               (CLONE / "CMakeLists.txt").read_text(), re.M))
assert len(objects) == expected_headers
save(OUT / "header-objects.json", objects)
config = OUT / "build-configuration"
config.mkdir()
for name in ("CMakeCache.txt", "disked.vcxproj", "disked_fat_tree_history.vcxproj",
             "disked_fat_tree_history_headers.vcxproj", "disked_fat_tree_extraction.vcxproj",
             "disked_fat_tree_extraction_worker.vcxproj", "disked_fat_tree_extraction_worker_fault.vcxproj",
             "fat_tree_history_probe.vcxproj", "fat_tree_extraction_probe.vcxproj",
             "fat_tree_extraction_worker_probe.vcxproj", "fat_tree_extraction_worker_fault.vcxproj"):
    shutil.copyfile(build / name, config / name)
shutil.copyfile(build / "private-header-usage.json", OUT / "private-header-usage.json")
assert not run("final-source-status", ["git", "status", "--porcelain"]).strip()
assert all(sha((CLONE / path).read_bytes()) == digest for path, digest in inputs.items())
save(OUT / "summary.json", dict(source_revision=REV, source_state="clean", host=host, passed=True,
     native_test_groups=120, independent_header_compilations=len(objects), tooling_count=238, tooling_skipped=2,
     source_input_count=len(inputs), structural=structure, artifacts=artifacts, focused_cases=counts,
     ordinary_recursive_extraction_qualified=True, physical_device_access=False,
     owner_accepted=False, release_ready=False))
print("Full clean-source recursive campaign completed.", flush=True)
