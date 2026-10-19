"""Bounded coordinator-only tests; no product, compiler or virtual media."""
import ast
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
record=dict(status='running',scope='Host coordinator tooling/recovery harness only; native fixture behavior unverified',commands=[])
try:
    migration=json.loads((HERE/'migration.json').read_bytes())
    for row in migration['changes']:
        data=(ROOT/row['path']).read_bytes();ast.parse(data)
        assert hashlib.sha256(data).hexdigest()==row['after_sha256']
    deps=Path(os.environ['DISKED_WORK_ROOT'])/'dependencies'
    env=dict(os.environ,PYTHONPATH=str(deps)+os.pathsep+str(ROOT/'spec/tools/tests'),PYTHONDONTWRITEBYTECODE='1')
    commands=[[sys.executable,'-B','-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-deps','--only-binary=:all:','--target',str(deps),'PyYAML==6.0.3'],
              [sys.executable,'-B','-m','unittest','discover','-s','tests/tools','-v'],
              [sys.executable,'-B','-m','unittest','discover','-s','tests/recovery','-p','test_gpt_fixture_harness.py','-v'],
              [sys.executable,'-B','-m','unittest','discover','-s','tests/artifacts','-p','test_artifact_check.py','-v'],
              [sys.executable,'-B','-m','unittest','test_specctl.BundleTests','-v'],
              [sys.executable,'-B','spec/tools/specctl.py','index'],
              [sys.executable,'-B','spec/tools/specctl.py','check'],
              [sys.executable,'-B','spec/tools/specctl.py','manifest'],
              [sys.executable,'-B','spec/tools/specctl.py','verify-manifest']]
    for index,command in enumerate(commands):
        started=time.monotonic()
        result=subprocess.run(command,cwd=ROOT,env=os.environ if index==0 else env,capture_output=True,timeout=600)
        assert len(result.stdout)+len(result.stderr)<=262144
        record['commands'].append(dict(arguments=command,exit_code=result.returncode,seconds=time.monotonic()-started,
            stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
        assert result.returncode==0
    record['status']='pass'
finally:
    (HERE/'fixture-checks.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
