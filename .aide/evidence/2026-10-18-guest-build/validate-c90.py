"""Host syntax-only portability check; never launches DiskEd or opens test media."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
WORK = Path(os.environ['DISKED_WORK_ROOT'])
compiler = shutil.which('gcc')
if not compiler:
    raise RuntimeError('Existing host GCC unavailable; no compiler was installed')
sources = sorted((ROOT / 'source/portable/ntfs').glob('*.c'))
inputs = sorted(p for p in (ROOT / 'source/portable').rglob('*') if p.suffix in ('.c','.h'))
before = {p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in inputs}
flags = ['-std=c90','-pedantic-errors','-Wall','-Wextra','-Werror','-fsyntax-only','-Isource']
commands = [[compiler,'--version'],[compiler,*flags,*[p.relative_to(ROOT).as_posix() for p in sources]]]
for header in ('ntfs.h','fixup.h'):
    path = WORK / (header+'.c')
    path.write_text('#include "portable/ntfs/'+header+'"\n',encoding='utf-8',newline='\n')
    commands.append([compiler,*flags,str(path)])
commands.append([sys.executable,'-B','tools/check-source-map.py'])
record = dict(status='running',scope='Host GCC syntax-only NTFS C90 and source-map metadata; no product execution, media, elevation or installation',
              execution_identity=os.environ.get('USERDOMAIN','')+'\\'+os.environ.get('USERNAME',''),
              source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),
              source_status=subprocess.check_output(['git','status','--porcelain'],cwd=ROOT,text=True),
              source_hashes=before,compiler_path=compiler,compiler_sha256=hashlib.sha256(Path(compiler).read_bytes()).hexdigest(),
              commands=[])
try:
    for command in commands:
        result = subprocess.run(command,cwd=ROOT,capture_output=True,timeout=120)
        if len(result.stdout)+len(result.stderr)>32768:
            raise RuntimeError('Syntax-check log exceeds declared bound')
        record['commands'].append(dict(arguments=command,exit_code=result.returncode,
            stdout=result.stdout.decode(errors='replace'),stderr=result.stderr.decode(errors='replace')))
        if result.returncode:
            raise RuntimeError('Syntax/source-map check failed')
    record['inputs_unchanged'] = all(hashlib.sha256((ROOT/p).read_bytes()).hexdigest()==digest for p,digest in before.items())
    if not record['inputs_unchanged']:
        raise RuntimeError('Portable source changed during syntax check')
    record['status']='pass'
finally:
    (HERE/'c90-source-map.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
