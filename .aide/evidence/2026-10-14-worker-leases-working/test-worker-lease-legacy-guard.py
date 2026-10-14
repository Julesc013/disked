import ctypes as C
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
root=Path.cwd()
sys.path.insert(0,str(root/'tests/resilience'));sys.path.insert(0,str(root/'tests/images'))
from memory_fixture import Job,K,Limits,sid,checked,limits,MIB
from test_fat_auxiliary import MetadataVolume
host=hashlib.sha256((sid()+'\n'+os.environ['COMPUTERNAME']).encode()).hexdigest()
with Job(128*MIB,'Local\\DiskEd.Fake.Workers.v1.'+host) as legacy:
    value=Limits();value.basic.flags=0x308;value.basic.active_limit=4;value.process_memory=128*MIB;value.job_memory=512*MIB
    checked(K.SetInformationJobObject(legacy.handle,9,C.byref(value),C.sizeof(value)))
    before=limits(legacy.handle)
    with tempfile.TemporaryDirectory(prefix='worker-legacy-guard-') as directory:
        path=Path(directory)/'generated.img';volume=MetadataVolume(12);volume.write(path)
        source_before=hashlib.sha256(path.read_bytes()).hexdigest()
        process=subprocess.run([str(root/'.aide-local/exfat-command-launch-diagnostic/build/Release/disked.exe'),
            '--json','image','inspect',str(path),'--view','fat','--volume-offset','0','--volume-bytes',str(volume.length)],
            capture_output=True,timeout=10)
        response=json.loads(process.stdout)
        assert process.returncode==3 and not process.stderr and response['diagnostics'][0]['code']=='operation_worker_budget_mismatch',response
        assert limits(legacy.handle)==before
        assert hashlib.sha256(path.read_bytes()).hexdigest()==source_before
        for index in range(4):
            handle=K.OpenJobObjectW(4,False,'Local\\DiskEd.Fake.Workers.v2.'+host+'.'+str(index))
            assert not handle,'new worker slot appeared while legacy budget was retained'
result=dict(passed=True,response=response,legacy_limits=before,source_preserved=True)
(root/'.aide-local/worker-lease-legacy-guard.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
print('Existing legacy budget remains unchanged; new admission refuses before any slot/process creation')
