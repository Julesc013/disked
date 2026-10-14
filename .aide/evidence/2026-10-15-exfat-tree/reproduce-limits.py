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


run('worktree', ['git', 'worktree', 'add', '--detach', '--no-checkout', clone, revision], root)
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
targets = ['bootstrap_registry', 'exfat_tree_probe', 'exfat_namespace_probe', 'exfat_capture_probe',
    'disked_exfat_tree_headers', 'disked_exfat_namespace_headers', 'disked_exfat_capture_headers', 'disked_exfat_upcase_headers']
for architecture in ['x64', 'Win32']:
    build = out / architecture
    if architecture == 'x64':
        run(architecture + '-configure', ['cmake', '--preset', 'windows-bootstrap',
            '-B', build, '-DPython3_EXECUTABLE=' + sys.executable])
        run(architecture + '-build', ['cmake', '--build', build, '--config', 'Release', '--target', *targets, '--parallel', '4'])
        run(architecture + '-native', ['ctest', '--test-dir', build, '-C', 'Release', '-R',
            '^(image.exfat_(tree|namespace|capture)|build.boundaries|recovery.gpt_fixture_harness)$',
            '--output-on-failure', '--output-junit', out / (architecture + '-junit.xml')])
        junit = ET.parse(out / (architecture + '-junit.xml')).getroot()
        assert len(list(junit.iter('testcase'))) == 5
        assert not any(list(junit.iter(k)) for k in ['failure', 'error', 'skipped'])
        identity = json.loads((build / 'generated/build-identity.json').read_bytes())
        dumpbin = Path(identity['compiler_path']).with_name('dumpbin.exe')
        shutil.copyfile(build / 'generated/build-identity.json', out / 'x64-build-identity.json')
        # Derive the fixture closure from this revision's actual CMake graph.
        reply = build / '.cmake/api/v1/reply'
        index = json.loads(sorted(reply.glob('index-*.json'))[-1].read_bytes())
        model = json.loads((reply / index['reply']['codemodel-v2']['jsonFile']).read_bytes())
        config = next(row for row in model['configurations'] if row['name'] == 'Release')
        nodes = {row['id']: json.loads((reply / row['jsonFile']).read_bytes()) for row in config['targets']}
        queue = [key for key, row in nodes.items() if row['name'] == 'disked_exfat_tree']
        source_targets = {}
        while queue:
            node = nodes[queue.pop()]
            if node['name'] in source_targets:
                continue
            names = [row['path'] for row in node.get('sources', []) if row['path'].endswith(('.c', '.cpp'))]
            assert all(name.startswith('source/') and '..' not in Path(name).parts for name in names)
            source_targets[node['name']] = names
            queue += [row['id'] for row in node.get('dependencies', [])]
        assert set(source_targets) == {'disked_exfat_tree', 'disked_exfat_capture', 'disked_exfat_namespace',
            'disked_exfat_upcase', 'disked_exfat', 'disked_primitives', 'disked_hash', 'disked_json'}
        save(out / 'fixture-source-targets.json', source_targets)
        project = out / 'Win32-fixtures'
        project.mkdir()
        def quote(path):
            text = str(path).replace('\\', '/')
            assert not any(c in text for c in ['"', ';', '\n', '\r'])
            return '"' + text + '"'
        cmake = '''cmake_minimum_required(VERSION 3.27)
project(ExfatTreePrivateFixtures LANGUAGES C CXX)
set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)
if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4
   OR NOT CMAKE_CXX_COMPILER_VERSION VERSION_EQUAL "19.44.35228.0"
   OR NOT CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION STREQUAL "10.0.19041.0")
  message(FATAL_ERROR "Pinned Win32 fixture compiler/SDK required")
endif()
'''
        sources = sorted({name for names in source_targets.values() for name in names})
        for name, probe in [('exfat_tree_probe', 'tests/unit/exfat_tree_probe.cpp'),
                            ('exfat_namespace_probe', 'tests/unit/exfat_namespace_probe.cpp'),
                            ('exfat_capture_probe', 'tests/unit/exfat_capture_probe.cpp')]:
            assert (clone / probe).is_file()
            cmake += 'add_executable(' + name + '\n' + '\n'.join('  ' + quote(clone / p) for p in sources + [probe]) + ')\n'
            cmake += 'target_include_directories(' + name + ' PRIVATE ' + quote(clone / 'source') + ')\n'
            cmake += 'set_target_properties(' + name + ' PROPERTIES C_STANDARD 90 C_STANDARD_REQUIRED YES C_EXTENSIONS NO CXX_STANDARD 14 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)\n'
            cmake += 'target_compile_options(' + name + ' PRIVATE /W4 /WX /GS /sdl /guard:cf "$<$<COMPILE_LANGUAGE:CXX>:/permissive-;/utf-8>")\n'
            cmake += 'target_link_options(' + name + ' PRIVATE /guard:cf /DYNAMICBASE /NXCOMPAT)\n'
        headers = ['exfat_tree', 'exfat_namespace', 'exfat_capture', 'exfat_upcase']
        for name in headers:
            (project / (name + '.cpp')).write_text('#include "runtime/capture/' + name + '.h"\n', encoding='utf8')
        cmake += 'add_library(exfat_headers OBJECT ' + ' '.join(name + '.cpp' for name in headers) + ')\n'
        cmake += 'target_include_directories(exfat_headers PRIVATE ' + quote(clone / 'source') + ')\n'
        cmake += 'set_target_properties(exfat_headers PROPERTIES CXX_STANDARD 14 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)\n'
        cmake += 'target_compile_options(exfat_headers PRIVATE /W4 /WX /permissive- /utf-8 /GS /sdl /guard:cf)\n'
        (project / 'CMakeLists.txt').write_text(cmake, encoding='utf8', newline='\n')
    else:
        run('Win32-configure', ['cmake', '-S', project, '-B', build, '-G', 'Visual Studio 17 2022',
            '-A', 'Win32,version=10.0.19041.0', '-T', 'v143,version=14.44.35207,host=x64'])
        run('Win32-build', ['cmake', '--build', build, '--config', 'Release', '--parallel', '4'])
        for label, script, binary in [('tree', 'tests/images/test_exfat_tree.py', 'exfat_tree_probe'),
            ('namespace', 'tests/property/test_exfat_namespace.py', 'exfat_namespace_probe'),
            ('capture', 'tests/images/test_exfat_capture.py', 'exfat_capture_probe')]:
            run('Win32-' + label, [sys.executable, clone / script, '--probe', build / 'Release' / (binary + '.exe'),
                '--output', build / ('exfat-' + label + '-cases.json')])
        shutil.copyfile(build / 'CMakeCache.txt', out / 'Win32-CMakeCache.txt')
        for path in (build / 'CMakeFiles').rglob('CMake*Compiler.cmake'):
            shutil.copyfile(path, out / ('Win32-' + path.name))
    for name in ['exfat-tree-cases.json', 'exfat-namespace-cases.json', 'exfat-capture-cases.json']:
        shutil.copyfile(build / name, out / (architecture + '-' + Path(name).name))
    tree = json.loads((build / 'exfat-tree-cases.json').read_bytes())
    assert tree['passed'] and tree['cases'] == 44 and tree['methods'] == 10
    for name in ['exfat_tree_probe', 'exfat_namespace_probe', 'exfat_capture_probe']:
        executable = build / 'Release' / (name + '.exe')
        save(out / (architecture + '-' + name + '-artifact.json'), dict(path=str(executable), bytes=executable.stat().st_size, sha256=sha(executable)))
        for mode in ['headers', 'imports', 'dependents']:
            run(architecture + '-' + name + '-' + mode, [dumpbin, '/' + mode, executable])
    objects = ([p for target in targets if target.endswith('_headers')
        for p in (build / (target + '.dir') / 'Release').glob('*.obj')] if architecture == 'x64'
        else list((build / 'exfat_headers.dir/Release').glob('*.obj')))
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
    architectures=['x64', 'Win32'], native_groups={'x64': 5, 'Win32_fixture_only': 3}, headers_per_architecture=4,
    tree_cases_per_architecture=44, tooling_tests_run=242, tooling_tests_skipped=2,
    scope='Private validated tree limits copy and supplied-reader regression delta',
    full_native_suite_fresh=False, full_product_win32_qualified=False, owner_accepted=False,
    prerequisite_full_campaign='e7e3297f6ef707628b607597bb8f7e2d6d76659a; requires independently retained successful terminal result'))
save(out / 'current-stage.json', dict(stage='complete', status='pass', source_revision=revision))
