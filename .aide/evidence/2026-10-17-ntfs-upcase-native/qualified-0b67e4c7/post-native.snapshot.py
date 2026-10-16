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
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args();root=args.root.resolve();output=args.output.resolve();build=output/'build'
    before=json.loads((output/'inputs.json').read_bytes())
    summary=json.loads((output/'summary-before-post-review.json').read_bytes())
    assert summary['status']=='fail' and 'FileNotFoundError' in summary['error']
    assert summary['native_exit_code']==0 and summary['native_groups']==173 and summary['full_native_suite_run']
    assert not summary['native_failed'] and not summary['native_skipped']
    assert summary['source_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip()
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=root)
    assert all(sha(root/n)==h for n,h in before.items())
    registered={r['name'] for r in json.loads((output/'registered.log').read_bytes())['tests']}
    cases=ET.parse(output/'native-junit.xml').getroot().findall('.//testcase')
    assert len(cases)==len(registered)==173 and {c.attrib['name'] for c in cases}==registered
    assert all(c.find('failure') is None and c.find('error') is None and c.find('skipped') is None for c in cases)
    proof=[dict(path=n,sha256=sha(output/n)) for n in ['inputs.json','native.log','native-junit.xml','registered.log','summary-before-post-review.json','recipe-before-post-review.py']]
    summary.pop('error');summary.update(status='post-native-running',native_tests_repeated=False,post_native_recipe_sha256=sha(Path(__file__).resolve()),original_native_proof=proof)
    def write(name,value):(output/name).write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
    def save():write('summary.json',summary)
    def run(name,command):
        command=list(map(str,command));print('BEGIN',name,flush=True);start=time.monotonic()
        with (output/(name+'.log')).open('wb') as log:result=subprocess.run(command,cwd=root,stdout=log,stderr=subprocess.STDOUT)
        summary['stages'].append(dict(name=name,command=command,cwd=str(root),exit_code=result.returncode,seconds=time.monotonic()-start,log=name+'.log'));save();print('END',name,result.returncode,flush=True);return result.returncode
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
    native_expected = json.loads((root / ".aide/evidence/2026-10-17-ntfs-upcase-native/expected-after-test-review.json").read_bytes())
    summary["native_upcase"] = {}
    for mode, methods in (("file", 8), ("worker", 10)):
        report = json.loads((build / ("ntfs-upcase-" + mode + "-cases.json")).read_bytes())
        name = "tests/images/test_ntfs_upcase_" + mode + ".py"
        assert report["status"] == "pass" and report["methods"] == methods
        assert report["failures"] == report["errors"] == 0 and not report["unverified"]
        assert report["recipe_sha256"] == native_expected["recipes"][name]
        assert all(r["before_sha256"] == r["after_sha256"] for r in report["source_receipts"])
        summary["native_upcase"][mode] = dict(cases=report["cases"], methods=report["methods"], recipe_sha256=report["recipe_sha256"])
    assert summary["full_native_suite_run"]

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
    assert len(objects) == 67
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
    assert run("context", [sys.executable, "spec/tools/specctl.py", "context", "--work", "DE-W101", "--output", output / "context",
                          "--byte-budget", "1200000", "--artifact-byte-budget", "16777216"]) == 0
    assert run("verify-context", [sys.executable, "spec/tools/specctl.py", "verify-context", output / "context"]) == 0
    summary["inputs_unchanged"] = all(sha(root / name) == digest for name, digest in before.items())
    summary["source_status_after"] = subprocess.check_output(["git", "status", "--porcelain"], cwd=root, text=True)
    assert summary["inputs_unchanged"] and not summary["source_status_after"]
    summary["status"] = "pass"
    save()
    print('Completed all original-source post-native checks without repeating the passing native campaign',flush=True)

if __name__=='__main__':
    main()
