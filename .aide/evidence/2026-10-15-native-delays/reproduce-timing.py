"""Bounded generated-fixture diagnostic, not qualification or a changed test deadline."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--normal', type=Path, required=True)
parser.add_argument('--fault', type=Path, required=True)
parser.add_argument('--request', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
args.output.mkdir(exist_ok=False)
root = Path.cwd()
sys.path.insert(0, str(root / 'tests/images'))
from test_fat_content import fixture
from test_acquisition_worker import map_check

def canonical(v):
    return json.dumps(v, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()

def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1048576), b''):
            h.update(block)
    return 'sha256:' + h.hexdigest()

def save(name, v):
    (args.output / name).write_bytes(json.dumps(v, indent=2).encode() + b'\n')

request = json.loads(args.request.read_bytes())['definition']['request']
source = Path(request['source'])
source_hash = sha(source)
_, expected = fixture(16, unit=512, per=128, chain=tuple(range(3, 263)))
assert len(expected) == int(request['logical_source']['expected_file_bytes']) == 17039341
env = {k: v for k, v in os.environ.items() if not k.startswith('DISKED_')}
commands = []

def run(name, executable, row, extra):
    raw = canonical(row)
    (args.output / (name + '-input.json')).write_bytes(raw)
    started = time.monotonic()
    with (args.output / (name + '-stdout.jsonl')).open('wb') as stdout, \
            (args.output / (name + '-stderr.log')).open('wb') as stderr:
        p = subprocess.Popen([str(executable.resolve())], stdin=subprocess.PIPE,
            stdout=stdout, stderr=stderr, env=dict(env, **extra))
        terminated = False
        try:
            p.communicate(raw, timeout=300)
        except subprocess.TimeoutExpired:
            terminated = True
            p.kill()
            p.communicate(timeout=10)
    commands.append(dict(name=name, command=[str(executable.resolve())], pid=p.pid,
        input=name + '-input.json', env=extra, exit_code=p.returncode,
        elapsed_seconds=round(time.monotonic() - started, 3), diagnostic_ceiling_seconds=300,
        terminated_on_ceiling=terminated, actual_child_exit_confirmed=p.returncode is not None))
    save('commands.json', commands)
    assert not terminated and p.returncode == 0
    assert not (args.output / (name + '-stderr.log')).read_bytes()
    rows = [json.loads(line) for line in (args.output / (name + '-stdout.jsonl')).read_bytes().splitlines()]
    assert sha(source) == source_hash
    return rows

options = dict(chunk_bytes='65536', retry_limit='0', read_policy='ordinary', substitution='stop')
row = dict(source=str(source), destination=str((args.output / 'content.bin').resolve()),
    map=str((args.output / 'content.map').resolve()), mode='start', options=options,
    logical_source=request['logical_source'])
seed = run('seed-paused-prefix', args.fault, row, {'DISKED_ACQ_TEST_STOP_AFTER': '589824'})
assert len(seed) == 1 and seed[-1]['outcome']['status'] == 'paused'
assert (args.output / 'content.bin').read_bytes() == expected[:589824]
row['mode'] = 'resume'
rows = run('timed-resume', args.fault, row, {'DISKED_ACQ_TEST_TIMING': '1'})
result, frames = rows[-1], rows[:-1]
assert result['outcome']['status'] == 'completed'
assert (args.output / 'content.bin').read_bytes() == expected
map_check(args.output / 'content.map', expected)
assert frames and len(frames) < 16384
assert all(f['schema'] == 'org.disked.acquisition-test-timing/1' and
    f['sequence'] == str(n + 1) and f['cpu_observed'] for n, f in enumerate(frames))
spans = {}
for start, end, label in [('logical-metadata-start', 'logical-metadata-end', 'metadata'),
                          ('logical-content-start', 'logical-content-end', 'content'),
                          ('map-flush-start', 'map-flushed', 'map_flush'),
                          ('destination-flush-start', 'destination-flushed', 'destination_flush'),
                          ('observe-start', 'observe-end', 'bindings')]:
    pending = None
    values = []
    for f in frames:
        if f['phase'] == start:
            assert pending is None
            pending = f
        elif f['phase'] == end:
            assert pending is not None
            values.append(dict(wall_ms=int(f['ticks_ms']) - int(pending['ticks_ms']),
                cpu_100ns=int(f['kernel_100ns']) + int(f['user_100ns']) -
                    int(pending['kernel_100ns']) - int(pending['user_100ns'])))
            pending = None
    assert pending is None and values, label
    spans[label] = dict(count=len(values), wall_ms=sum(v['wall_ms'] for v in values),
        cpu_seconds=round(sum(v['cpu_100ns'] for v in values) / 1e7, 6),
        max_wall_ms=max(v['wall_ms'] for v in values))
# A normal preparation must ignore the test timing environment and create no outputs.
normal_row = dict(row, mode='prepare', destination=str((args.output / 'never.bin').resolve()),
    map=str((args.output / 'never.map').resolve()))
normal = run('normal-ignores-test-control', args.normal, normal_row, {'DISKED_ACQ_TEST_TIMING': '1'})
assert len(normal) == 1 and 'plan' in normal[0]
assert not (args.output / 'never.bin').exists() and not (args.output / 'never.map').exists()
save('summary.json', dict(status='diagnostic-measured', qualification=False, deadline_changed=False,
    source_sha256=source_hash, fixture_request_sha256=sha(args.request),
    artifact_sha256={str(p): sha(p) for p in [args.normal, args.fault]},
    logical_bytes=len(expected), logical_sha256='sha256:' + hashlib.sha256(expected).hexdigest(),
    output_sha256=sha(args.output / 'content.bin'), timing_frames=len(frames), spans=spans,
    source_preserved=True, independent_content_and_map_verified=True,
    owner_accepted=False, original_failed_campaign_unresolved=True))
print(json.dumps(spans, indent=2), flush=True)
