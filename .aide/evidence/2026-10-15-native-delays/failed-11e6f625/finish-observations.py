"""Retain independent checks after failed native qualification; never clear that failure."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

out = Path(__file__).resolve().parent
source, build = out / 'source', out / 'build'
assert json.loads((out / 'current-stage.json').read_bytes())['status'] == 'fail'
assert (out / 'failure.json').is_file()
cases = list(ET.parse(out / 'native-junit.xml').getroot().iter('testcase'))
assert len(cases) == 145
failed = [c.attrib['name'] for c in cases if any(c.find(k) is not None for k in ['failure', 'error'])]
assert failed
commands = []

def save(name, value):
    (out / name).write_bytes(json.dumps(value, indent=2).encode() + b'\n')

def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()

def run(name, command):
    command = list(map(str, command))
    started = time.monotonic()
    with (out / ('post-native-' + name + '.log')).open('wb') as log:
        result = subprocess.run(command, cwd=source, stdout=log, stderr=subprocess.STDOUT)
    commands.append(dict(name=name, command=command, cwd=str(source), exit_code=result.returncode,
        elapsed_seconds=round(time.monotonic() - started, 3), log='post-native-' + name + '.log'))
    save('post-native-commands.json', commands)
    print(name + ': exit ' + str(result.returncode), flush=True)
    assert result.returncode == 0

run('tooling', [sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'spec/tools/tests', '-v'])
specctl = [sys.executable, '-X', 'utf8', 'spec/tools/specctl.py']
for name, options in [('spec-check', ['check']), ('index', ['index', '--check']),
                       ('manifest', ['verify-manifest'])]:
    run(name, specctl + options)
run('source-map', [sys.executable, '-X', 'utf8', 'tools/check-source-map.py'])
run('context', specctl + ['context', '--work', 'DE-W075', '--output', out / 'context', '--byte-budget', '1200000'])
run('verify-context', specctl + ['verify-context', out / 'context'])
identity = json.loads((build / 'generated/build-identity.json').read_bytes())
save('build-identity.json', identity)
dumpbin = Path(identity['compiler_path']).with_name('dumpbin.exe')
artifacts = []
for name in ['disked', 'disked_exfat_test', 'gpt_execution_probe', 'command_parser_probe', 'acquisition_command_probe',
             'exfat_capture_probe', 'exfat_tree_probe', 'exfat_namespace_probe', 'exfat_file_probe',
             'exfat_file_fault', 'exfat_worker_probe', 'exfat_worker_fault', 'report_worker_probe', 'report_worker_fault',
             'verification_worker_probe', 'verification_worker_fault', 'acquisition_worker_probe', 'acquisition_worker_fault']:
    artifact = build / 'Release' / (name + '.exe')
    artifacts.append(dict(path=str(artifact), bytes=artifact.stat().st_size, sha256=sha(artifact)))
    for mode in ['headers', 'imports', 'dependents']:
        run(name + '-' + mode, [dumpbin, '/' + mode, artifact])
objects = [p for directory in build.glob('*_headers.dir') for p in (directory / 'Release').glob('*.obj')]
assert len(objects) == 51
save('artifact-identities.json', artifacts + [dict(path=str(p), bytes=p.stat().st_size, sha256=sha(p)) for p in objects])
run('final-source-status', ['git', 'status', '--porcelain'])
assert not (out / 'post-native-final-source-status.log').read_bytes().strip()
inputs = json.loads((out / 'source-inputs.json').read_bytes())
assert all(sha(source / path) == digest for path, digest in inputs.items())
tooling = (out / 'post-native-tooling.log').read_text(encoding='utf8')
assert 'Ran 242 tests' in tooling and 'OK (skipped=2)' in tooling
tree = json.loads((build / 'exfat-tree-file-cases.json').read_bytes())
assert tree['passed'] and tree['cases'] == 46 and tree['methods'] == 8
file = json.loads((build / 'exfat-file-cases.json').read_bytes())
save('observation-summary.json', dict(status='fail', work_id='DE-W075',
    source_revision=identity['identity']['source_revision'], native_groups=145, native_failed=failed,
    native_passed=145-len(failed), full_native_qualified=False, header_compilations_fresh=51,
    tree_file_cases=46, tree_file_methods=8, tooling_tests_run=242, tooling_tests_skipped=2,
    source_state='clean_sparse', inputs_unchanged=True, unverified=file['unverified'],
    owner_accepted=False, full_0_1_0_complete=False,
    scope='Private held ordinary-image tree passes; full Windows regression campaign fails. Independent structural/tooling/import observations cannot clear native failures.'))
print('Failed native campaign retained; independent observations complete.', flush=True)
