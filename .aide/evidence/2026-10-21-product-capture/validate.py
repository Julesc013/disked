"""Bounded source-export/contract checks with retained command outcomes."""
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
full='--full' in sys.argv
finalize='--finalize' in sys.argv
record=dict(status='running',base_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),commands=[])
commands=[['-m','unittest','discover','-s','tests/tools','-p','test_source_snapshot.py','-v']]
env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1')
if full or finalize:
    env['PYTHONPATH']=str(work/'dependencies')
    commands=[['-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-deps','--only-binary=:all:','--target',env['PYTHONPATH'],'PyYAML==6.0.3'],
              ['spec/tools/specctl.py','index'],['spec/tools/specctl.py','manifest'],['spec/tools/specctl.py','check'],
              ['tools/check-source-map.py'],['-m','unittest','discover','-s','spec/tools/tests','-v'],
              ['-m','unittest','discover','-s','tests/tools','-v'],['-m','unittest','discover','-s','tests/differential','-v'],
              ['spec/tools/specctl.py','verify-manifest']]
    if finalize:commands=[c for c in commands if not ('spec/tools/tests' in c or 'tests/differential' in c)]
for path in [HERE/'cooperative.py',ROOT/'spec/tools/input_graph.py',ROOT/'tools/source-snapshot.py',ROOT/'tests/frontend/gui_fixture.py',ROOT/'tests/frontend/test_gui_capture.py',ROOT/'tests/support/window_capture.py',ROOT/'.aide/evidence/2026-10-18-ordinary-worker/campaign.py',ROOT/'.aide/evidence/2026-10-18-ordinary-worker/full-native.py']:
    ast.parse(path.read_bytes())
record['syntax_checks']=8
def retain():
    body=(json.dumps(record,indent=2)+'\n').encode();assert len(body)<4194304
    encoded=lzma.compress(body,format=lzma.FORMAT_XZ,filters=[dict(id=lzma.FILTER_LZMA2,dict_size=1048576,preset=6)])
    assert lzma.decompress(encoded)==body
    (HERE/('finalization.json.xz' if finalize else 'validation.json.xz' if full else 'focused-validation.json.xz')).write_bytes(encoded)
try:
    for arguments in commands:
        call=subprocess.run([sys.executable,'-B',*arguments],cwd=ROOT,env=env,capture_output=True,timeout=900)
        assert len(call.stdout)+len(call.stderr)<=262144
        record['commands'].append(dict(arguments=call.args,exit_code=call.returncode,stdout=call.stdout.decode(errors='replace'),stderr=call.stderr.decode(errors='replace')));retain()
        if call.returncode:raise RuntimeError('Validation command failed: '+str(arguments))
    record['status']='pass';retain()
except BaseException:
    record['status']='fail';retain();raise
