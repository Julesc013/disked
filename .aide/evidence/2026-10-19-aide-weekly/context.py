"""Verify complete source-bound contexts in disposable managed storage."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
work=Path(os.environ['DISKED_WORK_ROOT'])
deps=work/'dependencies'
env=dict(os.environ,PYTHONPATH=str(deps),PYTHONDONTWRITEBYTECODE='1')
record=dict(status='running',source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),commands=[],contexts=[])

def run(command):
    result=subprocess.run(command,cwd=ROOT,env=env,capture_output=True,timeout=180)
    assert len(result.stdout)+len(result.stderr)<=32768
    record['commands'].append(dict(arguments=list(map(str,command)),exit_code=result.returncode,
        stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
    assert result.returncode==0

try:
    run([sys.executable,'-B','-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-deps','--only-binary=:all:','--target',str(deps),'PyYAML==6.0.3'])
    for work_id in ('DE-W105','DE-W061'):
        target=work/work_id
        run([sys.executable,'-B','spec/tools/specctl.py','context','--work',work_id,'--output',str(target),'--byte-budget','2097152','--artifact-byte-budget','25165824'])
        run([sys.executable,'-B','spec/tools/specctl.py','verify-context',str(target)])
        record['contexts'].append(dict(work_id=work_id,manifest_sha256=hashlib.sha256((target/'manifest.json').read_bytes()).hexdigest(),
            bytes=sum(p.stat().st_size for p in target.rglob('*') if p.is_file()),scope='Declared input closure only; no execution authority or live consumer admission'))
    record['status']='pass'
finally:
    (HERE/'context.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
