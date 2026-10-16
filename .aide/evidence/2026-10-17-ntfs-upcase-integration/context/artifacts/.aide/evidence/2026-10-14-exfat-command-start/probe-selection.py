"""Independent native observations used to define automatic selection, not implement it."""
import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path

root = Path.cwd()
sys.path.insert(0, str(root / 'tests/property'))
from test_exfat_upcase import mapping, literal, compress, request, decode, checksum

parser = argparse.ArgumentParser()
parser.add_argument('--probe', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()

base = mapping()
ambiguous = base.copy()
ambiguous[128:130] = [65535, 2]
equivalent = base.copy()
equivalent[65535] = 65534
literal_only = base.copy()
literal_only[128:130] = [65535, 0]
bad_ascii = base.copy()
bad_ascii[97] = 97
cases = [
    ('compressed-standard', compress(base), 'compressed'),
    ('literal-standard', literal(base), 'equivalent'),
    ('literal-only-custom', literal(literal_only), 'literal'),
    ('different-valid-maps', literal(ambiguous), 'ambiguous'),
    ('same-valid-map', literal(equivalent), 'equivalent'),
    ('invalid-mandatory-ascii', literal(bad_ascii), 'invalid'),
]
inputs = []
for _, raw, _ in cases:
    inputs.extend([request(raw, compressed=0), request(raw, compressed=1)])
result = subprocess.run([str(args.probe.resolve())], input=json.dumps(inputs).encode(),
                        capture_output=True, timeout=30)
assert result.returncode == 0 and not result.stderr
outputs = json.loads(result.stdout)
assert len(outputs) == 2 * len(cases)
facts = []
for index, (name, raw, expected) in enumerate(cases):
    candidates = []
    for offset, format_name in enumerate(['literal', 'compressed']):
        actual = outputs[index * 2 + offset]
        units, issues = decode(raw, bool(offset))
        actual_valid = actual.get('valid', False)
        assert actual_valid == (issues == 0), (name, format_name, actual, issues)
        oracle_digest = 'sha256:' + hashlib.sha256(literal(units)).hexdigest() if not issues else None
        if oracle_digest:
            assert actual['map_sha256'] == oracle_digest
        candidates.append(dict(format=format_name, valid=actual_valid, native=actual,
                               oracle_issues=issues, oracle_mapping_sha256=oracle_digest))
    valid = [c for c in candidates if c['valid']]
    selected = ('invalid' if not valid else valid[0]['format'] if len(valid) == 1 else
                'equivalent' if valid[0]['oracle_mapping_sha256'] == valid[1]['oracle_mapping_sha256']
                else 'ambiguous')
    assert selected == expected, (name, expected, selected)
    facts.append(dict(name=name, bytes=len(raw), checksum=checksum(raw),
                      bytes_sha256='sha256:' + hashlib.sha256(raw).hexdigest(),
                      derived_selection=selected, candidates=candidates))
revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
unchanged = subprocess.check_output(['git', 'diff', 'e43f00fb494cd12727fc52fcf82cb040a85cde2c',
                                    revision, '--', 'source/portable/exfat',
                                    'tests/property/test_exfat_upcase.py',
                                    'tests/unit/exfat_upcase_probe.cpp'])
assert not unchanged
report = dict(status='pass', source_revision=revision, probe=str(args.probe.resolve()),
              probe_sha256='sha256:' + hashlib.sha256(args.probe.read_bytes()).hexdigest(),
              portable_and_oracle_unchanged_from='e43f00fb494cd12727fc52fcf82cb040a85cde2c',
              native_inputs=len(inputs), scenarios=len(cases), cases=facts,
              scope='Both existing explicit decoders and independent complete-map oracles; '
                    'derived expected automatic selection, no implemented auto/frontends claim.',
              source='https://learn.microsoft.com/en-us/windows/win32/fileio/exfat-specification')
args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8', newline='\n')
print(f'{len(cases)} independently derived selection scenarios; {len(inputs)} native decoder inputs pass')
