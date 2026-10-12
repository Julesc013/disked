"""Audit retained receipts against their native source revision and Git blobs.

This detects missing/changed evidence and applicability mistakes. It does not
authenticate an approval, establish independent review or rerun native tests.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def main():
    evidence = Path(__file__).resolve().parent
    root = evidence.parents[2]
    summary = json.loads((evidence / "summary.json").read_bytes())
    inputs = json.loads((evidence / "source-inputs.json").read_bytes())
    bindings = json.loads((evidence / "source-blob-bindings.json").read_bytes())
    identity = json.loads((evidence / "build-identity.json").read_bytes())
    commands = json.loads((evidence / "commands.json").read_bytes())
    inventory = json.loads((evidence / "retention.json").read_bytes())
    boundaries = json.loads((evidence / "build-boundaries.json").read_bytes())
    revision = summary["source_revision"]
    assert summary["passed"] and summary["source_state"] == "clean"
    assert not summary["owner_accepted"] and not summary["unit_complete"] and not summary["release_ready"]
    assert identity["identity"]["source_revision"] == revision and identity["identity"]["source_state"] == "clean"
    assert set(inputs) == set(bindings) and len(inputs) == summary["source_input_count"]
    tree = subprocess.check_output(["git", "ls-tree", "-r", "-z", revision], cwd=root)
    actual = {}
    for row in tree.split(b"\0"):
        if row:
            header, name = row.split(b"\t", 1)
            name = name.decode()
            if name in inputs:
                actual[name] = header.split()[2].decode()
    assert actual == bindings
    for name, blob in bindings.items():
        data = subprocess.check_output(["git", "cat-file", "blob", blob], cwd=root)
        assert sha(data) == inputs[name], name
    assert all(inputs[name] == value for name, value in identity["inputs"].items())
    assert len(identity["inputs"]) == summary["product_input_count"]
    expected_commands = {"configure", "build", "boundaries", "test-catalog", "native-tests",
                         "checker-negative-fixtures", "tooling", "spec-check", "index", "manifest",
                         "context", "verify-context", "product-launch", "final-source-status"}
    assert expected_commands <= {v["name"] for v in commands}
    for record in commands:
        assert record["exit_code"] == 0 and (evidence / record["log"]).is_file(), record["name"]
    assert summary["native_test_groups"] == 84 and summary["checker_negative_fixtures"] == 16
    assert summary["independent_core_header_compilations"] == 5
    assert boundaries["status"] == "PASS" and not boundaries["violations"]
    assert summary["quoted_include_edges"] == boundaries["quoted_include_edges"]
    assert summary["build_target_count"] == boundaries["target_count"]
    product_closure = set(boundaries["targets"]["disked"]["build_closure"])
    assert not product_closure & {"disked_gpt_fixture_execution", "disked_gpt_fixture_restoration", "disked_gpt_fixture_files",
                                  "disked_json_headers", "disked_command_headers", "disked_invocation_headers"}
    tests = json.loads((evidence / "logs/test-catalog.log").read_bytes())
    assert len(tests["tests"]) == 84
    details = (evidence / "logs/native-tests.log").read_text(encoding="utf-8")
    assert "100% tests passed, 0 tests failed out of 84" in details
    native_details = (evidence / "native-details.log").read_text(encoding="utf-8")
    assert len(re.findall(r"^Test Passed\.$", native_details, re.MULTILINE)) == 84
    headers = json.loads((evidence / "header-objects.json").read_bytes())
    assert len(headers) == 5 and all(v["bytes"] > 0 for v in headers)
    assert inventory["source_revision"] == revision
    retained = {p.relative_to(evidence).as_posix() for p in evidence.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts} - {"retention.json"}
    assert retained == set(inventory["files"]), (retained - set(inventory["files"]), set(inventory["files"]) - retained)
    for name, expected in inventory["files"].items():
        assert sha((evidence / name).read_bytes()) == expected, name
    assert sha((evidence / "reproduce.py").read_bytes()) == inputs[".aide/evidence/2026-10-12-build-boundaries/reproduce.py"]
    current = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip()
    print(json.dumps({"status": "PASS", "native_source_revision": revision, "current_revision": current,
                      "retained_files": len(retained), "source_blob_bindings": len(inputs),
                      "applicability": "Exact native source revision and fixture scope; evidence/metadata integration may be later.",
                      "owner_accepted": False, "release_ready": False}, indent=2))


if __name__ == "__main__":
    main()
