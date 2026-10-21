"""Small host checks for the repair; native qualification remains in the guest."""
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
record=dict(status='running',scope='Host repair regressions, structure and context only',commands=[])
env=dict(os.environ,PYTHONPATH=str(work/'dependencies'),PYTHONDONTWRITEBYTECODE='1')
commands=[
    ['-m','pip','install','--disable-pip-version-check','--no-cache-dir','--no-compile','--no-deps','--only-binary=:all:','--target',env['PYTHONPATH'],'PyYAML==6.0.3'],
    ['-m','unittest','discover','-s','tests/tools','-p','test_window_capture_review.py','-v'],
    ['spec/tools/specctl.py','index'],['spec/tools/specctl.py','manifest'],
    ['spec/tools/specctl.py','check'],['tools/check-source-map.py'],
    ['spec/tools/specctl.py','verify-manifest'],
    ['spec/tools/specctl.py','context','--work','DE-W030','--output',str(work/'context'),
     '--byte-budget','2097152','--artifact-byte-budget','25165824'],
    ['spec/tools/specctl.py','verify-context',str(work/'context')],
]
try:
    for command in commands:
        value=subprocess.run([sys.executable,'-B',*command],cwd=ROOT,env=env,capture_output=True,timeout=180)
        if len(value.stdout)+len(value.stderr)>65536:raise ValueError('Host check output bound')
        record['commands'].append(dict(arguments=value.args,exit_code=value.returncode,
            stdout=value.stdout.decode(errors='replace'),stderr=value.stderr.decode(errors='replace')))
        if value.returncode:raise RuntimeError('Repair preparation failed: '+str(command))
    paths=['tests/frontend/gui_fixture.py','tests/tools/test_window_capture_review.py',
        '.aide/evidence/2026-10-18-ordinary-worker/campaign.py',
        str((HERE/'launch-product.py').relative_to(ROOT)),str((HERE/'REPAIR.md').relative_to(ROOT))]
    record['inputs']={p:hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in paths}
    record['status']='pass'
except BaseException:
    record['status']='fail'
    raise
finally:
    body=(json.dumps(record,indent=2)+'\n').encode()
    if len(body)>131072:raise ValueError('Repair check receipt bound')
    (HERE/'repair-check.json.xz').write_bytes(lzma.compress(body,filters=[dict(id=lzma.FILTER_LZMA2,dict_size=1048576,preset=6)]))
