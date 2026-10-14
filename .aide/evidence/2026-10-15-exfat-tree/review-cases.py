"""Independent supplementary cases for the exact tree collector artifact."""
import argparse
import copy
import hashlib
import itertools
import json
from pathlib import Path
import struct
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--probe', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
sys.path.insert(0, str(args.source / 'tests/images'))
from test_exfat_tree import fixture, entry, name, allocate, fat_address
from test_exfat_capture import Volume
from test_exfat_upcase import namehash
from exfat_directory_vectors import seal

rows, expects = [], []
def case(label, row, complete, diagnostic=None, extra=None):
    rows.append(row)
    expects.append(dict(label=label, complete=complete, diagnostic=diagnostic, extra=extra))

# The custom table intentionally differs from host Unicode case folding.
volume = Volume(fragmented=False)
volume.records += [entry(volume, 'é'), entry(volume, 'e\u0301'), entry(volume, '😀')]
case('volume-specific-names', volume.request(), True, extra='names')
seen = {}
pair = None
for letters in itertools.product(range(65, 91), repeat=3):
    value = namehash(volume.table, letters)
    if value in seen and seen[value] != letters:
        pair = (seen[value], letters)
        break
    seen[value] = letters
assert pair
volume = Volume(fragmented=False)
for units in pair:
    volume.records.append(entry(volume, ''.join(chr(unit) for unit in units)))
case('different-names-same-hash', volume.request(), True, extra='hash-collision')

volume = Volume(fragmented=False)
allocate(volume, [1200])
raw = bytearray(entry(volume, 'time', 1200, 4))
raw[8:12] = bytes(4)
volume.records.append(bytes(seal(raw)))
row = volume.request()
row['regions'].append(dict(offset=str(volume.cluster_offset(1200)), hex=b'test'.hex()))
case('timestamp-separate-from-stream', row, True, extra='timestamp')

for label, changes in [('invalid-first-cluster', dict(first=5000, length=4)),
                      ('invalid-valid-length', dict(first=1200, length=4, valid=5)),
                      ('unaligned-directory', dict(first=1200, length=511, directory=True))]:
    volume = Volume(fragmented=False)
    volume.records.append(entry(volume, 'invalid', **changes))
    case(label, volume.request(), False, 'exfat_tree_invalid_stream')

for field, value in [('read_requests', 0), ('directories', 257), ('content_bytes', 1048577)]:
    _, row, _, _, _ = fixture()
    row['tree_limits'] = {field: str(value)}
    case('invalid-api-' + field, row, None)

volume, row, dirs, _, _ = fixture()
raw = entry(volume, 'self', dirs[0], volume.size * 2, directory=True) + bytes(32)
row['regions'].append(dict(offset=str(volume.cluster_offset(dirs[0])), hex=raw.hex()))
case('directory-self-reference', row, False, 'exfat_tree_crosslink')

volume = Volume(fragmented=False, copies=2, active=1)
volume.links[4] = 0xffffffff
volume.records.append(entry(volume, 'reserved', 4, 4, contiguous=True))
case('inactive-bitmap-alias', volume.request(), False, 'exfat_tree_crosslink')

data = json.dumps(rows, separators=(',', ':')).encode()
result = subprocess.run([str(args.probe.resolve())], input=data, capture_output=True, timeout=100)
assert result.returncode == 0 and not result.stderr, (result.returncode, result.stderr)
values = json.loads(result.stdout)
assert len(values) == len(expects)
for expected, observed in zip(expects, values):
    if expected['complete'] is None:
        assert observed.get('refusal') == 'exfat_tree_inputs' and not observed['requests'], (expected, observed)
        assert observed['source_unchanged'], (expected, observed)
        continue
    tree = observed['observation']
    assert tree['complete'] == expected['complete'], (expected, tree)
    assert not tree['authorizes_effects'] and not tree['current_source_authority']
    assert observed['source_unchanged']
    if expected['diagnostic']:
        assert expected['diagnostic'] in tree['diagnostics'], (expected, tree)
    if expected['extra'] == 'names':
        entries = tree['directories'][0]['namespace']['entries']
        assert [e['original_units'] for e in entries] == [list(map(str, name(text))) for text in ['é', 'e\u0301', '😀']]
        assert all(e['name_usable'] and e['name_hash_matches'] for e in entries)
    if expected['extra'] == 'hash-collision':
        entries = tree['directories'][0]['namespace']['entries']
        assert entries[0]['stored_name_hash'] == entries[1]['stored_name_hash']
        assert entries[0]['original_units'] != entries[1]['original_units']
        assert 'exfat_tree_name_collision' not in tree['diagnostics']
    if expected['extra'] == 'timestamp':
        item = tree['entries'][0]
        assert not item['entry']['metadata_valid'] and item['entry']['stream_valid']
        assert item['content_hex'] == b'test'.hex()
summary = dict(status='pass', cases=len(rows), expectations=expects,
    input_sha256='sha256:' + hashlib.sha256(data).hexdigest(),
    output_sha256='sha256:' + hashlib.sha256(result.stdout).hexdigest(),
    artifact_sha256='sha256:' + hashlib.sha256(args.probe.read_bytes()).hexdigest(),
    owner_accepted=False, full_0_1_0_complete=False)
args.output.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(summary, separators=(',', ':')))
