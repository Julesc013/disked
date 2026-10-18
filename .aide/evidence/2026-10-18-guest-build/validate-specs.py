"""Refresh dependency projections and run the complete specification-tool suite."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
deps = Path(os.environ['DISKED_WORK_ROOT'])/'dependencies'
environment = dict(os.environ,PYTHONPATH=str(deps),PYTHONDONTWRITEBYTECODE='1')
commands = [[sys.executable,'-B','-m','pip','install','--disable-pip-version-check','--no-cache-dir',
             '--no-deps','--only-binary=:all:','--target',str(deps),'PyYAML==6.0.3'],
            [sys.executable,'-B','spec/tools/specctl.py','index'],
            [sys.executable,'-B','spec/tools/specctl.py','check'],
            [sys.executable,'-B','-m','unittest','discover','-s','spec/tools/tests','-v'],
            [sys.executable,'-B','spec/tools/specctl.py','manifest'],
            [sys.executable,'-B','spec/tools/specctl.py','verify-manifest']]
record = dict(status='running',commands=[])
def save():
    (HERE/'specification-checks.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
try:
    for index,command in enumerate(commands):
        started = time.monotonic()
        try:
            result = subprocess.run(command,cwd=ROOT,env=os.environ if index==0 else environment,
                                    capture_output=True,timeout=900 if index==3 else 300)
        except subprocess.TimeoutExpired as error:
            record['commands'].append(dict(arguments=command,exit_code=None,timed_out=True,
                seconds=time.monotonic()-started,stdout=(error.stdout or b'')[-131072:].decode(errors='replace'),
                stderr=(error.stderr or b'')[-131072:].decode(errors='replace')))
            raise
        if len(result.stdout)+len(result.stderr)>262144:
            record['commands'].append(dict(arguments=command,exit_code=result.returncode,log_limit_exceeded=True,
                stdout=result.stdout[-131072:].decode(errors='replace'),stderr=result.stderr[-131072:].decode(errors='replace')))
            raise RuntimeError('Specification check log exceeds retention bound')
        record['commands'].append(dict(arguments=command,exit_code=result.returncode,
            seconds=time.monotonic()-started,stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
        save()
        if result.returncode:
            raise RuntimeError('Specification validation failed')
    record['status']='pass'
except BaseException as error:
    record.update(status='fail',error=str(error))
    raise
finally:
    save()
