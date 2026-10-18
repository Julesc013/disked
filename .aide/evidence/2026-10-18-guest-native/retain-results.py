"""Compress raw native/bootstrap observations once and retain readable summaries."""
import hashlib
import json
import lzma
from pathlib import Path

root = Path(__file__).resolve().parent
names = ['compiler-first-response-file.json', 'compiler-first-cleanup.json',
         'compiler-native-temp-diagnostic.json', 'compiler-diagnostic-cleanup.json',
         'context-before-temp-repair.json', 'compiler-results.json', 'tooling-checks.json',
         'source-snapshot-tests.json']
archive = root / 'observations.json.xz'
if archive.exists():
    raise RuntimeError('Raw observations already retained; do not duplicate')
raw = {}
for name in names:
    path = root / name
    if path.is_symlink() or path.is_junction() or path.resolve().parent != root:
        raise ValueError('Unsafe retained receipt')
    data = path.read_bytes()
    raw[name] = {'sha256': hashlib.sha256(data).hexdigest(), 'utf8': data.decode('utf-8')}
if sum(len(v['utf8'].encode()) for v in raw.values()) > 1048576:
    raise ValueError('Raw observation budget exceeded')
data = lzma.compress(json.dumps(raw, sort_keys=True).encode(), preset=9 | lzma.PRESET_EXTREME)
if len(data) > 131072:
    raise ValueError('Compressed observation budget exceeded')
with archive.open('xb') as stream:
    stream.write(data)
if json.loads(lzma.decompress(archive.read_bytes())) != raw:
    raise RuntimeError('Archive round trip failed; originals preserved')
index = {'archive_bytes': len(data), 'archive_sha256': hashlib.sha256(data).hexdigest(),
         'round_trip_verified': True, 'originals': {k: v['sha256'] for k, v in raw.items()}}
(root / 'observations-index.json').write_text(json.dumps(index, indent=2)+'\n', encoding='utf-8', newline='\n')
for name in names[-3:]:
    record = json.loads(raw[name]['utf8'])
    record['raw_archive'] = archive.name
    record['raw_original_sha256'] = raw[name]['sha256']
    if name == 'compiler-results.json':
        for architecture in record['guest']['proof']['architectures'].values():
            for command in architecture['commands']:
                command['output_sha256'] = hashlib.sha256(command.pop('output').encode()).hexdigest()
    else:
        record['log_sha256'] = hashlib.sha256(record.pop('log').encode()).hexdigest()
    (root / name).write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8', newline='\n')
for name in names[:-3]:
    (root / name).unlink()
print(json.dumps(index))
