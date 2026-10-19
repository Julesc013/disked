"""Bounded coordinator checks; preserve child failure output before cleanup."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
deps=Path(os.environ['DISKED_WORK_ROOT'])/'dependencies'
env=dict(os.environ,PYTHONPATH=str(deps),PYTHONDONTWRITEBYTECODE='1')
record=dict(status='running',scope='Coordinator/tooling and template checks,not product or crypto-device admission',prior_full_suite_attempt=dict(exit_code=3221225786,summary_produced=False,cause='unresolved interruption'),commands=[])
commands=[[sys.executable,'-B','-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-deps','--only-binary=:all:','--target',str(deps),'PyYAML==6.0.3'],
    [sys.executable,'-B','-m','unittest','discover','-s','tests/tools','-v'],
    [sys.executable,'-B',str(HERE/'campaign.py'),'--crypto-device','--prepare-only']]
try:
    for command in commands:
        started=time.monotonic();result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=300)
        if len(result.stdout)+len(result.stderr)>262144:raise ValueError('Validation log bound')
        record['commands'].append(dict(command=command,exit_code=result.returncode,seconds=time.monotonic()-started,stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
        if result.returncode:raise RuntimeError('Validation command failed')
    record['status']='pass'
finally:
    (HERE/'crypto-tooling-validation.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
