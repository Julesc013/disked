"""Private supplied-reader/table/stream regressions on pinned Win32/WOW64, not a Win32 product."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, required=True)
parser.add_argument("--codemodel", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root, model_build, output = args.root.resolve(), args.codemodel.resolve(), args.output.resolve()
output.mkdir()
fixture, build = output / "fixture", output / "build"
fixture.mkdir()


def sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def save(name, value):
    (output / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")


revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip()
assert revision == json.loads((model_build.parent / "summary.json").read_bytes())["source_revision"]
inputs = json.loads((model_build.parent / "inputs.json").read_bytes())
assert all(sha(root / name) == digest for name, digest in inputs.items())
assert not subprocess.check_output(["git", "status", "--porcelain"], cwd=root)
reply = model_build / ".cmake/api/v1/reply"
model = json.loads(next(reply.glob("codemodel-v2-*.json")).read_bytes())
targets = {t["id"]: t for t in model["configurations"][0]["targets"]}
by_name = {t["name"]: t for t in targets.values()}


def data(name):
    return json.loads((reply / by_name[name]["jsonFile"]).read_bytes())


def own(name):
    return {Path(p["path"]) if Path(p["path"]).is_absolute() else root / p["path"]
            for p in data(name).get("sources", []) if Path(p["path"]).suffix in (".c", ".cpp")}


def closure(name, seen=None):
    seen = set() if seen is None else seen
    if name in seen:
        return set()
    seen.add(name)
    sources = own(name)
    for edge in data(name).get("dependencies", []):
        sources |= closure(targets[edge["id"]]["name"], seen)
    return sources


probe_names = ("ntfs_upcase_probe", "ntfs_capture_probe", "ntfs_stream_probe", "ntfs_names_probe")
probe_sources = {n: own(n) for n in probe_names}
probe = set.union(*probe_sources.values())
common = set.union(*(closure(n) for n in probe_names)) - probe
assert all(p.is_relative_to(root / "source") for p in common)
quote = lambda path: '"' + path.as_posix() + '"'
lines = ["cmake_minimum_required(VERSION 3.27)", "project(NtfsUpcaseWin32 LANGUAGES C CXX)",
         'set(CMAKE_CONFIGURATION_TYPES Release CACHE STRING "Fixture profile" FORCE)',
         "set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)", "set(CMAKE_C_STANDARD 90)",
         "set(CMAKE_C_STANDARD_REQUIRED YES)", "set(CMAKE_C_EXTENSIONS NO)",
         "set(CMAKE_CXX_STANDARD 14)", "set(CMAKE_CXX_STANDARD_REQUIRED YES)", "set(CMAKE_CXX_EXTENSIONS NO)",
         'if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4 OR NOT CMAKE_VS_PLATFORM_NAME STREQUAL "Win32" OR NOT CMAKE_CXX_COMPILER_VERSION VERSION_EQUAL "19.44.35228.0" OR NOT CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION STREQUAL "10.0.19041.0")',
         'message(FATAL_ERROR "Pinned Win32 compiler and SDK required")', "endif()",
         "find_package(Python3 REQUIRED COMPONENTS Interpreter)", "enable_testing()",
         "add_library(ntfs_fixture STATIC " + " ".join(quote(p) for p in sorted(common)) + ")",
         "add_executable(ntfs_upcase_probe " + " ".join(quote(p) for p in sorted(probe_sources["ntfs_upcase_probe"])) + ")",
         "target_link_libraries(ntfs_upcase_probe PRIVATE ntfs_fixture)",
         "target_link_options(ntfs_upcase_probe PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)"]
for name in probe_names[1:]:
    lines.extend(["add_executable(" + name + " " + " ".join(quote(p) for p in sorted(probe_sources[name])) + ")",
                  "target_link_libraries(" + name + " PRIVATE ntfs_fixture)",
                  "target_link_options(" + name + " PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)"])
headers = []
for suffix in ("c", "cpp"):
    path = fixture / ("header." + suffix)
    path.write_text('#include "portable/ntfs/ntfs.h"\n', encoding="utf-8", newline="\n")
    headers.append(path)
for header in ("runtime/capture/ntfs_capture.h", "runtime/capture/ntfs_stream.h", "runtime/capture/ntfs_names.h"):
    path = fixture / (Path(header).stem + ".cpp")
    path.write_text('#include "' + header + '"\n', encoding="utf-8", newline="\n")
    headers.append(path)
lines.append("add_library(ntfs_fixture_headers OBJECT " + " ".join(quote(p) for p in headers) + ")")
for target in ("ntfs_fixture", "ntfs_fixture_headers", *probe_names):
    lines.extend(["target_include_directories(" + target + " PRIVATE " + quote(root / "source") + ")",
                  "target_compile_options(" + target + ' PRIVATE /W4 /WX /GS /sdl /guard:cf "$<$<COMPILE_LANGUAGE:CXX>:/permissive-;/utf-8>")'])
lines.extend(['add_test(NAME portable.ntfs_upcase COMMAND "${Python3_EXECUTABLE}" ' + quote(root / "tests/property/test_ntfs_upcase.py") + ' --probe "$<TARGET_FILE:ntfs_upcase_probe>" --output "${CMAKE_BINARY_DIR}/ntfs-upcase-cases.json")',
              "add_test(NAME portable.ntfs_upcase_guard COMMAND ntfs_upcase_probe --guard)",
              "set_tests_properties(portable.ntfs_upcase portable.ntfs_upcase_guard PROPERTIES TIMEOUT 180)"])
for kind in ("capture", "directory", "membership", "upcase_capture", "stream", "names"):
    probe_name = "ntfs_stream_probe" if kind == "stream" else "ntfs_names_probe" if kind == "names" else "ntfs_capture_probe"
    lines.extend(['add_test(NAME image.ntfs_' + kind + ' COMMAND "${Python3_EXECUTABLE}" ' + quote(root / ("tests/images/test_ntfs_" + kind + ".py")) + ' --probe "$<TARGET_FILE:' + probe_name + '>" --output "${CMAKE_BINARY_DIR}/ntfs-' + kind + '-cases.json")',
                  "set_tests_properties(image.ntfs_" + kind + " PROPERTIES TIMEOUT 180)"])
lines.extend(['add_test(NAME image.ntfs_closure COMMAND "${Python3_EXECUTABLE}" ' + quote(root / "tests/images/test_ntfs_closure.py") + ' --capture "$<TARGET_FILE:ntfs_capture_probe>" --join "$<TARGET_FILE:ntfs_stream_probe>" --output "${CMAKE_BINARY_DIR}/ntfs-closure-cases.json")',
              "set_tests_properties(image.ntfs_closure PROPERTIES TIMEOUT 180)"])
(fixture / "CMakeLists.txt").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
save("fixture-sources.json", {str(p): sha(p) for p in sorted(common | probe)})
save("inputs.json", inputs)
summary = dict(status="running", source_revision=revision, observed_at=datetime.now(timezone.utc).isoformat(),
               host=platform.platform(), stages=[], recipe_sha256=sha(Path(__file__).resolve()),
               scope="Nine private supplied-reader/table/stream tests and five C/C++ headers under Win32/WOW64. Actual closure derived from same-source x64 codemodel. Not full Win32 product,16-bit/DOS,big-endian or historical-host qualification.",
               full_win32_product_qualified=False, owner_accepted=False, full_0_1_0_complete=False)


def run(name, command):
    command = list(map(str, command))
    start = time.monotonic()
    with (output / (name + ".log")).open("wb") as log:
        result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
    summary["stages"].append(dict(name=name, command=command, cwd=str(root), exit_code=result.returncode,
                                  seconds=time.monotonic() - start, log=name + ".log"))
    save("summary.json", summary)
    print(name, result.returncode, flush=True)
    assert result.returncode == 0, name


try:
    run("configure", ["cmake", "-S", fixture, "-B", build, "-G", "Visual Studio 17 2022", "-A", "Win32,version=10.0.19041.0",
                      "-T", "v143,version=14.44.35207,host=x64", "-DCMAKE_SYSTEM_VERSION=10.0.19041.0", "-DPython3_EXECUTABLE=" + sys.executable])
    run("build", ["cmake", "--build", build, "--config", "Release", "--parallel", "2"])
    run("native", ["ctest", "--test-dir", build, "-C", "Release", "--parallel", "1", "--output-on-failure", "--output-junit", output / "native-junit.xml"])
    cases = ET.parse(output / "native-junit.xml").getroot().findall(".//testcase")
    assert len(cases) == 9 and all(c.find("failure") is None and c.find("error") is None and c.find("skipped") is None for c in cases)
    actual = json.loads((build / "ntfs-upcase-cases.json").read_bytes())
    expected = json.loads((root / ".aide/evidence/2026-10-17-ntfs-upcase/expected-before-implementation.json").read_bytes())
    assert actual["status"] == "pass" and actual["tables"] == expected["tables"] and actual["recipe_sha256"] == expected["recipe_sha256"]
    summary.update(native_groups=9, mapping_units=actual["mapping_units"], comparison_cases=actual["comparison_cases"])
    capture = json.loads((build / "ntfs-upcase_capture-cases.json").read_bytes())
    capture_expected = json.loads((root / ".aide/evidence/2026-10-17-ntfs-upcase-capture/expected-after-binding-review.json").read_bytes())
    assert capture["status"] == "pass" and capture["count"] == 158 and capture["expected_cases_sha256"] == capture_expected["expected_cases_sha256"]
    assert capture["recipe_sha256"] == capture_expected["recipe_sha256"]
    summary["upcase_capture_cases"] = capture["count"]
    compiler_file = next((build / "CMakeFiles").glob("*/CMakeCXXCompiler.cmake"))
    compiler = Path(re.search(r'set\(CMAKE_CXX_COMPILER "([^\"]+)"\)', compiler_file.read_text(encoding="utf-8"))[1])
    binary = build / "Release/ntfs_upcase_probe.exe"
    summary["artifact"] = dict(path=str(binary), sha256=sha(binary), bytes=binary.stat().st_size)
    for mode in ("headers", "imports", "dependents"):
        run(mode, [compiler.with_name("dumpbin.exe"), "/" + mode, binary])
    text = (output / "headers.log").read_text(encoding="utf-8")
    assert all(value in text for value in ("14C machine (x86)", "Dynamic base", "NX compatible", "Control Flow Guard"))
    summary["artifacts"] = []
    for name in probe_names:
        path = build / "Release" / (name + ".exe")
        summary["artifacts"].append(dict(path=str(path), sha256=sha(path), bytes=path.stat().st_size))
        if name == "ntfs_upcase_probe":
            continue
        for mode in ("headers", "imports", "dependents"):
            run(name + "-" + mode, [compiler.with_name("dumpbin.exe"), "/" + mode, path])
        text = (output / (name + "-headers.log")).read_text(encoding="utf-8")
        assert all(value in text for value in ("14C machine (x86)", "Dynamic base", "NX compatible", "Control Flow Guard"))
    summary["header_artifacts"] = [dict(path=str(p), sha256=sha(p)) for p in sorted((build / "ntfs_fixture_headers.dir/Release").glob("*.obj"))]
    assert len(summary["header_artifacts"]) == 5
    summary["inputs_unchanged"] = all(sha(root / name) == digest for name, digest in inputs.items())
    summary["checkout_clean"] = not subprocess.check_output(["git", "status", "--porcelain"], cwd=root)
    assert summary["inputs_unchanged"] and summary["checkout_clean"]
    summary["status"] = "pass"
except BaseException as error:
    summary.update(status="fail", error=repr(error))
    save("summary.json", summary)
    raise
save("summary.json", summary)
