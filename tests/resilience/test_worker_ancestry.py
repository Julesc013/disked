"""Actual read-only product requests under independent inherited caller jobs."""
import argparse
import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import time
from memory_fixture import Job, AssignedProcess, MIB, K, sid, limits, Limits, checked
import subprocess

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / 'tests/images'))
from test_fat_auxiliary import MetadataVolume

parser = argparse.ArgumentParser()
for name in ['exe', 'fault', 'output']:
    parser.add_argument('--' + name, type=Path, required=True)
args = parser.parse_args()
args.exe, args.fault = args.exe.resolve(), args.fault.resolve()
env = {key: value for key, value in os.environ.items() if not key.startswith('DISKED_')}
host = hashlib.sha256((sid() + '\n' + os.environ['COMPUTERNAME']).encode()).hexdigest()
result = dict(passed=False, cases=0)
try:
    with tempfile.TemporaryDirectory(prefix='disked-independent-reader-') as directory:
        path = Path(directory) / 'generated.img'
        volume = MetadataVolume(12); volume.write(path)
        before = hashlib.sha256(path.read_bytes()).hexdigest()
        request = json.dumps(dict(schema='org.disked.request/1', request_id='independent', command='image.inspect',
            parameters=dict(path=str(path), view='fat', volume_offset=str(volume.offset), volume_bytes=str(volume.length)),
            required_features=[])).encode() + b'\n'
        with Job(512*MIB) as host_a, Job(512*MIB) as host_b:
            original_a, original_b = limits(host_a.handle), limits(host_b.handle)
            with AssignedProcess([args.fault, 'protocol', 'serve', '--format=ndjson'], host_a,
                dict(env, DISKED_FAT_COMMAND_TEST_HANG='1'), pipe_input=True) as first:
                first.send(request)
                deadline = time.monotonic() + 2; lease = None
                while not lease:
                    lease = K.OpenJobObjectW(4, False, 'DiskEd.Fake.Workers.v2.' + host + '.0')
                    if time.monotonic() > deadline: raise AssertionError('no first reader lease')
                    if not lease: time.sleep(.01)
                try:
                    with AssignedProcess([args.exe, '--json', 'image', 'inspect', path, '--view', 'fat',
                        '--volume-offset', str(volume.offset), '--volume-bytes', str(volume.length)], host_b, env) as second:
                        code, out, error = second.result(); reply = json.loads(out)
                        assert code == 0 and not error and reply['status'] == 'completed', reply
                        result['second'] = reply; result['cases'] += 1
                finally: K.CloseHandle(lease)
                first.close_input(); code, out, error = first.result(); reply = json.loads(out)
                assert code == 6 and not error and reply['status'] == 'unknown', reply
                result['first'] = reply; result['cases'] += 1
            for original, after in [(original_a, limits(host_a.handle)), (original_b, limits(host_b.handle))]:
                assert all(original[key] == after[key] for key in ['flags', 'process_bytes', 'job_bytes', 'active_limit'])
            result['hosts_preserved'] = True
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
        # A retained/prepared v1 budget is incompatible even without members;
        # refuse it without rewriting limits or admitting a new slot.
        # The unknown request's owned child may still be closing its lease.
        # Observe the namespace; elapsed frontend wait is not an exit claim.
        deadline=time.monotonic()+3
        while True:
            retained=K.OpenJobObjectW(4,False,'DiskEd.Fake.Workers.v1.'+host)
            if not retained:break
            K.CloseHandle(retained)
            if time.monotonic()>deadline:raise AssertionError('owned reader guard remains retained')
            time.sleep(.01)
        with Job(128*MIB, 'DiskEd.Fake.Workers.v1.' + host) as legacy:
            value=Limits();value.basic.flags=0x308;value.basic.active_limit=4
            value.process_memory=128*MIB;value.job_memory=512*MIB
            checked(K.SetInformationJobObject(legacy.handle,9,C.byref(value),C.sizeof(value)))
            original=limits(legacy.handle)
            process=subprocess.run([str(args.exe),'--json','image','inspect',str(path),'--view','fat',
                '--volume-offset',str(volume.offset),'--volume-bytes',str(volume.length)],capture_output=True,timeout=10,env=env)
            reply=json.loads(process.stdout)
            assert process.returncode==3 and not process.stderr and reply['diagnostics'][0]['code']=='operation_worker_budget_mismatch',reply
            assert limits(legacy.handle)==original
            result['legacy_conflict']=reply;result['cases']+=1
        assert hashlib.sha256(path.read_bytes()).hexdigest() == before
    result['passed'] = True
finally:
    args.output.write_text(json.dumps(result, indent=2) + '\n', encoding='utf-8', newline='\n')
print('Independent caller jobs: actual second reader completes, first stays unknown, host limits/source preserved')
