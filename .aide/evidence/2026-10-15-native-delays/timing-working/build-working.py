import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

root = Path.cwd()
out = root / '.aide-local/acquisition-timing-build'
out.mkdir(exist_ok=False)
commands = []
source_path = root / 'source/providers/image/file_acquisition.cpp'
source_sha = 'sha256:' + hashlib.sha256(source_path.read_bytes()).hexdigest()

def run(name, command):
    command = list(map(str, command))
    started = time.monotonic()
    with (out / (name + '.log')).open('wb') as log:
        p = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
    commands.append(dict(name=name, command=command, exit_code=p.returncode,
        elapsed_seconds=round(time.monotonic() - started, 3), cwd=str(root), log=name + '.log'))
    (out / 'commands.json').write_bytes(json.dumps(commands, indent=2).encode() + b'\n')
    print(name + ': exit ' + str(p.returncode), flush=True)
    assert p.returncode == 0

run('configure', ['cmake', '--preset', 'windows-bootstrap', '-B', out,
    '-DPython3_EXECUTABLE=' + sys.executable])
run('build', ['cmake', '--build', out, '--config', 'Release', '--parallel', '4',
    '--target', 'file_acquisition_probe', 'file_acquisition_fault'])
run('existing-regression', ['ctest', '--test-dir', out, '-C', 'Release', '--output-on-failure',
    '-R', '^image.file_acquisition$', '--output-junit', out / 'regression-junit.xml'])
assert source_sha == 'sha256:' + hashlib.sha256(source_path.read_bytes()).hexdigest()
(out / 'summary.json').write_bytes(json.dumps(dict(status='selected-build-and-regression-pass',
    source_sha256=source_sha, full_native_qualified=False, owner_accepted=False), indent=2).encode() + b'\n')
