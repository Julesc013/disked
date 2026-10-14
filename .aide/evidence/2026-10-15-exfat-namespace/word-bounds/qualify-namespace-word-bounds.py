"""Rebuild only the supplied-data namespace closure for native x64/x86 checks."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

parser = argparse.ArgumentParser()
parser.add_argument('--source', type=Path, required=True)
parser.add_argument('--codemodel-build', type=Path, required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--cases', type=Path, required=True)
parser.add_argument('--revision', required=True)
args = parser.parse_args()
root = args.source.resolve()
repository = root
out = args.output.resolve()
out.mkdir(exist_ok=False)
logs = out / 'logs'
logs.mkdir()
commands = []
def save(path, value):
    path.write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')
def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
def run(name, argv, cwd=out, success=True, data=None):
    argv = list(map(str, argv))
    start = time.monotonic()
    with (logs / (name + '.log')).open('wb') as log:
        result = subprocess.run(argv, cwd=cwd, input=data, stdout=log, stderr=subprocess.STDOUT)
    commands.append(dict(name=name, argv=argv, cwd=str(cwd), exit_code=result.returncode,
        elapsed_seconds=round(time.monotonic() - start, 3), log='logs/' + name + '.log'))
    save(out / 'commands.json', commands)
    print(name + ': exit ' + str(result.returncode), flush=True)
    if success and result.returncode:
        raise SystemExit(result.returncode)
    return result.returncode

qualification = json.loads((args.codemodel_build.parent / 'current-stage.json').read_bytes())
assert qualification['status'] == 'pass' and qualification['stage'] == 'complete'
revision = subprocess.check_output(['git', 'rev-parse', args.revision], cwd=repository, text=True).strip()
case_path = args.cases.resolve().relative_to(repository).as_posix()
runner_path = Path(__file__).resolve().relative_to(repository).as_posix()
root = out / 'source'
run('clone', ['git', 'clone', '--local', '--no-hardlinks', '--no-checkout', repository, root], cwd=repository)
patterns = ['/source/', '/tests/property/', '/tests/unit/exfat_namespace_probe.cpp',
    '/CMakeLists.txt', '/AGENTS.md', '/.gitattributes', '/.gitignore',
    '/spec/catalog/native-bootstrap.json', '/' + case_path, '/' + runner_path]
run('sparse-selection', ['git', 'sparse-checkout', 'set', '--no-cone', '--stdin'],
    cwd=root, data=('\n'.join(patterns) + '\n').encode())
run('checkout', ['git', 'checkout', '--detach', revision], cwd=root)
assert not subprocess.check_output(['git', 'status', '--porcelain'], cwd=root).strip()
assert sha(Path(__file__)) == sha(root / runner_path)
assert sha(args.cases) == sha(root / case_path)
reference_inputs = json.loads((args.codemodel_build.parent / 'source-inputs.json').read_bytes())
assert sha(root / 'CMakeLists.txt') == reference_inputs['CMakeLists.txt']

reply = args.codemodel_build.resolve() / '.cmake/api/v1/reply'
index = json.loads(sorted(reply.glob('index-*.json'))[-1].read_bytes())
model_file = index['reply']['codemodel-v2']['jsonFile']
model = json.loads((reply / model_file).read_bytes())
configuration = next(row for row in model['configurations'] if row['name'] == 'Release')
targets = {row['id']: row for row in configuration['targets']}
start = next(row['id'] for row in targets.values() if row['name'] == 'disked_exfat_namespace')
queue, visited, source_names, source_targets = [start], set(), set(), {}
while queue:
    target_id = queue.pop()
    if target_id in visited:
        continue
    visited.add(target_id)
    reference = targets[target_id]
    target = json.loads((reply / reference['jsonFile']).read_bytes())
    assert target['type'] == 'STATIC_LIBRARY', target['name']
    names = []
    for source in target.get('sources', []):
        name = source['path']
        if Path(name).suffix not in ['.c', '.cpp']:
            continue
        assert not source.get('isGenerated'), name
        path = Path(name)
        if path.is_absolute():
            # Resolve the immutable reference checkout's relative source path.
            path = path.relative_to(Path(model['paths']['source']))
        name = path.as_posix()
        assert name.startswith('source/') and '..' not in path.parts, name
        assert (root / name).is_file(), name
        names.append(name)
        source_names.add(name)
    source_targets[target['name']] = sorted(names)
    queue += [row['id'] for row in target.get('dependencies', [])]
assert set(source_targets) == {'disked_exfat_namespace', 'disked_exfat_upcase',
    'disked_exfat', 'disked_primitives', 'disked_hash', 'disked_json'}, source_targets
source_names.add('tests/unit/exfat_namespace_probe.cpp')
tracked = set(source_names)
for folder in ['source/runtime/capture', 'source/runtime/command',
               'source/portable/exfat', 'source/portable/primitives', 'source/portable/hash']:
    tracked.update(p.relative_to(root).as_posix() for p in (root / folder).glob('*.h'))
tracked.update(['tests/property/test_exfat_namespace.py',
    'tests/property/test_exfat_upcase.py', 'tests/property/exfat_directory_vectors.py'])
inputs = {name: sha(root / name) for name in sorted(tracked)}
assert all(inputs[name] == reference_inputs[name] for name in tracked
    if name != 'tests/unit/exfat_namespace_probe.cpp')
save(out / 'source-inputs.json', inputs)
save(out / 'derived-source-targets.json', source_targets)
shutil.copyfile(args.cases, out / 'namespace-size-cases.py')
shutil.copyfile(Path(__file__), out / 'qualify-namespace-word-bounds.py')
project = out / 'project'
project.mkdir()
def quote(path):
    value = str(path).replace('\\', '/')
    assert not any(c in value for c in ['"', ';', '\n', '\r'])
    return '"' + value + '"'
for basename in ['exfat_upcase', 'exfat_namespace']:
    (project / (basename + '.cpp')).write_text(
        '#include "runtime/capture/' + basename + '.h"\n', encoding='utf-8')
cmake = '''cmake_minimum_required(VERSION 3.27)
project(NamespaceWordBounds LANGUAGES C CXX)
set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)
if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL EXPECTED_POINTER_BYTES
   OR NOT CMAKE_CXX_COMPILER_VERSION VERSION_EQUAL "19.44.35228.0"
   OR NOT CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION STREQUAL "10.0.19041.0")
  message(FATAL_ERROR "Pinned compiler/SDK required")
endif()
add_executable(exfat_namespace_probe
'''
cmake += '\n'.join('  ' + quote(root / name) for name in sorted(source_names))
cmake += '\n  exfat_upcase.cpp\n  exfat_namespace.cpp)\n'
cmake += 'target_include_directories(exfat_namespace_probe PRIVATE ' + quote(root / 'source') + ')\n'
cmake += '''set_target_properties(exfat_namespace_probe PROPERTIES C_STANDARD 90 C_STANDARD_REQUIRED YES C_EXTENSIONS NO
  CXX_STANDARD 14 CXX_STANDARD_REQUIRED YES CXX_EXTENSIONS NO)
target_compile_options(exfat_namespace_probe PRIVATE /W4 /WX /GS /sdl /guard:cf
  "$<$<COMPILE_LANGUAGE:CXX>:/permissive-;/utf-8>")
target_link_options(exfat_namespace_probe PRIVATE /guard:cf /DYNAMICBASE /NXCOMPAT)
'''
(project / 'CMakeLists.txt').write_text(cmake, encoding='utf-8', newline='\n')
run('cmake-version', ['cmake', '--version'])
identity = json.loads((args.codemodel_build / 'generated/build-identity.json').read_bytes())
dumpbin = Path(identity['compiler_path']).with_name('dumpbin.exe')
results, artifacts = [], []
for architecture, bits in [('x64', 64), ('Win32', 32)]:
    build = out / architecture
    run(architecture + '-configure', ['cmake', '-S', project, '-B', build,
        '-G', 'Visual Studio 17 2022', '-A', architecture + ',version=10.0.19041.0',
        '-T', 'v143,version=14.44.35207,host=x64', '-DEXPECTED_POINTER_BYTES=' + str(bits // 8)])
    run(architecture + '-build', ['cmake', '--build', build, '--config', 'Release', '--parallel', '4'])
    binary = build / 'Release/exfat_namespace_probe.exe'
    run(architecture + '-namespace', [sys.executable, root / 'tests/property/test_exfat_namespace.py',
        '--probe', binary, '--output', out / (architecture + '-namespace.json')])
    run(architecture + '-word-bounds', [sys.executable, out / 'namespace-size-cases.py',
        '--source', root, '--probe', binary, '--pointer-bits', bits,
        '--output', out / (architecture + '-word-bounds.json')])
    cases = json.loads((out / (architecture + '-namespace.json')).read_bytes())
    bounds = json.loads((out / (architecture + '-word-bounds.json')).read_bytes())
    assert cases['passed'] and cases['cases'] == 303 and cases['methods'] == 12
    assert bounds['passed'] and bounds['cases'] == 13 and bounds['pointer_bits'] == bits
    for mode in ['headers', 'imports', 'dependents']:
        run(architecture + '-' + mode, [dumpbin, '/' + mode, binary])
    for suffix in ['Compiler.cmake']:
        for p in (build / 'CMakeFiles').rglob('CMake*' + suffix):
            shutil.copyfile(p, out / (architecture + '-' + p.name))
    shutil.copyfile(build / 'CMakeCache.txt', out / (architecture + '-CMakeCache.txt'))
    artifacts.append(dict(path=str(binary), sha256=sha(binary), bytes=binary.stat().st_size))
    results.append(dict(architecture=architecture, pointer_bits=bits, namespace_cases=303,
        namespace_methods=12, word_boundary_cases=13, standalone_headers=2))
assert all(sha(root / name) == value for name, value in inputs.items())
baseline = out / 'baseline-project'
baseline.mkdir()
old_probe = subprocess.check_output(['git', 'show', qualification['source_revision'] +
    ':tests/unit/exfat_namespace_probe.cpp'], cwd=repository)
(baseline / 'legacy_probe.cpp').write_bytes(old_probe)
for basename in ['exfat_upcase', 'exfat_namespace']:
    shutil.copyfile(project / (basename + '.cpp'), baseline / (basename + '.cpp'))
probe_path = quote(root / 'tests/unit/exfat_namespace_probe.cpp')
assert cmake.count(probe_path) == 1
(baseline / 'CMakeLists.txt').write_text(cmake.replace(probe_path, quote(baseline / 'legacy_probe.cpp')),
    encoding='utf-8', newline='\n')
baseline_build = out / 'baseline-Win32'
run('baseline-configure', ['cmake', '-S', baseline, '-B', baseline_build,
    '-G', 'Visual Studio 17 2022', '-A', 'Win32,version=10.0.19041.0',
    '-T', 'v143,version=14.44.35207,host=x64', '-DEXPECTED_POINTER_BYTES=4'])
run('baseline-build', ['cmake', '--build', baseline_build, '--config', 'Release', '--parallel', '4'])
baseline_binary = baseline_build / 'Release/exfat_namespace_probe.exe'
run('baseline-word-bounds', [sys.executable, out / 'namespace-size-cases.py', '--source', root,
    '--probe', baseline_binary, '--pointer-bits', '32', '--output', out / 'baseline-word-bounds.json',
    '--observe-baseline'])
baseline_result = json.loads((out / 'baseline-word-bounds.json').read_bytes())
assert not baseline_result['passed']
assert any(row['case'] == 6 and row['actual'] == 'unique' for row in baseline_result['differences'])
assert any(row['case'] == 10 and row['actual'] == 'unique' for row in baseline_result['differences'])
save(out / 'baseline-source.json', dict(probe_revision=qualification['source_revision'],
    probe_sha256='sha256:' + hashlib.sha256(old_probe).hexdigest(),
    other_source_revision=revision, kernel_inputs_unchanged_from_probe_revision=True,
    scope='Old private probe input conversion measured against unchanged namespace kernel',
    binary_sha256=sha(baseline_binary)))
save(out / 'summary.json', dict(status='pass', source_root=str(root), source_inputs_unchanged=True,
    source_revision=revision, original_full_campaign_revision=qualification['source_revision'],
    campaigns=results, artifacts=artifacts, source_selection='Derived six-library actual CMake codemodel closure',
    baseline_mismatches_observed=len(baseline_result['differences']),
    product_rebuilt=False, full_x86_product_qualified=False, owner_accepted=False,
    full_0_1_0_complete=False))
print('Word-boundary campaigns completed.', flush=True)
