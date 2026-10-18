"""Retain coordinator outputs once, compressed; keep a small readable summary."""
import hashlib
import json
import lzma
from pathlib import Path
import re

root = Path(__file__).resolve().parent
names = ['spec-checks-first-timeout.json', 'spec-checks-context-budget.json', 'spec-checks.json']
records = {}
for name in names:
    path = root / name
    if path.resolve().parent != root or path.is_symlink() or path.is_junction():
        raise RuntimeError('Unsafe coordinator receipt')
    data = path.read_bytes()
    records[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'utf8': data.decode('utf-8')}
receipt = json.loads(records['spec-checks.json']['utf8'])
if receipt['status'] != 'pass' or sum(len(v['utf8'].encode()) for v in records.values()) > 1048576:
    raise RuntimeError('Incomplete or oversized coordinator evidence')
suite = next(c for c in receipt['commands'] if 'spec/tools/tests' in c['arguments'])
receipt['specification_tests_run'] = int(re.search(r'Ran (\d+) tests?', suite['stderr'])[1])
receipt['specification_tests_skipped'] = int(re.search(r'skipped=(\d+)', suite['stderr'])[1])
archive = root / 'coordinator-observations.json.xz'
with archive.open('xb') as stream:
    stream.write(lzma.compress(json.dumps(records, sort_keys=True).encode(), preset=9 | lzma.PRESET_EXTREME))
restored = json.loads(lzma.decompress(archive.read_bytes()))
if restored != records:
    raise RuntimeError('Coordinator archive verification failed; originals preserved')
receipt['raw_archive'] = archive.name
receipt['raw_archive_sha256'] = hashlib.sha256(archive.read_bytes()).hexdigest()
receipt['raw_archive_entries'] = {name: record['sha256'] for name, record in records.items()}
for command in receipt['commands']:
    for field in ('stdout', 'stderr'):
        command[field + '_sha256'] = hashlib.sha256(command.pop(field).encode()).hexdigest()
receipt['context_removed_after_verification'] = True
(root / 'spec-checks.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8', newline='\n')
for name in names[:-1]:
    (root / name).unlink()
print(json.dumps({'status': receipt['status'], 'specification_tests_run': receipt['specification_tests_run'],
                  'skipped': receipt['specification_tests_skipped'], 'archive_bytes': archive.stat().st_size,
                  'context_bytes_removed': receipt['context_bytes']}))
