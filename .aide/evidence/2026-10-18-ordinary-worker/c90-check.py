"""Required C90 syntax check using installed host GCC; no product code executes."""
import ctypes
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
work = Path(os.environ['DISKED_WORK_ROOT'])
record = dict(status='running', scope=__doc__, product_code_executed=False, commands=[], inputs=[])


def run(command, *, cwd):
    start = time.monotonic()
    result = subprocess.run(list(map(str, command)), cwd=cwd, env=env, capture_output=True, timeout=45)
    if len(result.stdout) + len(result.stderr) > 65536:
        raise ValueError('Syntax diagnostic bound')
    record['commands'].append(dict(command=list(map(str, command)), exit_code=result.returncode,
        seconds=time.monotonic()-start, stdout=result.stdout.decode(errors='replace'), stderr=result.stderr.decode(errors='replace')))
    if result.returncode:
        raise ValueError('C90 command failed')
    return result.stdout


try:
    if os.name != 'nt' or ctypes.windll.shell32.IsUserAnAdmin():
        raise PermissionError('This selected host metadata check requires a non-elevated Windows user')
    proof = json.loads((HERE / 'result.json').read_bytes())['guest']['proof']
    revision = proof['source_revision']
    record['source_revision'] = revision
    compiler = shutil.which('gcc')
    if not compiler:
        raise FileNotFoundError('Installed host GCC unavailable; do not install or silently substitute')
    record['compiler'] = dict(path=compiler, sha256=hashlib.sha256(Path(compiler).read_bytes()).hexdigest())
    source = work / 'source'
    source.mkdir()
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', revision, 'source/portable'], cwd=ROOT, text=True).splitlines()
    for name in paths:
        if not name.endswith(('.c', '.h')):
            continue
        data = subprocess.check_output(['git', 'show', revision + ':' + name], cwd=ROOT, timeout=30)
        if len(data) > 1024*1024:
            raise ValueError('Portable input bound')
        path = work / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        record['inputs'].append(dict(path=name, bytes=len(data), sha256=hashlib.sha256(data).hexdigest()))
    env = dict(os.environ, TEMP=str(work), TMP=str(work), TMPDIR=str(work))
    for name in ('CPATH', 'C_INCLUDE_PATH', 'CPLUS_INCLUDE_PATH', 'GCC_EXEC_PREFIX', 'COMPILER_PATH'):
        env.pop(name, None)
    record['execution'] = dict(host=os.environ.get('COMPUTERNAME'), user=os.environ.get('USERNAME'), elevated=False,
        temporary_output='owned managed workspace', ambient_include_and_compiler_overrides_cleared=True)
    run([compiler, '--version'], cwd=work)
    run([compiler, '-dumpmachine'], cwd=work)
    flags = ['-std=c90', '-pedantic-errors', '-Wall', '-Wextra', '-Werror', '-fsyntax-only', '-Isource']
    units = sorted((source / 'portable/ntfs').glob('*.c'))
    if not units:
        raise ValueError('No selected NTFS C units')
    run([compiler, *flags, *units], cwd=work)
    for name in ('ntfs.h', 'fixup.h'):
        unit = work / (name + '.c')
        unit.write_text('#include "portable/ntfs/' + name + '"\n', encoding='utf-8')
        run([compiler, *flags, unit], cwd=work)
    record.update(status='pass', c_units=len(units), standalone_c_headers=2)
except BaseException as error:
    record.update(status='fail', error=repr(error))
    raise
finally:
    (HERE / 'c90-result.json').write_text(json.dumps(record, indent=2) + '\n', encoding='utf-8', newline='\n')
