"""Compress selected superseded receipts once; retain exact verified bytes."""
import hashlib
import json
import lzma
from pathlib import Path

root = Path(__file__).resolve().parent
names = ['python-runtime-first.json', 'proof-32-policy-refusal.json',
         'policy-refusal-cleanup.json', 'proof-32-first-worker.json',
         'first-guest-proof-reports.json', 'first-proof-cleanup.json',
         'proof-32-private-station-first.json', 'proof-32-device-default-acl.json',
         'proof-32-device-scoped-first.json', 'proof-32-elevated-worker-diagnostic.json',
         'proof-32-restricted-token-first.json', 'proof-32-restricted-token-exit.json',
         'proof-32-device-delete-denied.json', 'proof-32-before-size-parameter.json',
         'proof-32-first-parameterized.json', 'proof-512-small-proof-deadline.json',
         'host-refusal.json']
archive = root / 'observations.json.xz'
if archive.exists():
    raise RuntimeError('Do not create duplicate observation archives')
records, total = {}, 0
for name in names:
    path = root / name
    if path.parent.resolve() != root or path.is_symlink() or path.is_junction():
        raise RuntimeError('Unsafe receipt path')
    data = path.read_bytes()
    total += len(data)
    if total > 1024 * 1024:
        raise RuntimeError('Receipt archive input bound exceeded')
    records[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'utf8': data.decode('utf-8')}
compressed = lzma.compress(json.dumps(records, sort_keys=True).encode(), preset=9 | lzma.PRESET_EXTREME)
if len(compressed) > 131072:
    raise RuntimeError('Receipt archive output bound exceeded')
with archive.open('xb') as stream:
    stream.write(compressed)
restored = json.loads(lzma.decompress(archive.read_bytes()))
for name, record in records.items():
    raw = restored[name]['utf8'].encode('utf-8')
    if raw != (root / name).read_bytes() or hashlib.sha256(raw).hexdigest() != record['sha256']:
        raise RuntimeError('Archive round trip failed; originals retained')
index = {'files': {name: {'sha256': v['sha256'], 'bytes': len(v['utf8'].encode('utf-8'))}
                   for name, v in records.items()},
         'original_bytes': total, 'archive_bytes': len(compressed),
         'archive_sha256': hashlib.sha256(compressed).hexdigest(), 'round_trip_verified': True}
(root / 'observations-index.json').write_text(json.dumps(index, indent=2)+'\n', encoding='utf-8', newline='\n')
# Exact ordinary files only, after every retained byte has been verified.
for name in names:
    (root / name).unlink()
print(json.dumps({k: v for k, v in index.items() if k != 'files'}))
