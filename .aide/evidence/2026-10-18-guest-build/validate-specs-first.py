"""Refresh dependency projections and run the complete specification-tool suite."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

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
try:
    for index,command in enumerate(commands):
        result = subprocess.run(command,cwd=ROOT,env=os.environ if index==0 else environment,
                                capture_output=True,timeout=300)
        if len(result.stdout)+len(result.stderr)>262144:
            raise RuntimeError('Specification check log exceeds retention bound')
        record['commands'].append(dict(arguments=command,exit_code=result.returncode,
            stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
        if result.returncode:
            raise RuntimeError('Specification validation failed')
    record['status']='pass'
finally:
    (HERE/'specification-checks.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
