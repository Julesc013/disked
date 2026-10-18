"""Bounded recipe/retention validation; runs no guest or product commands."""
import ast
import hashlib
import importlib.util
import json
from pathlib import Path
import runpy
import sys
import tarfile
import traceback

HERE = Path(__file__).resolve().parent
def record_failure(kind, error, trace):
    (HERE / 'checkpoint-failure.json').write_text(json.dumps(dict(status='fail',
        error=str(error), traceback=''.join(traceback.format_exception(kind, error, trace))[-8192:]),
        indent=2)+'\n', encoding='utf-8', newline='\n')
sys.excepthook = record_failure
for name in ('campaign.py', 'build-driver.py', 'guest-source.py'):
    ast.parse((HERE / name).read_bytes(), filename=name)
definition = importlib.util.spec_from_file_location('campaign', HERE / 'campaign.py')
campaign = importlib.util.module_from_spec(definition)
definition.loader.exec_module(campaign)
sys.argv = [str(HERE / 'campaign.py'), '--prepare-only']
assert campaign.main() == 0
runpy.run_path(str(HERE / 'validate-archive.py'), run_name='__main__')

verified = []
for receipt in HERE.glob('*.json'):
    data = json.loads(receipt.read_bytes())
    if not isinstance(data, dict):
        continue
    proof = (data.get('guest') or {}).get('proof') or {}
    entries = proof.get('archive_entries')
    if not entries:
        continue
    candidates = [p for p in HERE.glob('*.tar.xz')
                  if hashlib.sha256(p.read_bytes()).hexdigest() == proof['archive_sha256']]
    assert len(candidates) == 1, receipt.name
    actual = {}
    with tarfile.open(candidates[0], 'r|xz') as archive:
        for member in archive:
            assert member.isfile() and member.name not in actual
            with archive.extractfile(member) as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
            actual[member.name] = dict(bytes=member.size, sha256=digest)
    assert entries == actual, receipt.name
    verified.append(dict(receipt=receipt.name, archive=candidates[0].name, entries=len(actual)))
(HERE / 'checkpoint-checks.json').write_text(json.dumps(dict(status='pass',
    scope='Host recipe syntax, Windows PowerShell parse, streaming archive round-trip and retained archive hashes only',
    native_execution=False, archives=verified), indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(dict(status='pass', verified_archives=len(verified))))
