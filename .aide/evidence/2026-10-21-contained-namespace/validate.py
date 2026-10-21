"""Retain bounded host metadata checks; no host native execution."""
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
work=Path(os.environ['DISKED_WORK_ROOT'])
full=sys.argv[1:]==['--full']
if sys.argv[1:] not in ([],['--full']):raise ValueError('Select preparation or full metadata validation')
record=dict(status='running',source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),commands=[])
record['source_worktree_dirty']=bool(subprocess.check_output(['git','status','--porcelain'],cwd=ROOT))
record['scope']='Host metadata/tests and retained evidence integrity; not native qualification'
record['native_gate_passed']=False
record['native_gate_source']='54bc8cd8a844344336ce8485202a108e5c04d784'
record['native_groups_passed']=176
record['native_groups_attempted']=180
env=dict(os.environ,PYTHONPATH=str(work/'dependencies'),PYTHONDONTWRITEBYTECODE='1')
commands=[['-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-compile','--no-deps','--only-binary=:all:','--target',env['PYTHONPATH'],'PyYAML==6.0.3'],
    ['spec/tools/specctl.py','index'],['spec/tools/specctl.py','manifest'],['spec/tools/specctl.py','check'],['tools/check-source-map.py'],
    ['-m','unittest','discover','-s','tests/tools','-v'],
    ['-m','unittest','discover','-s','tests/windows','-p','test_native*observations.py','-v'],
    [str(HERE/'replay.py')],['spec/tools/specctl.py','verify-manifest']]
if (HERE/'private-win32/receipt.json.xz').exists():
    commands.insert(-1,[str(HERE.parent/'2026-10-21-product-capture/private-win32/replay.py'),'--evidence-dir',str(HERE/'private-win32')])
if full:
    commands.insert(5,['-m','unittest','discover','-s','spec/tools/tests','-v'])
    commands.insert(-1,['-m','unittest','discover','-s','tests/differential','-v'])
    commands.extend([
        [str(HERE/'review-failure.py')],
        ['spec/tools/specctl.py','context','--work','DE-W030','--output',str(work/'context'),
         '--byte-budget','2097152','--artifact-byte-budget','25165824'],
        ['spec/tools/specctl.py','verify-context',str(work/'context')],
    ])
else:
    commands.extend([[str(HERE/'launch-product.py'),flag,'--prepare-only'] for flag in ('--full-suite','--win32-suite')])

def retain():
    body=(json.dumps(record,indent=2)+'\n').encode();assert len(body)<1048576
    data=lzma.compress(body,filters=[dict(id=lzma.FILTER_LZMA2,dict_size=1048576,preset=6)])
    assert lzma.decompress(data)==body
    (HERE/('validation.json.xz' if full else 'product-preparation.json.xz')).write_bytes(data)

def inputs():
    definition=importlib.util.spec_from_file_location('selected_source',ROOT/'tools/source-snapshot.py')
    snapshot=importlib.util.module_from_spec(definition);definition.loader.exec_module(snapshot)
    paths=set(snapshot.selected_inputs(ROOT,'DE-W030'))
    paths.update(('TODO.MD','docs/project-status.md','docs/index.md','docs/structure-review.md',
        'docs/windows-inventory.md','docs/development-plan.md'))
    size=sum((ROOT/p).stat().st_size for p in paths)
    assert len(paths)<=snapshot.FILE_LIMIT and size<=snapshot.SOURCE_LIMIT
    return {p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in sorted(paths)},size

try:
    for arguments in commands:
        if arguments==['spec/tools/specctl.py','check']:
            record['tested_inputs'],record['source_bytes']=inputs()
        value=subprocess.run([sys.executable,'-B',*arguments],cwd=ROOT,env=env,capture_output=True,timeout=1200)
        assert len(value.stdout)+len(value.stderr)<=262144
        record['commands'].append(dict(arguments=value.args,exit_code=value.returncode,
            stdout=value.stdout.decode(errors='replace'),stderr=value.stderr.decode(errors='replace')));retain()
        print(json.dumps(dict(command=arguments,exit_code=value.returncode)),flush=True)
        if value.returncode:raise RuntimeError('Metadata validation failed: '+str(arguments))
    current,size=inputs()
    if current!=record['tested_inputs']:raise ValueError('Validation inputs changed during execution')
    record.update(status='pass',source_files=len(current),source_bytes=size,tested_inputs_unchanged=True)
    retain()
except BaseException:
    record['status']='fail';retain();raise
