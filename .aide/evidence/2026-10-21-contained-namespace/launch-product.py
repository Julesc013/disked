"""Current DE-W030 full-product qualification through the proven bounded guest runner."""
import importlib.util
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
OLD=HERE.parent/'2026-10-18-ordinary-worker'
BUILD=HERE.parent/'2026-10-18-guest-build'
work=Path(os.environ['DISKED_WORK_ROOT'])
prepare='--prepare-only' in sys.argv
background='--background-proof' in sys.argv
transport=background or '--transport-proof' in sys.argv
full='--full-suite' in sys.argv
win32='--win32-suite' in sys.argv
source_proof='--source-proof' in sys.argv
watch='--watch-fixture' in sys.argv
if background and '--transport-proof' in sys.argv:raise ValueError('Select one control profile')
if sum((full,transport,win32,source_proof,watch))>1:raise ValueError('Select one native suite or private control profile')
if any(a not in ('--prepare-only','--transport-proof','--background-proof','--full-suite','--win32-suite','--source-proof','--watch-fixture') for a in sys.argv[1:]):raise ValueError('Only preparation or a declared product/transport campaign')
if transport or full or win32 or source_proof or watch:HERE=HERE/('watch-fixture' if watch else 'source-proof' if source_proof else 'private-win32' if win32 else 'full-native' if full else 'background-controls' if background else 'framed-controls');HERE.mkdir(exist_ok=True)
CAMPAIGN=BUILD if win32 else OLD
prepared_path=CAMPAIGN/('preparation.json' if win32 else 'prepared.json')
prepared_before=prepared_path.read_bytes() if prepared_path.exists() else None
if not prepare and (HERE/'receipt.json.xz').exists():raise ValueError('Review/retain previous product attempt before another run')
if not prepare:
    outputs=('result.json','cleanup.json','runner-error.txt','observations.tar.xz' if win32 else 'retained.tar.xz')
    if any((CAMPAIGN/name).exists() for name in outputs):raise ValueError('Retain previous raw campaign outputs before another run')
record=dict(status='running',source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),commands=[])
def call(args,*,env=None,timeout=180):
    result=subprocess.run(list(map(str,args)),cwd=ROOT,env=env,capture_output=True,timeout=timeout)
    if len(result.stdout)+len(result.stderr)>65536:raise ValueError('Preparation output bound')
    record['commands'].append(dict(arguments=result.args,exit_code=result.returncode,stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
    if result.returncode:raise RuntimeError('Preparation command failed:'+str(result.args))
def packed(name,body):
    if len(body)>8388608:raise ValueError('Receipt bound')
    data=lzma.compress(body,format=lzma.FORMAT_XZ,filters=[dict(id=lzma.FILTER_LZMA2,dict_size=1048576,preset=6)])
    assert lzma.decompress(data)==body
    (HERE/name).write_bytes(data)
try:
    if not prepare:
        call([sys.executable,'-B','-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-compile','--no-deps','--only-binary=:all:','--target',work/'dependencies','PyYAML==6.0.3'])
        env=dict(os.environ,PYTHONPATH=str(work/'dependencies'),PYTHONDONTWRITEBYTECODE='1')
        call([sys.executable,'-B','tools/workspace.py','check','--planned-bytes','29360128'])
        call([sys.executable,'-B','spec/tools/specctl.py','context','--work','DE-W030','--output','.aide-local/context/current','--byte-budget','2097152','--artifact-byte-budget','25165824'],env=env)
        call([sys.executable,'-B','spec/tools/specctl.py','verify-context','.aide-local/context/current'],env=env)
    definition=importlib.util.spec_from_file_location('product_campaign',CAMPAIGN/'campaign.py');campaign=importlib.util.module_from_spec(definition);definition.loader.exec_module(campaign)
    sys.argv=[str(CAMPAIGN/'campaign.py'),*([] if win32 else ['--focus-fat-watch','--interactive-ui'] if watch else ['--capture-background-proof'] if background else ['--capture-transport-proof'] if transport else ['--null-proof','--interactive-ui'] if source_proof else ['--native-x64','--interactive-ui'] if full else ['--focus-product-captures','--interactive-ui']),*(['--prepare-only'] if prepare else [])]
    code=campaign.main();record.update(status='pass' if code==0 else 'fail',exit_code=code)
    if code:raise RuntimeError('Product campaign did not pass; inspect retained exact outcome')
except BaseException:
    record['status']='fail';raise
finally:
    try:
        if prepared_path.exists():
            packed('prepared.json.xz',prepared_path.read_bytes())
            if prepared_before is None:prepared_path.unlink()
            else:prepared_path.write_bytes(prepared_before)
        if not prepare:
            for source,target in [('result.json','receipt.json.xz'),('cleanup.json','cleanup.json.xz'),('runner-error.txt','runner-error.txt.xz')]:
                path=CAMPAIGN/source
                if path.exists():packed(target,path.read_bytes());path.unlink()
            path=CAMPAIGN/('observations.tar.xz' if win32 else 'retained.tar.xz')
            if path.exists():
                target=HERE/'retained.tar.xz'
                if target.exists():raise ValueError('Refuse replacing retained evidence')
                path.replace(target)
            # The campaign has returned and retired its readers. Keep the context
            # until then; the reviewed helper rejects nested repositories/links.
            call(['pwsh','-NoProfile','-File','tools/clean-scratch.ps1','-Delete','-WorkersStopped'])
    except BaseException:
        record['status']='fail';raise
    finally:
        packed('preparation.json.xz' if prepare else 'launch.json.xz',(json.dumps(record,indent=2)+'\n').encode())
