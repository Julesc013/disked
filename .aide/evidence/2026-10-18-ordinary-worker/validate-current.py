"""Bounded host metadata/tooling checks; no DiskEd or guest test execution."""
import ast
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
record=dict(status='running',scope=__doc__,commands=[])
commands=[['-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-deps','--only-binary=:all:','--target',str(deps),'PyYAML==6.0.3'],
    ['spec/tools/specctl.py','index'],['spec/tools/specctl.py','manifest'],['spec/tools/specctl.py','check'],
    ['-m','unittest','discover','-s','spec/tools/tests','-v'],['-m','unittest','discover','-s','tests/tools','-v'],
    ['tools/check-source-map.py'],['spec/tools/specctl.py','verify-manifest'],
    [str(HERE/'campaign.py'),'--native-x64','--prepare-only']]
if '--metadata-only' in sys.argv:
    commands=[command for command in commands if command[:2]!=['-m','unittest']]
    record['scope']='Metadata/AST/generated/source-map/manifest only; no native or full test-suite rerun'
if '--tools-only' in sys.argv:
    commands=[command for command in commands if 'spec/tools/tests' not in command]
    record['scope']='Tooling tests plus metadata/AST/generated/source-map/manifest; unchanged specification-test receipt retained separately'
try:
    for path in HERE.glob('*.py'):ast.parse(path.read_bytes(),filename=path.name)
    for args in commands:
        command=[sys.executable,'-B',*args];started=time.monotonic()
        try:
            outcome=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=900)
        except subprocess.TimeoutExpired as error:
            record['commands'].append(dict(arguments=command,exit_code=None,status='coordinator_timeout',seconds=time.monotonic()-started,
                stdout=(error.stdout or b'')[-131072:].decode(errors='replace'),stderr=(error.stderr or b'')[-131072:].decode(errors='replace')))
            raise
        if len(outcome.stdout)+len(outcome.stderr)>262144:raise ValueError('Metadata log bound')
        record['commands'].append(dict(arguments=command,exit_code=outcome.returncode,seconds=time.monotonic()-started,
            stdout=outcome.stdout.decode(errors='replace'),stderr=outcome.stderr.decode(errors='replace')))
        if outcome.returncode:raise RuntimeError('Metadata check failed')
    record['status']='pass'
except BaseException as error:
    record.update(status='fail',error=repr(error));raise
finally:(HERE/('final-validation.json' if '--full-qualification' in sys.argv else 'tooling-refresh.json' if '--tools-only' in sys.argv else 'metadata-refresh.json' if '--metadata-only' in sys.argv else 'current-validation.json')).write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
