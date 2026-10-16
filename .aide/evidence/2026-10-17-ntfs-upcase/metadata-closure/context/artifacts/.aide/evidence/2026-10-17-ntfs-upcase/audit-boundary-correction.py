"""Observe the exact-source-set correction against an unchanged generated graph."""
import argparse
import copy
import importlib.util
import json
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--root", type=Path, required=True)
parser.add_argument("--build", type=Path, required=True)
parser.add_argument("--contract", type=Path, required=True)
parser.add_argument("--output", type=Path, required=True)
args = parser.parse_args()
root, build = args.root.resolve(), args.build.resolve()
spec = importlib.util.spec_from_file_location("boundary_checker", root / "tools/check-build-boundaries.py")
checker = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checker)
targets, metadata = checker.load_codemodel(root, build, "Release")
usage = json.loads((build / "private-header-usage.json").read_bytes())
contract = json.loads(args.contract.read_bytes())["build_checks"]
results = {}
for name in ("corrected", "missing-upcase", "extra-source"):
    candidate = copy.deepcopy(targets)
    target = next(t for t in candidate if t["name"] == "disked_ntfs")
    if name == "missing-upcase":
        target["sources"] = [s for s in target["sources"] if s["path"] != "source/portable/ntfs/upcase.c"]
    if name == "extra-source":
        target["sources"].append({"path": "source/portable/mbr/mbr.c", "compileGroupIndex": 0})
    result = checker.inspect(root, build, candidate, contract, usage)
    results[name] = {k: result[k] for k in ("status", "violations")}
args.output.write_text(json.dumps(dict(scope="Unchanged candidate codemodel with a corrected canonical exact-source policy and in-memory negative mutations; diagnostic, not a new native qualification.",
                                      results=results, metadata=metadata), indent=2) + "\n", encoding="utf-8", newline="\n")
assert results["corrected"]["status"] == "PASS", results["corrected"]
for name in ("missing-upcase", "extra-source"):
    assert results[name]["status"] == "FAIL" and any("disked_ntfs: unexpected compiled sources" in s for s in results[name]["violations"])
print("Exact source-set correction passes; missing and additional source mutations still fail")
