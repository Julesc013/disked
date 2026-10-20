"""One bounded product-capture attempt; retain compact results and owned cleanup."""
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
work=Path(os.environ['DISKED_WORK_ROOT'])
prepare='--prepare-only' in sys.argv
background='--background-proof' in sys.argv
transport=background or '--transport-proof' in sys.argv
full='--full-suite' in sys.argv
if background and '--transport-proof' in sys.argv:raise ValueError('Select one control profile')
if full and transport:raise ValueError('Select the full product suite or private controls')
if any(a not in ('--prepare-only','--transport-proof','--background-proof','--full-suite') for a in sys.argv[1:]):raise ValueError('Only preparation or a declared product/transport campaign')
if transport or full:HERE=HERE/('full-native' if full else 'background-controls' if background else 'framed-controls');HERE.mkdir(exist_ok=True)
if not prepare and (HERE/'receipt.json.xz').exists():raise ValueError('Review/retain previous product attempt before another run')
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
        call([sys.executable,'-B','spec/tools/specctl.py','context','--work','DE-W105','--output','.aide-local/context/current','--byte-budget','2097152','--artifact-byte-budget','25165824'],env=env)
        call([sys.executable,'-B','spec/tools/specctl.py','verify-context','.aide-local/context/current'],env=env)
    definition=importlib.util.spec_from_file_location('product_campaign',OLD/'campaign.py');campaign=importlib.util.module_from_spec(definition);definition.loader.exec_module(campaign)
    sys.argv=[str(OLD/'campaign.py'),*(['--capture-background-proof'] if background else ['--capture-transport-proof'] if transport else ['--native-x64','--interactive-ui'] if full else ['--focus-product-captures','--interactive-ui']),*(['--prepare-only'] if prepare else [])]
    code=campaign.main();record.update(status='pass' if code==0 else 'fail',exit_code=code)
    if code:raise RuntimeError('Product campaign did not pass; inspect retained exact outcome')
except BaseException:
    record['status']='fail';raise
finally:
    try:
        if not prepare:
            for source,target in [('result.json','receipt.json.xz'),('cleanup.json','cleanup.json.xz'),('runner-error.txt','runner-error.txt.xz')]:
                path=OLD/source
                if path.exists():packed(target,path.read_bytes());path.unlink()
            path=OLD/'retained.tar.xz'
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
