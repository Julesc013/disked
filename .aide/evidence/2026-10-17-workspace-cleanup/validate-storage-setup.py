"""Bounded tooling/spec validation; does not build DiskEd or provision storage."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parent
WORK = Path(os.environ['DISKED_WORK_ROOT']).resolve()
assert json.loads((WORK / 'owner.json').read_bytes())['root'] == str(ROOT)
results = []


def execute(name, command, env=None):
    log = WORK / (name + '.log')
    with log.open('wb') as stream:
        child = subprocess.run(command, cwd=ROOT, env=env, stdout=stream, stderr=subprocess.STDOUT,
                               timeout=600)
    data = log.read_bytes()
    if len(data) > 512 * 1024:
        raise RuntimeError('Unexpected validation log budget exceeded: ' + name)
    saved = OUT / ('storage-' + name + '.log')
    saved.write_bytes(data)
    results.append({'command': command, 'cwd': str(ROOT), 'exit_code': child.returncode,
                    'status': 'pass' if child.returncode == 0 else 'fail',
                    'evidence_path': saved.relative_to(ROOT).as_posix(),
                    'sha256': hashlib.sha256(data).hexdigest(), 'bytes': len(data)})
    if child.returncode:
        raise RuntimeError('Validation failed: ' + name)


try:
    deps = WORK / 'deps'
    execute('dependencies', [sys.executable, '-B', '-m', 'pip', 'install', '--target', str(deps),
            '--no-cache-dir', '--no-compile', '--no-deps', '--only-binary=:all:', 'PyYAML==6.0.3'])
    env = dict(os.environ, PYTHONPATH=str(deps), PYTHONDONTWRITEBYTECODE='1')
    for action in ('index', 'check'):
        execute(action, [sys.executable, '-B', 'spec/tools/specctl.py', action], env)
    execute('spec-tests', [sys.executable, '-B', '-m', 'unittest', 'discover', '-s', 'spec/tools/tests', '-v'], env)
    for action in ('manifest', 'verify-manifest'):
        execute(action, [sys.executable, '-B', 'spec/tools/specctl.py', action], env)
finally:
    (OUT / 'storage-validation.json').write_bytes((json.dumps(results, indent=2) + '\n').encode())
