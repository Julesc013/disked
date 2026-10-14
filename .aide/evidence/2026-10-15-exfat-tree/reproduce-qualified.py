"""Reproduce W074's tree and full native campaign at an immutable source revision."""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument('--revision', required=True)
args = parser.parse_args()
root = Path.cwd()
revision = subprocess.check_output(['git', 'rev-parse', args.revision], text=True).strip()
out = root / ('.aide-local/exfat-tree-exact-' + revision[:8])
out.mkdir(exist_ok=False)
clone, build = out / 'source', out / 'build'
commands = []

def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')

def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()

def run(name, command, cwd=clone, data=None):
    command = list(map(str, command))
    save(out / 'current-stage.json', dict(stage=name, status='running', source_revision=revision))
    started = time.monotonic()
    with (out / (name + '.log')).open('wb') as log:
        result = subprocess.run(command, cwd=cwd, input=data, stdout=log, stderr=subprocess.STDOUT)
    commands.append(dict(name=name, command=command, cwd=str(cwd), exit_code=result.returncode,
        elapsed_seconds=round(time.monotonic() - started, 3), log=name + '.log'))
    save(out / 'commands.json', commands)
    print(name + ': exit ' + str(result.returncode), flush=True)
    if result.returncode:
        failure = dict(stage=name, status='fail', exit_code=result.returncode, source_revision=revision)
        save(out / 'failure.json', failure)
        save(out / 'current-stage.json', failure)
        raise SystemExit(result.returncode)
    return (out / (name + '.log')).read_bytes()

run('clone', ['git', 'clone', '--local', '--no-hardlinks', '--no-checkout', root, clone], root)
def blob(path):
    return json.loads(subprocess.check_output(['git', 'show', revision + ':' + path], cwd=root))
catalog, registry = blob('tools/build-inputs.json'), blob('spec/catalog/input-dependencies.json')
required = set(catalog['files']) | set(registry['always']) | {i['path'] for i in registry['inputs']}
patterns = sorted({'/source/', '/tests/', '/spec/', '/tools/', '/docs/', '/external/', '/release/',
                   '/.gitattributes', '/.gitignore', '/.editorconfig', '/.clang-format', '/AGENTS.md'} |
                  {'/' + p for p in required})
run('sparse-selection', ['git', 'sparse-checkout', 'set', '--no-cone', '--stdin'],
    data=('\n'.join(patterns) + '\n').encode())
run('checkout', ['git', 'checkout', '--detach', revision])
assert not run('initial-source-status', ['git', 'status', '--porcelain']).strip()
assert all((clone / p).is_file() for p in required)
paths = required | {p.relative_to(clone).as_posix() for folder in ['source', 'tests']
                    for p in (clone / folder).rglob('*') if p.is_file()}
inputs = {p: sha(clone / p) for p in sorted(paths)}
save(out / 'source-inputs.json', inputs)
save(out / 'checkout-selection.json', dict(source_state='clean_sparse', patterns=patterns,
    registered_and_build_inputs_complete=True,
    excluded='Unused historical evidence archive; all current implementation and native test inputs included.'))
run('configure', ['cmake', '--preset', 'windows-bootstrap', '-B', build,
                  '-DPython3_EXECUTABLE=' + sys.executable])
run('build', ['cmake', '--build', build, '--config', 'Release', '--parallel', '4'])
run('native', ['ctest', '--test-dir', build, '-C', 'Release', '--output-on-failure',
               '--output-junit', out / 'native-junit.xml'])
junit = ET.parse(out / 'native-junit.xml').getroot()
assert len(list(junit.iter('testcase'))) == 143
assert not any(list(junit.iter(k)) for k in ['failure', 'error', 'skipped'])
run('tooling', [sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'spec/tools/tests', '-v'])
specctl = [sys.executable, '-X', 'utf8', 'spec/tools/specctl.py']
for name, options in [('spec-check', ['check']), ('index', ['index', '--check']),
                       ('manifest', ['verify-manifest'])]:
    run(name, specctl + options)
run('source-map', [sys.executable, '-X', 'utf8', 'tools/check-source-map.py'])
run('context', specctl + ['context', '--work', 'DE-W074', '--output', out / 'context',
                         '--byte-budget', '1200000'])
run('verify-context', specctl + ['verify-context', out / 'context'])
identity = json.loads((build / 'generated/build-identity.json').read_bytes())
dumpbin = Path(identity['compiler_path']).with_name('dumpbin.exe')
artifacts = []
for name in ['disked', 'disked_exfat_test', 'exfat_capture_probe', 'exfat_tree_probe', 'exfat_namespace_probe', 'exfat_file_probe',
             'exfat_file_fault', 'exfat_worker_probe', 'exfat_worker_fault', 'report_worker_probe', 'report_worker_fault',
             'verification_worker_probe', 'verification_worker_fault', 'acquisition_worker_probe', 'acquisition_worker_fault']:
    artifact = build / 'Release' / (name + '.exe')
    artifacts.append(dict(path=str(artifact), bytes=artifact.stat().st_size, sha256=sha(artifact)))
    for mode in ['headers', 'imports', 'dependents']:
        run(name + '-' + mode, [dumpbin, '/' + mode, artifact])
objects = [p for directory in build.glob('*_headers.dir') for p in (directory / 'Release').glob('*.obj')]
assert len(objects) == 51
save(out / 'artifact-identities.json', artifacts + [dict(path=str(p), bytes=p.stat().st_size,
                                                       sha256=sha(p)) for p in objects])
for name in ['exfat-tree-cases.json', 'exfat-namespace-cases.json', 'exfat-command-cases.json', 'exfat-capture-cases.json', 'exfat-file-cases.json',
             'exfat-worker-cases.json', 'worker-ancestry-cases.json', 'private-header-usage.json']:
    shutil.copyfile(build / name, out / name)
shutil.copyfile(build / 'generated/build-identity.json', out / 'build-identity.json')
shutil.copyfile(out / 'context/manifest.json', out / 'context-manifest.json')
capture = json.loads((out / 'exfat-capture-cases.json').read_bytes())
file = json.loads((out / 'exfat-file-cases.json').read_bytes())
worker = json.loads((out / 'exfat-worker-cases.json').read_bytes())
ancestry = json.loads((out / 'worker-ancestry-cases.json').read_bytes())
assert ancestry['passed'] and ancestry['cases'] == 3
command = json.loads((out / 'exfat-command-cases.json').read_bytes())
namespace = json.loads((out / 'exfat-namespace-cases.json').read_bytes())
tree = json.loads((out / 'exfat-tree-cases.json').read_bytes())
assert tree['passed'] and tree['cases'] == 40 and tree['methods'] == 9
assert namespace['passed'] and namespace['cases'] == 303 and namespace['methods'] == 12
assert capture['passed'] and capture['cases'] == 146 and capture['methods'] == 13
assert file['passed'] and file['cases'] == 89 and file['methods'] == 11
assert worker['passed'] and worker['cases'] == 94 and worker['methods'] == 9
assert command['passed'] and command['cases'] == 33
assert 'Ran 242 tests' in (out / 'tooling.log').read_text(encoding='utf-8')
assert 'OK (skipped=2)' in (out / 'tooling.log').read_text(encoding='utf-8')
assert not run('final-source-status', ['git', 'status', '--porcelain']).strip()
assert all(sha(clone / p) == digest for p, digest in inputs.items())
save(out / 'summary.json', dict(status='pass', source_revision=revision, source_state='clean_sparse',
    native_groups_fresh=143, header_compilations_fresh=51, tree_cases=40, tree_methods=9, namespace_cases=303, namespace_methods=12, capture_cases=146, capture_methods=13,
    file_cases=89, file_methods=11, worker_cases=94, worker_methods=9, command_cases=33,
    tooling_tests_run=242, tooling_tests_skipped=2, full_native_suite_fresh=True,
    scope='Private supplied-reader coherent exFAT tree/logical contents, owned root capture and existing Windows ordinary-image prototype',
    tested_frontends=['cli', 'protocol', 'gui', 'tui', 'shell'],
    unverified=file['unverified'], owner_accepted=False, full_0_1_0_complete=False))
save(out / 'current-stage.json', dict(stage='complete', status='pass', source_revision=revision))
