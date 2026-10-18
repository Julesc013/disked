"""Fresh source-bound work context using disposable coordinator dependencies."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[3]
work = Path(os.environ['DISKED_WORK_ROOT'])
deps = work / 'dependencies'
env = dict(os.environ, PYTHONPATH=str(deps), PYTHONDONTWRITEBYTECODE='1')
commands = [[sys.executable, '-B', '-m', 'pip', 'install', '--disable-pip-version-check',
             '--no-cache-dir', '--no-deps', '--only-binary=:all:', '--target', str(deps), 'PyYAML==6.0.3'],
            [sys.executable, '-B', 'spec/tools/specctl.py', 'check'],
            [sys.executable, '-B', 'spec/tools/specctl.py', 'verify-manifest'],
            [sys.executable, '-B', 'tools/workspace.py', 'check', '--planned-bytes', '29360128'],
            [sys.executable, '-B', 'spec/tools/specctl.py', 'context', '--work', 'DE-W105',
             '--output', '.aide-local/context/current', '--byte-budget', '2097152',
             '--artifact-byte-budget', '25165824'],
            [sys.executable, '-B', 'spec/tools/specctl.py', 'verify-context', '.aide-local/context/current']]
record = {'status': 'running', 'commands': []}
try:
    for index, command in enumerate(commands):
        result = subprocess.run(command, cwd=root, env=os.environ if index == 0 else env,
                                capture_output=True, timeout=180)
        if len(result.stdout) + len(result.stderr) > 32768:
            raise RuntimeError('Context coordinator output exceeds bound')
        record['commands'].append({'arguments': command, 'exit_code': result.returncode,
                                    'stdout': result.stdout.decode(errors='replace'),
                                    'stderr': result.stderr.decode(errors='replace')})
        if result.returncode:
            raise RuntimeError('Context preparation failed')
    pack = root / '.aide-local/context/current'
    record.update(status='pass', context_manifest_sha256=hashlib.sha256((pack / 'manifest.json').read_bytes()).hexdigest(),
                  complete_pack_bytes=sum(p.stat().st_size for p in pack.rglob('*') if p.is_file()))
finally:
    Path(__file__).with_name('context.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8', newline='\n')
