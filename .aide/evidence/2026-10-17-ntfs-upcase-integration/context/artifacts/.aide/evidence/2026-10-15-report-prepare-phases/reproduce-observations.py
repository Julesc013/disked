import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

root = Path.cwd()
build = root / '.aide-local/report-phases-build'
fixture = root / '.aide-local/exfat-tree-file-exact-11e6f625/source/.aide-local/disked-acq-worker-_zqxk64f'
parser = argparse.ArgumentParser()
parser.add_argument('--output', type=Path, default=Path('.aide-local/report-phases-observations'))
args = parser.parse_args()
out = args.output.resolve()
out.mkdir(exist_ok=False)
header = fixture / 'case/acquisition.request'
history = fixture / 'case/acquisition.records'
collection = fixture / 'verification/verification.collection'
def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
inputs = {str(p):sha(p) for p in [header, history, collection]}
state, destination = fixture / 'cli/state', fixture / 'cli/support.json'
request = dict(mode='prepare-joined', operation_id=json.loads(header.read_bytes())['operation_id'],
    case_directory=str(header.parent), collection_path=str(collection), collection_digest=sha(collection),
    policy={k:False for k in ['identifiers', 'raw_values', 'interpretations', 'customer_data']},
    destination=str(destination), state_directory=str(state))
env = {k:v for k,v in os.environ.items() if not k.startswith('DISKED_')}
commands = []
def run(name, exe, row, expected=0):
    raw = json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    (out / (name + '-input.json')).write_bytes(raw)
    start = time.monotonic()
    p = subprocess.run([str(exe)], input=raw, capture_output=True, env=env, timeout=15)
    (out / (name + '-stdout.json')).write_bytes(p.stdout)
    (out / (name + '-stderr.log')).write_bytes(p.stderr)
    commands.append(dict(name=name, command=[str(exe)], exit_code=p.returncode,
        elapsed_seconds=round(time.monotonic() - start, 6), diagnostic_ceiling_seconds=15))
    (out / 'commands.json').write_bytes(json.dumps(commands, indent=2).encode() + b'\n')
    assert p.returncode == expected and not p.stderr, (name,p.returncode,p.stderr)
    assert not destination.exists() and not list(state.iterdir())
    assert all(sha(Path(s)) == digest for s,digest in inputs.items())
    return json.loads(p.stdout)
normal = build / 'Release/report_worker_probe.exe'
fault = build / 'Release/report_worker_fault.exe'
baseline = run('fault-standard', fault, request)
names = [part + suffix for part in ['directory', 'identity', 'image', 'export_review', 'definition']
    for suffix in ['_begin', '_end']]
summaries = []
for n in range(6):
    result = run('trace-' + str(n), fault, dict(request, mode='prepare-joined-trace'))
    phases = result.pop('phase_trace')
    assert result == baseline and [p['phase'] for p in phases] == names
    assert all(p['cpu_observed'] and p['io_observed'] for p in phases)
    spans = []
    for first,last in zip(phases[::2], phases[1::2]):
        spans.append(dict(phase=first['phase'][:-6], wall_ms=int(last['ticks_ms'])-int(first['ticks_ms']),
            cpu_100ns=int(last['kernel_100ns'])+int(last['user_100ns'])-int(first['kernel_100ns'])-int(first['user_100ns']),
            read_operations=int(last['read_operations'])-int(first['read_operations']),
            read_bytes=int(last['read_bytes'])-int(first['read_bytes']),
            other_operations=int(last['other_operations'])-int(first['other_operations'])))
    summaries.append(dict(sample=n, spans=spans))
mutated = run('caller-mutation', fault, dict(request, mode='prepare-joined-trace-mutate'))
assert mutated.pop('caller_mutation_attempted')
assert [p['phase'] for p in mutated.pop('phase_trace')] == names
assert mutated == baseline
for mode in ['prepare-joined-trace', 'prepare-joined-trace-mutate']:
    refused = run('normal-rejects-' + mode, normal, dict(request, mode=mode), 3)
    assert refused == {'refusal':'probe_input'}
run('normal-standard', normal, request)
assert b'prepare-joined-trace' not in normal.read_bytes()
(out / 'summary.json').write_bytes(json.dumps(dict(status='diagnostic-pass', qualification=False,
    source_base='89cd7b88691a661cc6d2da53e2af9b19a1f0d234', source_state='working',
    artifacts={str(p):sha(p) for p in [normal,fault]}, inputs=inputs,
    samples=summaries, original_selection_preserved=True, caller_mutation_refused=True,
    normal_trace_mode_unavailable=True, source_preserved=True, no_effects=True,
    original_deadlines_changed=False, timeout_cause_established=False), indent=2).encode() + b'\n')
print(json.dumps(summaries[0], indent=2), flush=True)
print('Six traces, mutation snapshot, normal refusals and inert preparation pass.', flush=True)
