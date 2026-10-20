"""Bounded host Python/metadata validation; no native or external-tool campaign."""
import hashlib
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
WORK = Path(os.environ['DISKED_WORK_ROOT'])
DEPS = WORK / 'dependencies'
ENV = dict(os.environ, PYTHONPATH=str(DEPS), PYTHONDONTWRITEBYTECODE='1')
PREFIX = ('native-probes' if '--native-probes' in sys.argv else 'native-port' if '--native-port' in sys.argv else 'coordinator' if '--coordinator' in sys.argv
          else 'collector' if '--collectors' in sys.argv else 'bindings')
record = dict(status='running', scope=__doc__, suite=PREFIX, commands=[], base_revision=None)
commands = [
    ['-m', 'pip', 'install', '--disable-pip-version-check', '--no-cache-dir', '--no-deps',
     '--only-binary=:all:', '--target', str(DEPS), 'PyYAML==6.0.3'],
    ['spec/tools/specctl.py', 'index'],
    ['spec/tools/specctl.py', 'manifest'],
    ['spec/tools/specctl.py', 'check'],
    ['tools/check-source-map.py'],
    ['-m', 'unittest', 'discover', '-s', 'spec/tools/tests', '-v'],
    ['-m', 'unittest', 'discover', '-s', 'tests/tools', '-v'],
    ['-m', 'unittest', 'discover', '-s', 'tests/differential', '-v'],
    ['spec/tools/specctl.py', 'verify-manifest'],
]
if PREFIX == 'native-probes':
    commands.insert(5, [str(HERE / 'native-probes-replay.py')])


def retain():
    body = (json.dumps(record, indent=2) + '\n').encode()
    if len(body) > 4 * 1024 * 1024:
        raise ValueError('Validation receipt bound')
    packed = lzma.compress(body, format=lzma.FORMAT_XZ,
                           filters=[dict(id=lzma.FILTER_LZMA2, dict_size=1024 * 1024, preset=6)])
    if lzma.decompress(packed) != body:
        raise ValueError('Compressed receipt verification')
    (HERE / (PREFIX + '-validation.json.xz')).write_bytes(packed)


def input_hashes():
    paths = set()
    for directory in ('spec', 'tools', 'tests/tools', 'tests/differential', 'tests/corpus'):
        paths.update(p for p in (ROOT / directory).rglob('*') if p.is_file() and p.suffix in ('.py', '.json', '.md', '.yaml', '.yml'))
    paths.update(p for p in (ROOT / '.aide/evidence/2026-10-18-ordinary-worker').iterdir()
                 if p.is_file() and p.suffix in ('.py', '.ps1', '.cpp', '.h'))
    paths.update((ROOT / 'CMakeLists.txt', ROOT / 'docs/source-map.json', ROOT / 'docs/code-structure.md',
                  HERE / (PREFIX + '-expected.json'), Path(__file__).resolve()))
    if PREFIX == 'native-port':
        paths.update(HERE / name for name in ('native-port.py', 'native-port.cpp', 'native-port-inventory.ps1'))
    if PREFIX == 'native-probes':
        paths.update(HERE / name for name in ('native-port.py', 'native-port.cpp', 'native-probes.py',
            'native-probes-replay.py', 'native-probes-result.json.xz', 'native-probes-observations.tar.xz'))
        for directory in ('source/portable/primitives', 'source/portable/mbr', 'source/portable/ebr', 'source/portable/gpt'):
            paths.update(p for p in (ROOT / directory).iterdir() if p.suffix in ('.c', '.h'))
        paths.update(ROOT / name for name in ('source/runtime/command/json.cpp', 'source/runtime/command/json.h',
            'tests/unit/mbr_probe.cpp', 'tests/unit/gpt_probe.cpp'))
    return {p.relative_to(ROOT).as_posix(): 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()
            for p in sorted(paths) if p.is_file()}


try:
    record['base_revision'] = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip()
    for index, args in enumerate(commands):
        if index == 3:
            record['tested_inputs'] = input_hashes()
        command = [sys.executable, '-B', *args]
        print(json.dumps(dict(running=command)), flush=True)
        started = time.monotonic()
        result = subprocess.run(command, cwd=ROOT, env=ENV if index else os.environ,
                                capture_output=True, timeout=900)
        if len(result.stdout) + len(result.stderr) > 262144:
            raise ValueError('Validation command log bound')
        record['commands'].append(dict(arguments=command, exit_code=result.returncode,
            seconds=time.monotonic() - started, stdout=result.stdout.decode(errors='replace'),
            stderr=result.stderr.decode(errors='replace')))
        retain()
        if result.returncode:
            raise RuntimeError('Validation command failed')
    if input_hashes() != record['tested_inputs']:
        raise ValueError('Validation inputs changed during checks')
    record['inputs_unchanged'] = True
    record['status'] = 'pass'
except BaseException as error:
    record.update(status='fail', error=repr(error))
    raise
finally:
    retain()
