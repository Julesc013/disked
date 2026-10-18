"""Recheck three pure comparator gaps without generating images or native work."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
assert Path(os.environ['DISKED_WORK_ROOT']).is_dir()
path = ROOT/'tests/differential/compare.py'
module_spec = importlib.util.spec_from_file_location('reference_comparator', path)
module = importlib.util.module_from_spec(module_spec)
module_spec.loader.exec_module(module)
fixture_hash = 'sha256:'+'1'*64
rows = [dict(slot=1, start=34, end=61)]
manifest = dict(cases=[dict(name='control', common_projection=True,
                          sha256=fixture_hash, bytes=65536, unit=512, blocks=128)])
native = dict(observations=[dict(name='control', sha256=fixture_hash,
    projection=dict(label='gpt', candidates=[dict(role='primary', rows=rows)]))])
external = dict(name='control', kind='sfdisk-json', sha256=fixture_hash,
    outcome='exited', exit_code=0, stdout='synthetic', stderr='',
    projection=dict(label='gpt', rows=rows, fields=['slot', 'start', 'end']))
wrong = copy.deepcopy(external)
wrong['sha256'] = 'sha256:'+'2'*64
results = []
for name, items in [('missing', []), ('mismatched_hash', [wrong]),
                    ('duplicate', [external, copy.deepcopy(external)])]:
    value = module.compare(manifest, native, dict(reference=dict(observations=items)))
    results.append(dict(probe=name, adapter_controls_passed=value['adapter_controls_passed'],
                        comparisons=len(value['comparisons'])))
assert [x['adapter_controls_passed'] for x in results] == [True, True, True]
assert [x['comparisons'] for x in results] == [0, 1, 2]
record = dict(status='gaps_reproduced', source_revision=subprocess.check_output(
    ['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    comparator_sha256='sha256:'+hashlib.sha256(path.read_bytes()).hexdigest(),
    recipe_sha256='sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
    observations=results,
    scope='Synthetic pure-function evidence-boundary probes only. No Windows reference application, product executable, REA, image, WSL or historical campaign run. Not evidence that historical retained results were invalid.',
    follow_up='DE-W106 planned; comparator and coordinator are not repaired by this planning change.')
(HERE/'review.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(record))
