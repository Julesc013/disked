"""Bounded host coordinator checks; no native product execution or global install."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
work = Path(os.environ['DISKED_WORK_ROOT']).resolve()
deps = work / 'dependencies'
receipt = {'scope': 'Host specification coordinator only', 'status': 'running', 'commands': []}
resume = sys.argv[1:] == ['--resume-context']
if sys.argv[1:] and not resume:
    raise ValueError('Unknown coordinator option')
if resume:
    previous = json.loads(Path(__file__).with_name('spec-checks-context-budget.json').read_bytes())
    receipt['previous_stage_receipt'] = 'spec-checks-context-budget.json'
    receipt['commands'] = [c for c in previous['commands'] if c['exit_code'] == 0]
env = dict(os.environ, PYTHONPATH=str(deps), PYTHONDONTWRITEBYTECODE='1')


def run(arguments, *, dependency_env=True):
    # The complete schema/fixture suite needs more than the initial four-minute
    # bootstrap allowance on this shared host. Keep a finite 15-minute deadline;
    # no assertions or workspace/resource limits change.
    timeout = 900 if 'unittest' in arguments else 240
    try:
        result = subprocess.run(arguments, cwd=root, env=env if dependency_env else os.environ,
                                capture_output=True, timeout=timeout)
    except subprocess.TimeoutExpired as error:
        receipt['commands'].append({'arguments': list(map(str, arguments)),
                                    'exit_code': None, 'status': 'timeout',
                                    'deadline_seconds': timeout,
                                    'stdout': (error.stdout or b'')[:65536].decode(errors='replace'),
                                    'stderr': (error.stderr or b'')[:65536].decode(errors='replace')})
        raise
    if len(result.stdout) + len(result.stderr) > 131072:
        raise RuntimeError('Retained coordinator output limit exceeded')
    receipt['commands'].append({'arguments': list(map(str, arguments)), 'exit_code': result.returncode,
                                'stdout': result.stdout.decode(errors='replace'),
                                'stderr': result.stderr.decode(errors='replace')})
    if result.returncode:
        raise RuntimeError('Coordinator command failed: ' + str(arguments))


try:
    # The host already has jsonschema; only the pinned missing dependency is
    # installed into disposable work. No pip cache, user or global installation.
    run([sys.executable, '-B', '-m', 'pip', 'install', '--disable-pip-version-check',
         '--no-cache-dir', '--no-deps', '--only-binary=:all:', '--target', str(deps),
         'PyYAML==6.0.3'], dependency_env=False)
    size = sum(p.stat().st_size for p in deps.rglob('*') if p.is_file())
    if size > 16 * 1024 * 1024:
        raise RuntimeError('Coordinator dependency exceeds its 16 MiB bound')
    receipt['disposable_dependency_bytes'] = size
    for arguments in ([] if resume else [('spec/tools/specctl.py', 'index'), ('spec/tools/specctl.py', 'check'),
                      ('-m', 'unittest', 'discover', '-s', 'spec/tools/tests', '-v'),
                      ('spec/tools/specctl.py', 'manifest'), ('spec/tools/specctl.py', 'verify-manifest')]):
        run([sys.executable, '-B', *arguments])
    pack = root / '.aide-local/context/current'
    if pack.exists():
        raise RuntimeError('Superseded pack must be inspected and removed before generation')
    # 2 MiB prose + 24 MiB artifacts + 2 MiB manifest/overhead remains below
    # the unchanged 32 MiB aggregate metadata ceiling.
    run([sys.executable, '-B', 'tools/workspace.py', 'check', '--planned-bytes', '29360128'])
    run([sys.executable, '-B', 'spec/tools/specctl.py', 'context', '--work', 'DE-W105',
         '--output', str(pack), '--byte-budget', '2097152', '--artifact-byte-budget', '25165824'])
    run([sys.executable, '-B', 'spec/tools/specctl.py', 'verify-context', str(pack)])
    receipt['context_bytes'] = sum(p.stat().st_size for p in pack.rglob('*') if p.is_file())
    if receipt['context_bytes'] > 29360128:
        raise RuntimeError('Complete pack exceeds declared aggregate bound')
    receipt['context_manifest_sha256'] = hashlib.sha256((pack / 'manifest.json').read_bytes()).hexdigest()
    receipt['status'] = 'pass'
except BaseException as error:
    receipt['status'] = 'fail'
    receipt['error'] = str(error)
    raise
finally:
    Path(__file__).with_name('spec-checks.json').write_text(json.dumps(receipt, indent=2)+'\n',
                                                         encoding='utf-8', newline='\n')
