"""Prepare the DE-W105 Win32 fixture from fresh CMake metadata; never build/run it."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import re

PROBES = ('ntfs_file_probe', 'ntfs_file_fault', 'ntfs_capture_probe',
          'ntfs_names_probe', 'ntfs_stream_probe', 'ntfs_worker_probe',
          'ntfs_worker_fault', 'ntfs_upcase_probe', 'ntfs_inspection_probe')
VARIANTS = ('disked_ntfs_file', 'disked_ntfs_file_fault', 'disked_ntfs_snapshot',
            'disked_ntfs_snapshot_fault', 'disked_ntfs_worker', 'disked_ntfs_worker_fault',
            'disked_observation_worker', 'disked_observation_worker_fault')
HEADERS = ('portable/ntfs/ntfs.h', 'runtime/capture/ntfs_membership.h',
           'runtime/capture/ntfs_membership_detail.h', 'runtime/capture/ntfs_name_order.h',
           'runtime/capture/ntfs_names.h', 'runtime/capture/ntfs_attributes_detail.h',
           'runtime/capture/ntfs_capture.h', 'providers/image/ntfs_file.h',
           'runtime/capture/ntfs_directory.h', 'runtime/capture/ntfs_directory_detail.h',
           'providers/image/ntfs_snapshot.h', 'platform/windows/storage/ntfs_worker.h')
TESTS = {
    'name_order_file': ('file', 'fault', 'pure', 'inspection'),
    'name_order_worker': ('worker', 'worker_fault', 'pure'),
    'name_order': ('capture_probe',),
    'upcase_file': ('file', 'fault', 'pure', 'inspection'),
    'upcase_worker': ('worker', 'worker_fault', 'pure'),
    'upcase_capture': ('capture_probe',),
    'membership_worker': ('worker', 'worker_fault', 'pure'),
    'membership_file': ('file', 'fault', 'pure'),
    'membership': ('capture_probe',), 'names': ('names',), 'capture': ('capture_probe',),
    'stream': ('stream',), 'directory': ('capture_probe',), 'closure': ('capture', 'join'),
    'file': ('file', 'fault'), 'directory_file': ('file', 'fault', 'pure'),
    'worker': ('worker', 'worker_fault'), 'directory_worker': ('worker', 'worker_fault'),
}
ARGUMENTS = {
    'file': ('--probe', 'ntfs_file_probe'), 'fault': ('--fault', 'ntfs_file_fault'),
    'pure': ('--pure', 'ntfs_capture_probe'), 'capture_probe': ('--probe', 'ntfs_capture_probe'),
    'inspection': ('--inspection', 'ntfs_inspection_probe'),
    'worker': ('--probe', 'ntfs_worker_probe'), 'worker_fault': ('--fault', 'ntfs_worker_fault'),
    'names': ('--probe', 'ntfs_names_probe'), 'stream': ('--probe', 'ntfs_stream_probe'),
    'capture': ('--capture', 'ntfs_capture_probe'), 'join': ('--join', 'ntfs_stream_probe'),
}
OUTPUT_LIMIT = 128 * 1024
INPUT_FILE_LIMIT = 8 * 1024 * 1024
TOTAL_INPUT_LIMIT = 32 * 1024 * 1024


class FixtureError(ValueError):
    pass


def inside(path, boundary):
    path, boundary = Path(path), Path(boundary).resolve()
    current = path.absolute()
    while True:
        try:
            info = current.lstat()
            if current.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
                raise FixtureError('Linked input/output path: ' + str(current))
        except FileNotFoundError:
            pass
        if current.parent == current:
            break
        current = current.parent
    full = path.resolve()
    if not full.is_relative_to(boundary) or full == boundary:
        raise FixtureError('Path outside its allowed directory: ' + str(path))
    return full


def quote(path):
    text = Path(path).as_posix()
    if any(c in text for c in '\x00\r\n";$[]'):
        raise FixtureError('Unsupported CMake path characters: ' + text)
    return '"' + text + '"'


def prepare(root, build, output, work):
    root, build = Path(root).resolve(), Path(build).resolve()
    if work is None:
        raise FixtureError('DISKED_WORK_ROOT is required; no output created')
    work = Path(work).resolve()
    marker = inside(work / 'owner.json', work)
    if not marker.is_file() or marker.stat().st_size > 4096:
        raise FixtureError('Owned workspace marker required')
    if Path(json.loads(marker.read_bytes())['root']).resolve() != root:
        raise FixtureError('Workspace belongs to another source checkout')
    if work == root or work.is_relative_to(root):
        raise FixtureError('Managed work must be outside the source checkout')
    output = inside(Path(output).absolute(), work)
    if output.is_relative_to(root) or output.exists():
        raise FixtureError('Output must be a fresh managed directory outside the checkout')
    build = inside(build, work)
    inputs, cached_reads, total_input_bytes = {}, {}, 0

    def read(path, boundary):
        nonlocal total_input_bytes
        path = inside(path, boundary)
        if path in cached_reads:
            return cached_reads[path]
        if not path.is_file() or path.stat().st_size > INPUT_FILE_LIMIT:
            raise FixtureError('Missing or oversized required input: ' + str(path))
        with path.open('rb') as stream:
            data = stream.read(INPUT_FILE_LIMIT + 1)
        if len(data) > INPUT_FILE_LIMIT:
            raise FixtureError('Input grew beyond its byte budget: ' + str(path))
        if str(path) not in inputs:
            total_input_bytes += len(data)
        if total_input_bytes > TOTAL_INPUT_LIMIT:
            raise FixtureError('Complete fixture inputs exceed 32 MiB')
        inputs[str(path)] = 'sha256:' + hashlib.sha256(data).hexdigest()
        cached_reads[path] = data
        return data

    reply = build / '.cmake/api/v1/reply'
    indexes = sorted(reply.glob('index-*.json'))
    if not indexes:
        raise FixtureError('Fresh CMake File API index required; old build metadata is not recreated')
    index = json.loads(read(indexes[-1], build))
    models = [x for x in index.get('objects', []) if x.get('kind') == 'codemodel'
              and x.get('version', {}).get('major') == 2]
    if len(models) != 1:
        raise FixtureError('Exactly one codemodel v2 response is required')
    model = json.loads(read(reply / models[0]['jsonFile'], reply))
    if Path(model['paths']['source']).resolve() != root or Path(model['paths']['build']).resolve() != build:
        raise FixtureError('CMake metadata belongs to another source/build directory')
    configs = [x for x in model['configurations'] if x.get('name') == 'Release']
    if len(configs) != 1:
        raise FixtureError('Exactly one Release configuration is required')
    records = configs[0]['targets']
    if len(records) > 4096:
        raise FixtureError('CMake target-count budget exceeded')
    by_id, by_name = {x['id']: x for x in records}, {x['name']: x for x in records}
    if len(by_id) != len(records) or len(by_name) != len(records):
        raise FixtureError('Duplicate CMake target identity')
    cache, own_cache, closure_cache = {}, {}, {}

    def target(name):
        if name not in by_name:
            raise FixtureError('Required target missing: ' + name)
        if name not in cache:
            cache[name] = json.loads(read(reply / by_name[name]['jsonFile'], reply))
        return cache[name]

    def own(name):
        if name in own_cache:
            return own_cache[name]
        result = set()
        for item in target(name).get('sources', []):
            path = Path(item['path'])
            if path.suffix not in ('.c', '.cpp'):
                continue
            if not path.is_absolute():
                path = root / path
            path = inside(path, root)
            read(path, root)
            result.add(path)
        own_cache[name] = result
        return result

    def dependencies(name):
        result = []
        for edge in target(name).get('dependencies', []):
            if edge['id'] not in by_id:
                raise FixtureError('Missing target dependency: ' + edge['id'])
            result.append(by_id[edge['id']]['name'])
        return result

    def closure(name, pending=()):
        if len(pending) > 128:
            raise FixtureError('Target dependency depth budget exceeded')
        if name in pending:
            raise FixtureError('Cyclic target dependency: ' + name)
        if name in closure_cache:
            return closure_cache[name]
        result = set(own(name))
        for child in dependencies(name):
            result |= closure(child, pending + (name,))
        closure_cache[name] = result
        return result

    def definitions(name):
        values = sorted({d['define'] for g in target(name).get('compileGroups', [])
                         for d in g.get('defines', [])} - {'WIN32', '_WINDOWS', 'NDEBUG'})
        if any(not re.fullmatch(r'[A-Za-z_]\w*(?:=[A-Za-z0-9_.+\-]+)?', d) for d in values):
            raise FixtureError('Unsupported compile definition: ' + name)
        return values

    probes, variants = {n: own(n) for n in PROBES}, {n: own(n) for n in VARIANTS}
    if any(not files for files in probes.values()) or any(len(files) != 1 for files in variants.values()):
        raise FixtureError('Probe/variant source ownership is incomplete')
    if any(not p.is_relative_to(root / 'tests') for files in probes.values() for p in files):
        raise FixtureError('A probe contains production sources')
    if any(not p.is_relative_to(root / 'source') for files in variants.values() for p in files):
        raise FixtureError('A variant source is outside source/')
    common = set.union(*(closure(n) for n in PROBES)) - set.union(*probes.values()) - set.union(*variants.values())
    if not common or any(not p.is_relative_to(root / 'source') for p in common):
        raise FixtureError('Common fixture sources have invalid ownership')
    for name in VARIANTS:
        if bool([d for d in definitions(name) if d.startswith('DISKED_')]) != name.endswith('_fault'):
            raise FixtureError('Normal/fault definitions do not match their variant: ' + name)
    profile_path = root / 'spec/catalog/native-bootstrap.json'
    profile = json.loads(read(profile_path, root))
    for field in ('compiler_version', 'toolset', 'sdk'):
        if not re.fullmatch(r'[0-9]+(?:\.[0-9]+)+', profile[field]):
            raise FixtureError('Invalid pinned build profile: ' + field)
    if profile.get('language') != 'C++14' or profile.get('crt') != 'static-release-MT':
        raise FixtureError('Unsupported source compiler/runtime profile')
    gate = root / 'tools/workspace.cmake'
    read(gate, root)
    for header in HEADERS:
        read(root / 'source' / header, root)
    for kind in TESTS:
        read(root / 'tests/images' / ('test_ntfs_' + kind + '.py'), root)

    lines = ['cmake_minimum_required(VERSION 3.27)', 'include(' + quote(gate) + ')',
             'project(NtfsReaderWin32Fixture LANGUAGES C CXX)',
             'set(CMAKE_CONFIGURATION_TYPES Release CACHE STRING "Fixture profile" FORCE)',
             'set(CMAKE_MSVC_RUNTIME_LIBRARY MultiThreaded)',
             'set(CMAKE_C_STANDARD 90)', 'set(CMAKE_C_STANDARD_REQUIRED YES)', 'set(CMAKE_C_EXTENSIONS NO)',
             'set(CMAKE_CXX_STANDARD 14)', 'set(CMAKE_CXX_STANDARD_REQUIRED YES)', 'set(CMAKE_CXX_EXTENSIONS NO)',
             'if(NOT MSVC OR NOT CMAKE_SIZEOF_VOID_P EQUAL 4 OR NOT CMAKE_VS_PLATFORM_NAME STREQUAL "Win32"',
             ' OR NOT CMAKE_CXX_COMPILER_VERSION VERSION_EQUAL "' + profile['compiler_version'] + '"',
             ' OR NOT CMAKE_VS_WINDOWS_TARGET_PLATFORM_VERSION STREQUAL "' + profile['sdk'] + '")',
             'message(FATAL_ERROR "Pinned Win32 compiler and SDK required")', 'endif()',
             'find_package(Python3 REQUIRED COMPONENTS Interpreter)', 'enable_testing()',
             'add_library(ntfs_fixture STATIC ' + ' '.join(quote(p) for p in sorted(common)) + ')']

    def options(name, defines=()):
        lines.extend(['target_include_directories(' + name + ' PRIVATE ' + quote(root / 'source') + ')',
                      'target_compile_definitions(' + name + ' PRIVATE _WIN32_WINNT=0x0A00 ' + ' '.join(defines) + ')',
                      'target_compile_options(' + name + ' PRIVATE /W4 /WX /GS /sdl /guard:cf '
                      '"$<$<COMPILE_LANGUAGE:CXX>:/permissive-;/utf-8>")'])

    options('ntfs_fixture')
    for name, files in variants.items():
        lines.append('add_library(' + name + ' STATIC ' + ' '.join(quote(p) for p in sorted(files)) + ')')
        deps = sorted(set(dependencies(name)) & set(VARIANTS))
        lines.append('target_link_libraries(' + name + ' PUBLIC ntfs_fixture ' + ' '.join(deps) + ' advapi32)')
        options(name, definitions(name))
    for name, files in probes.items():
        dep = {'ntfs_file_probe': 'disked_ntfs_file', 'ntfs_file_fault': 'disked_ntfs_file_fault',
               'ntfs_worker_probe': 'disked_ntfs_worker', 'ntfs_worker_fault': 'disked_ntfs_worker_fault'}.get(name, 'ntfs_fixture')
        lines.extend(['add_executable(' + name + ' ' + ' '.join(quote(p) for p in sorted(files)) + ')',
                      'target_link_libraries(' + name + ' PRIVATE ' + dep + ' advapi32)',
                      'target_link_options(' + name + ' PRIVATE /DYNAMICBASE /NXCOMPAT /guard:cf)'])
        options(name, definitions(name))
    generated = {'header-' + str(i) + '.cpp': ('#include "' + h + '"\n').encode() for i, h in enumerate(HEADERS)}
    lines.append('add_library(ntfs_fixture_headers OBJECT ' + ' '.join(quote(output / n) for n in generated) + ')')
    options('ntfs_fixture_headers')
    for kind, aliases in TESTS.items():
        args = []
        for alias in aliases:
            flag, name = ARGUMENTS[alias]
            args += [flag, '"$<TARGET_FILE:' + name + '>"']
        lines.append('add_test(NAME image.ntfs_' + kind + ' COMMAND "${Python3_EXECUTABLE}" '
                     + quote(root / 'tests/images' / ('test_ntfs_' + kind + '.py')) + ' ' + ' '.join(args)
                     + ' --output "${CMAKE_BINARY_DIR}/ntfs-' + kind.replace('_', '-') + '-cases.json")')
        lines.append('set_tests_properties(image.ntfs_' + kind + ' PROPERTIES TIMEOUT 240 RESOURCE_LOCK disked_fake_workers)')
    generated['CMakeLists.txt'] = ('\n'.join(lines) + '\n').encode('utf-8')
    result = dict(status='prepared_not_qualified', work_id='DE-W105', source_root=str(root),
                  codemodel_build=str(build), tests=['image.ntfs_' + k for k in TESTS],
                  executable_targets=list(PROBES), standalone_headers=list(HEADERS),
                  inputs=inputs, compiler_profile={k: profile[k] for k in
                      ('compiler_version', 'toolset', 'sdk', 'language', 'crt')},
                  compiler_profile_source=str(profile_path), fixture_architecture='Win32',
                  native_execution_performed=False,
                  generator_sha256='sha256:' + hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                  generated_files={n: 'sha256:' + hashlib.sha256(b).hexdigest() for n, b in generated.items()},
                  binding_scope='Fixture generation only; full work-unit/test-helper inputs still required for execution.',
                  execution_input_closure_complete=False,
                  owner_accepted=False, hard_storage_boundary_demonstrated=False)
    generated['fixture-inputs.json'] = (json.dumps(result, indent=2) + '\n').encode('utf-8')
    if sum(map(len, generated.values())) > OUTPUT_LIMIT:
        raise FixtureError('Complete fixture output exceeds 128 KiB; nothing written')
    output.mkdir(parents=True)
    for name, data in generated.items():
        (output / name).write_bytes(data)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--build', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.root, args.build, args.output, os.environ.get('DISKED_WORK_ROOT'))
    except (FixtureError, OSError, ValueError, KeyError) as error:
        parser.exit(2, 'Fixture preparation refused: ' + str(error) + '\n')
    print(json.dumps(dict(status=result['status'], output=str(args.output), native_execution_performed=False)))


if __name__ == '__main__':
    main()
