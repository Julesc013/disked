"""Audit retained shared-presentation evidence against exact source Git blobs.

This checks evidence integrity/applicability, not owner approval or native reruns.
"""
import hashlib
import json
from pathlib import Path
import re
import subprocess


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


def git_blobs(root, revision, names):
    raw = subprocess.check_output(["git", "cat-file", "--batch"], cwd=root,
                                  input=("\n".join(revision + ":" + name for name in names) + "\n").encode())
    offset = 0
    for name in names:
        end = raw.index(b"\n", offset)
        header = raw[offset:end].split()
        assert len(header) == 3 and header[1] == b"blob", name
        length = int(header[2])
        value = raw[end + 1:end + length + 1]
        offset = end + length + 2
        yield name, header[0].decode(), value


def main():
    evidence = Path(__file__).resolve().parent
    root = evidence.parents[2]
    summary = json.loads((evidence / "summary.json").read_bytes())
    identity = json.loads((evidence / "build-identity.json").read_bytes())
    inputs = json.loads((evidence / "source-inputs.json").read_bytes())
    bindings = json.loads((evidence / "source-blob-bindings.json").read_bytes())
    commands = json.loads((evidence / "commands.json").read_bytes())
    inventory = json.loads((evidence / "retention.json").read_bytes())
    boundaries = json.loads((evidence / "build-boundaries.json").read_bytes())
    source = summary["source_revision"]
    assert summary["passed"] and summary["source_state"] == "clean"
    assert not summary["owner_accepted"] and not summary["unit_complete"] and not summary["release_ready"]
    assert identity["identity"]["source_revision"] == source and identity["identity"]["source_state"] == "clean"
    assert set(inputs) == set(bindings) and len(inputs) == summary["source_input_count"]
    for name, blob, data in git_blobs(root, source, list(inputs)):
        assert sha(data) == inputs[name] and blob == bindings[name], name
    assert identity["inputs"] == {name: inputs[name] for name in identity["inputs"]}
    assert len(identity["inputs"]) == summary["product_input_count"]
    assert summary["native_test_groups"] == 85 and summary["shared_rule_cases"] == 34
    assert summary["shared_python_tests"] == 8 and summary["independent_header_compilations"] == 7
    assert summary["checker_negative_fixtures"] == 16
    assert {"configure", "build", "boundaries", "native-tests", "tooling", "verify-context", "product-launch", "final-source-status"} <= {v["name"] for v in commands}
    for command in commands:
        assert command["exit_code"] == 0 and (evidence / command["log"]).is_file(), command["name"]
    tests = json.loads((evidence / "logs/test-catalog.log").read_bytes())
    assert len(tests["tests"]) == 85
    details = (evidence / "native-details.log").read_text(encoding="utf-8")
    assert len(re.findall(r"^Test Passed\.$", details, re.MULTILINE)) == 85
    assert "Ran 8 tests" in details and "frontend.shared_presentation" in details
    assert boundaries["status"] == "PASS" and not boundaries["violations"]
    assert summary["quoted_include_edges"] == boundaries["quoted_include_edges"]
    assert summary["build_target_count"] == boundaries["target_count"]
    closure = set(boundaries["targets"]["disked"]["build_closure"])
    assert not closure & {"disked_gpt_fixture_execution", "disked_gpt_fixture_restoration", "disked_gpt_fixture_files",
                          "disked_json_headers", "disked_command_headers", "disked_invocation_headers", "disked_presentation_headers"}
    header_objects = json.loads((evidence / "header-objects.json").read_bytes())
    assert len(header_objects) == 7 and all(v["bytes"] > 0 for v in header_objects)
    rule_receipt = json.loads((evidence / "rule-cases.json").read_bytes())
    assert rule_receipt["passed"] and len(rule_receipt["cases"]) == len(set(rule_receipt["cases"])) == 34
    assert {"request-id-number", "maximum-view-equality", "old-delivery-cannot-clear-new-request",
            "availability-duplicate-identity"} <= set(rule_receipt["cases"])
    assert inventory["source_revision"] == source
    retained = {p.relative_to(evidence).as_posix() for p in evidence.rglob("*")
                if p.is_file() and "__pycache__" not in p.parts} - {"retention.json"}
    assert retained == set(inventory["files"])
    for name, expected in inventory["files"].items():
        assert sha((evidence / name).read_bytes()) == expected, name
    assert sha((evidence / "reproduce.py").read_bytes()) == inputs[".aide/evidence/2026-10-12-shared-presentation/reproduce.py"]
    current = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=root).decode().strip()
    print(json.dumps(dict(status="PASS", native_source_revision=source, current_revision=current,
                         retained_files=len(retained), source_blob_bindings=len(inputs),
                         native_groups=85, shared_rule_cases=34, standalone_headers=7,
                         applicability="Exact source/fixture/host scope; metadata integration may be later.",
                         owner_accepted=False, release_ready=False), indent=2))


if __name__ == "__main__":
    main()
