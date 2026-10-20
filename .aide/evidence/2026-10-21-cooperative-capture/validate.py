"""One bounded host validation of the cooperative-control checkpoint."""
import hashlib
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
SCRIPT=HERE
TREE='--tree' in sys.argv
if TREE:HERE=HERE.parent/'2026-10-21-cooperative-tree'
TRANSPORT='--transport' in sys.argv
if TRANSPORT:HERE=SCRIPT.parent/'2026-10-21-capture-transport'
WORK=Path(os.environ['DISKED_WORK_ROOT'])
DEPS=WORK/'dependencies'
ENV=dict(os.environ,PYTHONPATH=str(DEPS),PYTHONDONTWRITEBYTECODE='1')
record=dict(status='running',scope=__doc__,commands=[],base_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT).decode().strip())
commands=[
    ['-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-deps','--only-binary=:all:','--target',str(DEPS),'PyYAML==6.0.3'],
    ['spec/tools/specctl.py','index'],['spec/tools/specctl.py','manifest'],['spec/tools/specctl.py','check'],
    ['tools/check-source-map.py'],[str(SCRIPT/'replay.py'),*(['--transport'] if TRANSPORT else ['--tree'] if TREE else [])],
    ['-m','unittest','discover','-s','spec/tools/tests','-v'],
    ['-m','unittest','discover','-s','tests/tools','-v'],
    ['-m','unittest','discover','-s','tests/differential','-v'],
    ['spec/tools/specctl.py','verify-manifest'],
]
if TREE or TRANSPORT:commands.insert(6,[str(SCRIPT/'replay.py'),'--no-write'])
if TRANSPORT:commands.insert(7,[str(SCRIPT/'replay.py'),'--tree','--no-write'])


def inputs():
    paths=set()
    for directory in ('spec','source','tools','tests/tools','tests/differential','tests/support','tests/corpus'):
        paths.update(p for p in (ROOT/directory).rglob('*') if p.is_file() and p.suffix in ('.py','.ps1','.c','.cpp','.h','.json','.md','.yaml','.yml'))
    for directory in (HERE,SCRIPT,ROOT/'.aide/evidence/2026-10-18-ordinary-worker'):
        paths.update(p for p in directory.iterdir() if p.is_file() and p.suffix in ('.py','.ps1','.cpp','.h'))
    paths.update((ROOT/'CMakeLists.txt',ROOT/'docs/source-map.md',ROOT/'tests/frontend/window_capture_probe.cpp',ROOT/'tests/frontend/window_capture_import_probe.cpp',HERE/'expected.json',SCRIPT/'expected.json'))
    if TRANSPORT:paths.add(SCRIPT.parent/'2026-10-21-cooperative-tree/expected.json')
    return {p.relative_to(ROOT).as_posix():'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(paths)}


def retain():
    body=(json.dumps(record,indent=2)+'\n').encode();assert len(body)<=4194304
    packed=lzma.compress(body,format=lzma.FORMAT_XZ,filters=[dict(id=lzma.FILTER_LZMA2,dict_size=1048576,preset=6)])
    assert lzma.decompress(packed)==body
    (HERE/'validation.json.xz').write_bytes(packed)


try:
    for i,args in enumerate(commands):
        if i==3:record['tested_inputs']=inputs()
        print(json.dumps(dict(running=args)),flush=True)
        result=subprocess.run([sys.executable,'-B',*args],cwd=ROOT,env=os.environ if i==0 else ENV,capture_output=True,timeout=900)
        assert len(result.stdout)+len(result.stderr)<=262144
        record['commands'].append(dict(arguments=result.args,exit_code=result.returncode,stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
        retain()
        if result.returncode:raise RuntimeError('Validation failed:'+str(args))
    assert inputs()==record['tested_inputs']
    record.update(status='pass',tested_inputs_unchanged=True);retain()
except BaseException:
    record['status']='fail';retain();raise
