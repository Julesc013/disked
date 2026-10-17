"""Exact-source full native qualification for native held-file/owned-reader NTFS table binding."""
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


def sha(path):
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    output.mkdir()
    build = output / "build"
    inputs = set(json.loads((root / "tools/build-inputs.json").read_bytes())["files"])
    inputs.update(row["path"] for row in json.loads((root / "spec/catalog/input-dependencies.json").read_bytes())["inputs"])
    inputs.update(p.relative_to(root).as_posix() for p in (root / "source").rglob("*") if p.is_file())
    before = {name: sha(root / name) for name in sorted(inputs)}

    def write(name, value):
        (output / name).write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8", newline="\n")

    write("inputs.json", before)
    summary = dict(status="running", work_id="DE-W105", observed_at=datetime.now(timezone.utc).isoformat(),
                   source_revision=subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root, text=True).strip(),
                   source_status_before=subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True),
                   host=platform.platform(), python=sys.version, stages=[], owner_accepted=False,
                   full_0_1_0_complete=False, full_native_suite_run=False,
                   recipe_sha256=sha(Path(__file__).resolve()),
                   scope="Public same-capture primary name-order observation through the common action/frontends,with bounded explicit projections. Exact all-target x64/full178 native suite. No full collation,host case policy,alias resolution,lookup,physical/elevated/effect/release qualification.")

    def save():
        write("summary.json", summary)

    def run(name, command):
        command = list(map(str, command))
        print("BEGIN", name, flush=True)
        start = time.monotonic()
        with (output / (name + ".log")).open("wb") as log:
            result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
        summary["stages"].append(dict(name=name, command=command, cwd=str(root), exit_code=result.returncode,
                                      seconds=time.monotonic() - start, log=name + ".log"))
        save()
        print("END", name, result.returncode, flush=True)
        return result.returncode

    try:
        assert not summary["source_status_before"], "Clean source checkout required"
        assert run("configure", ["cmake", "--preset", "windows-bootstrap", "-B", build,
                                  "-DPython3_EXECUTABLE=" + sys.executable]) == 0
        assert run("build", ["cmake", "--build", build, "--config", "Release", "--parallel", "4"]) == 0
        assert run("registered", ["ctest", "--test-dir", build, "-C", "Release", "--show-only=json-v1"]) == 0
        registered = {row["name"] for row in json.loads((output / "registered.log").read_bytes())["tests"]}
        contract = json.loads((root / "spec/catalog/ntfs-name-order-command-prototype.json").read_bytes())
        selected = registered
        assert len(registered) == 178 and "image.ntfs_upcase_capture" in registered
        summary["registered_native_groups"] = len(registered)
        summary["selected_native_groups"] = sorted(selected)
        pattern = "^(" + "|".join(re.escape(name) for name in sorted(selected)) + ")$"
        assert run("selected-registration", ["ctest", "--test-dir", build, "-C", "Release", "--show-only=json-v1", "-R", pattern]) == 0
        rows = json.loads((output / "selected-registration.log").read_bytes())["tests"]
        assert len(rows) == len(selected) and {r["name"] for r in rows} == selected
        summary["native_exit_code"] = run("native", ["ctest", "--test-dir", build, "-C", "Release", "--parallel", "1",
                                                        "--output-on-failure", "--stop-on-failure", "-R", pattern,
                                                        "--output-junit", output / "native-junit.xml"])
        cases = ET.parse(output / "native-junit.xml").getroot().findall(".//testcase")
        summary["native_groups"] = len(cases)
        summary["full_native_suite_run"] = {c.attrib["name"] for c in cases} == registered and len(cases) == len(registered)
        summary["native_failed"] = [c.attrib["name"] for c in cases if c.find("failure") is not None or c.find("error") is not None]
        summary["native_skipped"] = [c.attrib["name"] for c in cases if c.find("skipped") is not None]
        summary["native_not_run"] = sorted(selected - {c.attrib["name"] for c in cases})
        assert summary["native_exit_code"] == 0 and len(cases) == len(selected) and not summary["native_failed"] and not summary["native_skipped"]
        actual = json.loads((build / "ntfs-upcase-cases.json").read_bytes())
        expected = json.loads((root / ".aide/evidence/2026-10-17-ntfs-upcase/expected-before-implementation.json").read_bytes())
        assert actual["status"] == "pass" and actual["tables"] == expected["tables"]
        assert actual["recipe_sha256"] == expected["recipe_sha256"]
        assert actual["mapping_units"] == 327680 and actual["comparison_cases"] == expected["comparison_cases"]
        summary["mapping_units"] = actual["mapping_units"]
        summary["comparison_cases"] = actual["comparison_cases"]
        guard = next(c for c in cases if c.attrib["name"] == "portable.ntfs_upcase_guard")
        guard_result = json.loads(guard.find("system-out").text.strip())
        assert guard_result == {"status": "pass", "guard_cases": 78}
        summary["guard_cases"] = guard_result["guard_cases"]
        capture = json.loads((build / "ntfs-upcase-capture-cases.json").read_bytes())
        capture_expected = json.loads((root / ".aide/evidence/2026-10-17-ntfs-upcase-capture/expected-after-binding-review.json").read_bytes())
        assert capture["status"] == "pass" and capture["count"] == 158
        assert capture["expected_cases_sha256"] == capture_expected["expected_cases_sha256"]
        assert capture["recipe_sha256"] == capture_expected["recipe_sha256"]
        assert len(capture["cases"]) == 158 and all(c["passed"] for c in capture["cases"])
        summary["upcase_capture_cases"] = capture["count"]
        native_expected = json.loads((root / ".aide/evidence/2026-10-17-ntfs-upcase-command/expected-after-startup-review.json").read_bytes())
        summary["native_upcase"] = {}
        for mode, methods in (("file", 8), ("worker", 10)):
            report = json.loads((build / ("ntfs-upcase-" + mode + "-cases.json")).read_bytes())
            name = "tests/images/test_ntfs_upcase_" + mode + ".py"
            assert report["status"] == "pass" and report["methods"] == methods
            assert report["failures"] == report["errors"] == 0 and not report["unverified"]
            assert report["recipe_sha256"] == native_expected["recipes"][name]
            assert all(r["before_sha256"] == r["after_sha256"] for r in report["source_receipts"])
            summary["native_upcase"][mode] = dict(cases=report["cases"], methods=report["methods"], recipe_sha256=report["recipe_sha256"])
        commands=json.loads((build/'ntfs-upcase-command-cases.json').read_bytes())
        assert commands['passed'] and commands['cases']==native_expected['frontend_cases']==119
        assert commands['recipe_sha256']==native_expected['recipes']['tests/frontend/test_ntfs_upcase_commands.py']
        assert all(r['before_sha256']==r['after_sha256'] for r in commands['source_receipts'])
        summary['upcase_command_cases']=commands['cases']
        name_order=json.loads((build/'ntfs-name-order-cases.json').read_bytes())
        name_expected=json.loads((root/'.aide/evidence/2026-10-17-ntfs-name-order/expected-after-fixture-review.json').read_bytes())
        assert name_order['status']=='pass' and name_order['count']==name_expected['count']==172
        assert name_order['recipe_sha256']==name_expected['recipe_sha256']
        assert name_order['expected_cases_sha256']==name_expected['expected_cases_sha256']
        assert len(name_order['cases'])==172 and all(r['passed'] for r in name_order['cases'])
        summary['name_order_cases']=name_order['count']
        native_name_expected=json.loads((root/'.aide/evidence/2026-10-17-ntfs-name-order-command/expected-after-fixture-review.json').read_bytes())
        summary['native_name_order']={}
        for mode,methods in [('file',9),('worker',10)]:
            native_report=json.loads((build/('ntfs-name-order-'+mode+'-cases.json')).read_bytes())
            native_recipe='tests/images/test_ntfs_name_order_'+mode+'.py'
            assert native_report['status']=='pass' and native_report['methods']==methods
            assert native_report['failures']==native_report['errors']==0 and not native_report['unverified']
            assert native_report['recipe_sha256']==native_name_expected['recipes'][native_recipe]
            assert native_report['helper_sha256']==native_name_expected['recipes']['tests/images/ntfs_name_order_native_expectations.py']
            assert all(r['before_sha256']==r['after_sha256'] and r['before_bytes']==r['after_bytes'] for r in native_report['source_receipts'])
            summary['native_name_order'][mode]=dict(methods=methods,calls=native_report['calls'])

        command_report=json.loads((build/'ntfs-name-order-command-cases.json').read_bytes())
        assert command_report['status']=='pass' and command_report['passed']
        assert command_report['families']==native_name_expected['families']
        assert command_report['layouts_tested']==native_name_expected['layouts']
        assert command_report['recipe_sha256']==native_name_expected['recipes']['tests/frontend/test_ntfs_name_order_commands.py']
        assert command_report['helper_sha256']==native_name_expected['recipes']['tests/frontend/ntfs_name_order_command_expectations.py']
        assert all(r['before_sha256']==r['after_sha256'] for r in command_report['source_receipts'])
        summary['name_order_command_layouts']=len(command_report['layouts_tested'])
        summary['name_order_command_families']=len(command_report['families'])
        summary['name_order_command_calls']=command_report['calls']

        assert summary['full_native_suite_run']

        identity = json.loads((build / "generated/build-identity.json").read_bytes())
        summary["build_identity"] = identity
        dumpbin = Path(identity["compiler_path"]).with_name("dumpbin.exe")
        summary["artifacts"] = []
        for name in ("disked", "ntfs_upcase_probe", "ntfs_capture_probe", "ntfs_index_probe", "ntfs_file_probe", "ntfs_file_fault", "ntfs_worker_probe", "ntfs_worker_fault", "disked_ntfs_test", "ntfs_inspection_probe", "ntfs_stream_probe", "ntfs_names_probe", "ntfs_block_probe", "ntfs_attributes_probe"):
            path = build / "Release" / (name + ".exe")
            summary["artifacts"].append(dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path)))
            for mode in ("headers", "imports", "dependents"):
                assert run(name + "-" + mode, [dumpbin, "/" + mode, path]) == 0
            headers = (output / (name + "-headers.log")).read_text(encoding="utf-8")
            assert all(text in headers for text in ("8664 machine (x64)", "Dynamic base", "NX compatible", "Control Flow Guard"))
        assert run("c90-version", ["gcc", "--version"]) == 0
        assert run("c90", ["gcc", "-std=c90", "-pedantic-errors", "-Wall", "-Wextra", "-Werror", "-fsyntax-only", "-Isource",
                            *sorted(str(p.relative_to(root)) for p in (root / "source/portable/ntfs").glob("*.c"))]) == 0
        for header in ("ntfs.h", "fixup.h"):
            path = output / (header + ".c")
            path.write_text('#include "portable/ntfs/' + header + '"\n', encoding="utf-8", newline="\n")
            assert run("c90-header-" + header, ["gcc", "-std=c90", "-pedantic-errors", "-Wall", "-Wextra", "-Werror", "-fsyntax-only", "-Isource", path]) == 0
        objects = [p for directory in build.glob("*_headers.dir") for p in (directory / "Release").glob("*.obj")]
        assert len(objects) == 68
        summary["standalone_headers"] = len(objects)
        summary["header_artifacts"] = [dict(path=str(p), sha256=sha(p)) for p in sorted(objects)]
        for name, command in [("source-map", ["tools/check-source-map.py"]), ("index", ["spec/tools/specctl.py", "index", "--check"]),
                               ("structural", ["spec/tools/specctl.py", "check"]),
                               ("tooling", ["-m", "unittest", "discover", "-s", "spec/tools/tests", "-v"]),
                               ("manifest", ["spec/tools/specctl.py", "verify-manifest"])]:
            assert run(name, [sys.executable, *command]) == 0
        text = (output / "tooling.log").read_text(encoding="utf-8")
        summary["tooling_tests_run"] = int(re.findall(r"Ran (\d+) tests in ", text)[-1])
        summary["tooling_skipped"] = int(re.findall(r"skipped=(\d+)", text)[-1]) if "skipped=" in text else 0
        assert summary['tooling_tests_run']==253 and summary['tooling_skipped']==2
        assert run("context", [sys.executable, "spec/tools/specctl.py", "context", "--work", "DE-W105", "--output", output / "context",
                              "--byte-budget", "1300000", "--artifact-byte-budget", "25165824"]) == 0
        assert run("verify-context", [sys.executable, "spec/tools/specctl.py", "verify-context", output / "context"]) == 0
        summary["inputs_unchanged"] = all(sha(root / name) == digest for name, digest in before.items())
        summary["source_status_after"] = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True)
        assert summary["inputs_unchanged"] and not summary["source_status_after"]
        summary["status"] = "pass"
    except BaseException as error:
        summary.update(status="fail", error=repr(error))
        save()
        raise
    save()
    print(summary["status"], summary.get("native_groups"), flush=True)


if __name__ == "__main__":
    main()
