"""Audit retained bytes against Git blobs and frozen native artifacts."""
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path.cwd().resolve()
DIR = ROOT / ".aide/evidence/2026-10-14-fat-recursive-qualification"
REV = "243f748e6a6af62469b184614d4d623b8ad239ea"
assert DIR.is_dir()
summary = json.loads((DIR / "summary.json").read_bytes())
assert summary["source_revision"] == REV and summary["passed"]
retention = json.loads((DIR / "retention.json").read_bytes())
inputs = json.loads((DIR / "source-inputs.json").read_bytes())
blobs = json.loads((DIR / "source-blob-bindings.json").read_bytes())
assert set(inputs) == set(blobs)
count = 0


def sha(data):
    return "sha256:" + hashlib.sha256(data).hexdigest()


for path, expected in inputs.items():
    data = subprocess.check_output(["git", "cat-file", "blob", REV + ":" + path])
    assert sha(data) == expected, path
    assert hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == blobs[path], path
    count += 1
for entry in retention["files"]:
    path = ROOT / entry["path"]
    data = path.read_bytes()
    assert len(data) == entry["bytes"] and sha(data) == entry["sha256"], entry["path"]
    indexed = subprocess.check_output(["git", "cat-file", "blob", ":" + entry["path"]])
    assert indexed == data, entry["path"]
    count += 1
for entry in summary["artifacts"]:
    assert sha(Path(entry["retained_copy"]).read_bytes()) == entry["sha256"], entry["kind"]
    count += 1
handoff = json.loads((ROOT / ".aide/handoffs/DE-W056-qualified-2026-10-14.json").read_bytes())
for entry in handoff["artifacts"]:
    assert sha(Path(entry["path"]).read_bytes()) == entry["sha256"]
    count += 1
print(json.dumps(dict(status="PASS", bindings=count, source_inputs=len(inputs),
                      retained_files=len(retention["files"]), artifacts=len(summary["artifacts"]),
                      source_revision=REV)))
