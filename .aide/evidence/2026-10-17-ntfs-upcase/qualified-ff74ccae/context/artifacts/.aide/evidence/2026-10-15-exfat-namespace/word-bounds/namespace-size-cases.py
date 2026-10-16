"""Independent decimal-boundary invocations for exact x64/x86 probe binaries."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import sys

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--probe', type=Path, required=True)
parser.add_argument('--pointer-bits', type=int, choices=[32, 64], required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--observe-baseline', action='store_true')
args = parser.parse_args()
sys.path.insert(0, str(args.source / 'tests/property'))
from exfat_directory_vectors import file_set, seal
from test_exfat_upcase import mapping, compress, checksum, namehash
import struct

table = mapping()
encoded = compress(table)
raw = file_set([65])
struct.pack_into('<H', raw, 36, namehash(table, [65]))
raw = bytes(seal(raw)) + bytes(32)
baseline = dict(table=encoded.hex(), checksum=str(checksum(encoded)), format='auto',
    directories=[dict(id='0', root=True, complete=True, records=[
        dict(offset=str(1000 + i), bytes=raw[i:i+32].hex()) for i in range(0, len(raw), 32)])],
    queries=[dict(directory='0', units=['65'])])
rows, expectations = [], []
def case(change, expect):
    row = copy.deepcopy(baseline)
    change(row)
    rows.append(row)
    expectations.append(expect)
for key, low in [('records', 1), ('directories', 1), ('queries', 1),
                 ('comparisons', 1), ('findings', 1), ('output_bytes', 16384)]:
    case(lambda row, key=key, low=low: row.update(limits={key: str((1 << 32) + low)}), 'error')
case(lambda row: row.update(map_budget=str((1 << 32) + 786432)), 'error')
for value in [(1 << 32), (1 << 32) + 1, (1 << 64) - 1]:
    def identify(row, value=value):
        row['directories'][0]['id'] = str(value)
        row['queries'][0]['directory'] = str(value)
    case(identify, 'unique' if args.pointer_bits == 64 else 'error')
case(lambda row: row['queries'][0].update(directory=str(1 << 32)),
    'directory_not_observed' if args.pointer_bits == 64 else 'error')
case(lambda row: row['directories'][0].update(id=str(1 << 64)), 'error')
case(lambda row: row.update(map_budget='18446744073709551616'), 'error')
data = b''.join((json.dumps(row, separators=(',', ':')) + '\n').encode() for row in rows)
before = hashlib.sha256(data).hexdigest()
result = subprocess.run([str(args.probe.resolve())], input=data, capture_output=True, timeout=90)
assert result.returncode == 0 and not result.stderr, (result.returncode, result.stderr)
values = [json.loads(row) for row in result.stdout.splitlines()]
assert len(values) == len(rows)
differences = []
for index, (row, value, expected) in enumerate(zip(rows, values, expectations)):
    if expected == 'error':
        if 'error' not in value:
            differences.append(dict(case=index, expected='error', actual=value['result']['queries'][0]['status']))
    else:
        if 'error' in value or value['result']['queries'][0]['status'] != expected:
            differences.append(dict(case=index, expected=expected, actual=value.get('error', value.get('result', {}).get('queries'))))
        else:
            assert value['result']['queries'][0]['directory_id'] == row['queries'][0]['directory']
    if 'result' in value:
        assert not value['result']['authorizes_effects']
        assert not value['result']['physical_admission']
summary = dict(passed=not differences, cases=len(rows), pointer_bits=args.pointer_bits,
    input_sha256=before, output_sha256=hashlib.sha256(result.stdout).hexdigest(),
    binary_sha256='sha256:' + hashlib.sha256(args.probe.read_bytes()).hexdigest(),
    expected=expectations, differences=differences, baseline_observation=args.observe_baseline)
args.output.write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8', newline='\n')
print(json.dumps(summary, separators=(',', ':')))
if differences and not args.observe_baseline:
    raise SystemExit(1)
