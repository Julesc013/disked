"""Six bounded read-only samples on the retained fixture; no qualification/retry-to-pass."""
import ctypes as C
from ctypes import wintypes as W
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time

root = Path.cwd()
campaign = root / '.aide-local/exfat-tree-file-exact-11e6f625'
fixture = campaign / 'source/.aide-local/disked-acq-worker-_zqxk64f'
out = root / '.aide-local/joined-prepare-profile-11e6f625'
out.mkdir(exist_ok=False)
product = campaign / 'build/Release/disked.exe'
request = json.loads((fixture / 'case/acquisition.request').read_bytes())
collection = fixture / 'verification/verification.collection'
destination, state = fixture / 'cli/support.json', fixture / 'cli/state'
assert not destination.exists() and not list(state.iterdir())
inputs = [fixture / 'case/acquisition.request', fixture / 'case/acquisition.records', collection]
def sha(p):
    return 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()
hashes = {str(p): sha(p) for p in inputs}
command = [str(product), '--json', 'evidence', 'export', 'prepare', request['operation_id'],
    str(destination), '--case-state-dir', str(fixture / 'case'), '--state-dir', str(state),
    '--collection', str(collection), '--collection-digest', hashes[str(collection)]]
env = {k:v for k,v in os.environ.items() if not k.startswith('DISKED_')}
k = C.WinDLL('kernel32', use_last_error=True)
k.GetProcessTimes.argtypes = [W.HANDLE] + [C.POINTER(W.FILETIME)] * 4
k.GetProcessTimes.restype = W.BOOL
class IO(C.Structure):
    _fields_ = [(n, C.c_ulonglong) for n in ['read_operations', 'write_operations',
        'other_operations', 'read_bytes', 'written_bytes', 'other_bytes']]
k.GetProcessIoCounters.argtypes = [W.HANDLE, C.POINTER(IO)]
k.GetProcessIoCounters.restype = W.BOOL
def ticks(t):
    return t.dwLowDateTime + (t.dwHighDateTime << 32)
samples = []
for n in range(6):
    started = time.monotonic()
    with (out / (str(n) + '-stdout.json')).open('wb') as stdout, \
            (out / (str(n) + '-stderr.log')).open('wb') as stderr:
        p = subprocess.Popen(command, stdout=stdout, stderr=stderr, cwd=campaign / 'source', env=env)
        terminated = False
        try:
            p.wait(timeout=15)
        except subprocess.TimeoutExpired:
            terminated = True
            p.kill()
            p.wait(timeout=10)
    cpu = [W.FILETIME() for _ in range(4)]
    measured = bool(k.GetProcessTimes(W.HANDLE(int(p._handle)), *(C.byref(v) for v in cpu)))
    io = IO()
    io_measured = bool(k.GetProcessIoCounters(W.HANDLE(int(p._handle)), C.byref(io)))
    raw = (out / (str(n) + '-stdout.json')).read_bytes()
    response = json.loads(raw) if raw else {}
    assert not destination.exists() and not list(state.iterdir())
    assert all(sha(path) == digest for path, digest in ((Path(s), d) for s,d in hashes.items()))
    samples.append(dict(sample=n, pid=p.pid, exit_code=p.returncode,
        elapsed_seconds=round(time.monotonic() - started, 6), terminated_on_ceiling=terminated,
        actual_child_exit_confirmed=p.returncode is not None,
        response_status=response.get('status'), diagnostics=response.get('diagnostics'),
        cpu_observed=measured, cpu_seconds=(ticks(cpu[2]) + ticks(cpu[3])) / 1e7 if measured else None,
        io_observed=io_measured, io={name:getattr(io,name) for name,_ in io._fields_} if io_measured else None,
        source_preserved=True, no_effects=True, stdout_sha256=sha(out / (str(n) + '-stdout.json'))))
    (out / 'summary.json').write_bytes(json.dumps(dict(command=command, source_revision='11e6f6258a966b716a58a3336ff07aea8bf60e70',
        artifact_sha256=sha(product), inputs=hashes, input_sizes={s:Path(s).stat().st_size for s in hashes},
        samples=samples, sample_limit=6, diagnostic_ceiling_seconds=15,
        qualification=False, original_campaign_unresolved=True), indent=2).encode() + b'\n')
    print(json.dumps(samples[-1]), flush=True)
