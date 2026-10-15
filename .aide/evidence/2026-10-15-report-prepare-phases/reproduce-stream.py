import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

root = Path.cwd()
build = root / '.aide-local/report-phases-build'
fixture = root / '.aide-local/exfat-tree-file-exact-11e6f625/source/.aide-local/disked-acq-worker-_zqxk64f'
out = root / '.aide-local/report-phase-stream-observations'
out.mkdir(exist_ok=False)
inputs = json.loads((root / '.aide-local/report-phases-observations-final/fault-standard-input.json').read_bytes())
names = [p+s for p in ['directory', 'identity', 'image', 'export_review', 'definition'] for s in ['_begin','_end']]
env = {k:v for k,v in os.environ.items() if not k.startswith('DISKED_')}
def sha(p):
    return 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()
sources = [fixture / 'case/acquisition.request', fixture / 'case/acquisition.records', fixture / 'verification/verification.collection']
hashes = {str(p):sha(p) for p in sources}
commands = []
def run(name, exe, row, ceiling=15, pause=False, refusal=False):
    raw = json.dumps(row, sort_keys=True, separators=(',', ':'), ensure_ascii=False).encode()
    (out / (name + '-input.json')).write_bytes(raw)
    start = time.monotonic()
    with (out / (name + '-stdout.jsonl')).open('wb') as stdout, (out / (name + '-stderr.log')).open('wb') as stderr:
        p = subprocess.Popen([str(exe)], stdin=subprocess.PIPE, stdout=stdout, stderr=stderr, env=env)
        terminated = False
        try:
            p.communicate(raw, timeout=ceiling)
        except subprocess.TimeoutExpired:
            terminated = True
            p.kill()
            p.communicate(timeout=10)
    commands.append(dict(name=name, command=[str(exe)], pid=p.pid, exit_code=p.returncode,
        elapsed_seconds=round(time.monotonic()-start,6), diagnostic_ceiling_seconds=ceiling,
        controlled_pause=pause, terminated=terminated, actual_child_exit_confirmed=p.returncode is not None))
    (out / 'commands.json').write_bytes(json.dumps(commands,indent=2).encode()+b'\n')
    assert not (out / (name + '-stderr.log')).read_bytes()
    assert terminated == pause
    assert p.returncode == 3 if refusal else p.returncode != 0 if pause else p.returncode == 0
    assert not Path(row['destination']).exists() and not list(Path(row['state_directory']).iterdir())
    assert all(sha(Path(s)) == h for s,h in hashes.items())
    return [json.loads(line) for line in (out / (name + '-stdout.jsonl')).read_bytes().splitlines()]
normal = build / 'Release/report_worker_probe.exe'
fault = build / 'Release/report_worker_fault.exe'
rows = run('joined-stream',fault,dict(inputs,mode='prepare-joined-trace-stream'))
assert len(rows)==11 and [p['phase'] for p in rows[:-1]]==names and rows[-1]['phase_trace']==rows[:-1]
unjoined = dict(inputs,mode='prepare-trace-stream')
unjoined.pop('collection_path');unjoined.pop('collection_digest')
rows = run('unjoined-stream',fault,unjoined)
assert len(rows)==11 and [p['phase'] for p in rows[:-1]]==names and rows[-1]['phase_trace']==rows[:-1]
rows = run('controlled-prefix',fault,dict(inputs,mode='prepare-joined-trace-stream-wait'),3,True)
assert len(rows)==5 and [p['phase'] for p in rows]==names[:5] and rows[-1]['phase']=='image_begin'
for n,row in enumerate([dict(inputs,mode='prepare-joined-trace-stream'),unjoined,
        dict(inputs,mode='prepare-joined-trace-stream-wait')]):
    rows = run('normal-refusal-'+str(n),normal,row,refusal=True)
    assert rows == [{'refusal':'probe_input'}]
(out / 'summary.json').write_bytes(json.dumps(dict(status='diagnostic-pass', qualification=False,
    source_preserved=True, no_effects=True, streamed_joined_and_unjoined=True,
    controlled_prefix_preserved=True, actual_exit_confirmed=True, original_timeout_reproduced=False,
    original_deadlines_changed=False, artifacts={str(p):sha(p) for p in [normal,fault]}, inputs=hashes),indent=2).encode()+b'\n')
print('Streaming joined/unjoined, controlled prefix/owned exit and normal refusals pass.',flush=True)
