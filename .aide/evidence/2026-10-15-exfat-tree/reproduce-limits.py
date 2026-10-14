"""Exact-source qualification of the private tree limits correction.

This is a delta to the separately retained complete e7e3297f campaign. It does
not claim that the full native suite or product was rebuilt at this revision.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET

parser = argparse.ArgumentParser()
parser.add_argument('--revision', required=True)
args = parser.parse_args()
root = Path.cwd()
revision = subprocess.check_output(['git', 'rev-parse', args.revision], text=True).strip()
out = root / ('.aide-local/exfat-tree-limits-exact-' + revision[:8])
out.mkdir(exist_ok=False)
clone = out / 'source'
commands = []


def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf8', newline='\n')


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def run(name, command, cwd=clone, data=None):
    command = list(map(str, command))
    stage = dict(stage=name, status='running', source_revision=revision)
    save(out / 'current-stage.json', stage)
    started = time.monotonic()
    with (out / (name + '.log')).open('wb') as log:
        result = subprocess.run(command, cwd=cwd, input=data, stdout=log, stderr=subprocess.STDOUT)
    commands.append(dict(name=name, command=command, cwd=str(cwd), exit_code=result.returncode,
        elapsed_seconds=round(time.monotonic() - started, 3), log=name + '.log'))
    save(out / 'commands.json', commands)
    print(name + ': exit ' + str(result.returncode), flush=True)
    if result.returncode:
        stage.update(status='fail', exit_code=result.returncode)
        save(out / 'current-stage.json', stage)
        save(out / 'failure.json', stage)
        raise SystemExit(result.returncode)


run('clone', ['git', 'clone', '--local', '--no-hardlinks', '--no-checkout', root, clone], root)
def blob(path):
    return json.loads(subprocess.check_output(['git', 'show', revision + ':' + path], cwd=root))
catalog, registry = blob('tools/build-inputs.json'), blob('spec/catalog/input-dependencies.json')
required = set(catalog['files']) | set(registry['always']) | {r['path'] for r in registry['inputs']}
patterns = sorted({'/source/', '/tests/', '/spec/', '/tools/', '/docs/', '/external/', '/release/',
    '/.gitattributes', '/.gitignore', '/.editorconfig', '/.clang-format', '/AGENTS.md'} | {'/' + p for p in required})
run('sparse', ['git', 'sparse-checkout', 'set', '--no-cone', '--stdin'], data=('\n'.join(patterns) + '\n').encode())
run('checkout', ['git', 'checkout', '--detach', revision])
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=clone).strip()
assert all((clone / p).is_file() for p in required)
paths = required | {p.relative_to(clone).as_posix() for folder in ['source', 'tests']
    for p in (clone / folder).rglob('*') if p.is_file()}
inputs = {p: sha(clone / p) for p in sorted(paths)}
save(out / 'source-inputs.json', inputs)
targets = ['exfat_tree_probe', 'exfat_namespace_probe', 'exfat_capture_probe',
    'disked_exfat_tree_headers', 'disked_exfat_namespace_headers', 'disked_exfat_capture_headers', 'disked_exfat_upcase_headers']
for architecture in ['x64', 'Win32']:
    build = out / architecture
    run(architecture + '-configure', ['cmake', '--preset', 'windows-bootstrap', '-A', architecture,
        '-B', build, '-DPython3_EXECUTABLE=' + sys.executable])
    run(architecture + '-build', ['cmake', '--build', build, '--config', 'Release', '--target', *targets, '--parallel', '4'])
    run(architecture + '-native', ['ctest', '--test-dir', build, '-C', 'Release', '-R',
        '^(image.exfat_(tree|namespace|capture)|build.boundaries|recovery.gpt_fixture_harness)$',
        '--output-on-failure', '--output-junit', out / (architecture + '-junit.xml')])
    junit = ET.parse(out / (architecture + '-junit.xml')).getroot()
    assert len(list(junit.iter('testcase'))) == 5
    assert not any(list(junit.iter(k)) for k in ['failure', 'error', 'skipped'])
    for name in ['exfat-tree-cases.json', 'exfat-namespace-cases.json', 'exfat-capture-cases.json', 'generated/build-identity.json']:
        shutil.copyfile(build / name, out / (architecture + '-' + Path(name).name))
    tree = json.loads((build / 'exfat-tree-cases.json').read_bytes())
    assert tree['passed'] and tree['cases'] == 44 and tree['methods'] == 10
    identity = json.loads((build / 'generated/build-identity.json').read_bytes())
    dumpbin = Path(identity['compiler_path']).with_name('dumpbin.exe')
    for name in ['exfat_tree_probe', 'exfat_namespace_probe', 'exfat_capture_probe']:
        executable = build / 'Release' / (name + '.exe')
        save(out / (architecture + '-' + name + '-artifact.json'), dict(path=str(executable), bytes=executable.stat().st_size, sha256=sha(executable)))
        for mode in ['headers', 'imports', 'dependents']:
            run(architecture + '-' + name + '-' + mode, [dumpbin, '/' + mode, executable])
    objects = [p for target in targets if target.endswith('_headers')
        for p in (build / (target + '.dir') / 'Release').glob('*.obj')]
    assert len(objects) == 4
    save(out / (architecture + '-headers.json'), [dict(path=str(p), sha256=sha(p)) for p in objects])
run('tooling', [sys.executable, '-X', 'utf8', '-m', 'unittest', 'discover', '-s', 'spec/tools/tests', '-v'])
tooling = (out / 'tooling.log').read_text(encoding='utf8')
assert 'Ran 242 tests' in tooling and 'OK (skipped=2)' in tooling
specctl = [sys.executable, '-X', 'utf8', 'spec/tools/specctl.py']
for name, options in [('spec-check', ['check']), ('index', ['index', '--check']), ('manifest', ['verify-manifest'])]:
    run(name, specctl + options)
run('source-map', [sys.executable, '-X', 'utf8', 'tools/check-source-map.py'])
run('context', specctl + ['context', '--work', 'DE-W074', '--output', out / 'context', '--byte-budget', '1200000'])
run('verify-context', specctl + ['verify-context', out / 'context'])
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=clone).strip()
assert all(sha(clone / p) == digest for p, digest in inputs.items())
save(out / 'summary.json', dict(status='pass', source_revision=revision, source_state='clean_sparse',
    architectures=['x64', 'Win32'], native_groups_per_architecture=5, headers_per_architecture=4,
    tree_cases_per_architecture=44, tooling_tests_run=242, tooling_tests_skipped=2,
    scope='Private validated tree limits copy and supplied-reader regression delta',
    full_native_suite_fresh=False, full_product_win32_qualified=False, owner_accepted=False,
    prerequisite_full_campaign='e7e3297f6ef707628b607597bb8f7e2d6d76659a; requires independently retained successful terminal result'))
save(out / 'current-stage.json', dict(stage='complete', status='pass', source_revision=revision))
