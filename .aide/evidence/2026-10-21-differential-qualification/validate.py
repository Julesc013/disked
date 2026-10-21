"""One managed host metadata/regression pass; no native product execution."""
import ast
import hashlib
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
work=Path(os.environ['DISKED_WORK_ROOT'])
record=dict(status='running',source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),commands=[])
env=dict(os.environ,PYTHONPATH=str(work/'dependencies'),PYTHONDONTWRITEBYTECODE='1')
commands=[['-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-compile','--no-deps',
           '--only-binary=:all:','--target',env['PYTHONPATH'],'PyYAML==6.0.3'],
          ['spec/tools/specctl.py','index'],['spec/tools/specctl.py','manifest'],['spec/tools/specctl.py','check'],
          ['tools/check-source-map.py'],['-m','unittest','discover','-s','spec/tools/tests','-v'],
          ['-m','unittest','discover','-s','tests/tools','-v'],
          ['-m','unittest','discover','-s','tests/differential','-v'],['spec/tools/specctl.py','verify-manifest']]
def inputs():
    paths=[]
    for root in ('spec','tests','tools'):
        paths.extend(p for p in (ROOT/root).rglob('*') if p.is_file() and p.suffix in ('.py','.cpp','.h','.json','.md','.yaml','.ps1'))
    paths.extend(HERE.glob('*.py'));paths.append(HERE/'expected.json')
    paths.extend(ROOT/'.aide/evidence/2026-10-18-ordinary-worker'/p for p in ('campaign.py','guest-proof.py'))
    return {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}
try:
    for p in [*HERE.glob('*.py'),ROOT/'.aide/evidence/2026-10-18-ordinary-worker/campaign.py',ROOT/'.aide/evidence/2026-10-18-ordinary-worker/guest-proof.py']:ast.parse(p.read_bytes())
    for args in commands:
        if args==['spec/tools/specctl.py','check']:record['tested_inputs']=inputs()
        value=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,env=env,capture_output=True,timeout=1200)
        assert len(value.stdout)+len(value.stderr)<=262144
        record['commands'].append(dict(argv=value.args,exit_code=value.returncode,stdout=value.stdout.decode(errors='replace'),stderr=value.stderr.decode(errors='replace')))
        print(json.dumps(dict(command=args,exit_code=value.returncode)),flush=True)
        if value.returncode:raise RuntimeError('Validation failed: '+str(args))
    record['inputs_unchanged']=record['tested_inputs']==inputs()
    assert record['inputs_unchanged']
    record['status']='pass'
except BaseException:
    record['status']='fail';raise
finally:
    raw=(json.dumps(record,indent=2)+'\n').encode();assert len(raw)<=4194304
    encoded=lzma.compress(raw,filters=[dict(id=lzma.FILTER_LZMA2,dict_size=1048576,preset=6)])
    assert lzma.decompress(encoded)==raw
    (HERE/'validation.json.xz').write_bytes(encoded)
