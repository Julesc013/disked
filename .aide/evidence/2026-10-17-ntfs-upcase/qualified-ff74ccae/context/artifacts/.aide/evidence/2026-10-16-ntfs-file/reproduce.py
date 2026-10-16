"""Finite ordinary-file NTFS profile qualification; not the full product suite."""
import argparse
import hashlib
import json
import platform
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path


def digest(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    build = output / 'build'
    summary = dict(schema='org.disked.ntfs-file-qualification/1',
                   observed_at=datetime.now(timezone.utc).isoformat(),
                   source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                   checkout_status=subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True),
                   root=str(root), host=platform.platform(), python=sys.version,
                   scope='Selected Windows x64 ordinary-file NTFS binding/profiles, existing primitives and exFAT reader/file regressions; strict WSL C90/C++14 syntax checks. No full native suite or other-host/product qualification.',
                   stages=[], owner_accepted=False, original_failures_cleared=False,
                   full_0_1_0_complete=False, physical_devices=False)
    paths = set(json.loads((root / 'tools/build-inputs.json').read_bytes())['files'])
    paths.update(item['path'] for item in json.loads((root / 'spec/catalog/input-dependencies.json').read_bytes())['inputs'])
    paths.update(path.relative_to(root).as_posix() for path in (root / 'source').rglob('*') if path.is_file())
    before = {name: digest(root / name) for name in sorted(paths)}
    (output / 'inputs.json').write_text(json.dumps(before, indent=2) + '\n', encoding='utf-8')
    def save():
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
    def run(name, command):
        print('BEGIN', name, flush=True)
        start = time.monotonic()
        with (output / (name + '.log')).open('wb') as log:
            result = subprocess.run([str(item) for item in command], cwd=root,
                                    stdout=log, stderr=subprocess.STDOUT)
        summary['stages'].append(dict(name=name, command=[str(item) for item in command],
                                      cwd=str(root), exit_code=result.returncode,
                                      seconds=round(time.monotonic() - start, 3), log=name + '.log'))
        save()
        print('END', name, result.returncode, flush=True)
        return result.returncode == 0
    py = Path(sys.executable)
    ok = run('configure', ['cmake', '--preset', 'windows-bootstrap', '-B', build, '-DPython3_EXECUTABLE=' + str(py)])
    targets = ['bootstrap_registry', 'ntfs_file_probe', 'ntfs_file_fault', 'exfat_file_probe', 'exfat_file_fault', 'disked_ntfs_file_headers', 'disked_exfat_file_headers', 'ntfs_capture_probe', 'ntfs_attributes_probe', 'exfat_capture_probe', 'ntfs_boot_probe', 'ntfs_record_probe', 'disked_ntfs_headers', 'disked_ntfs_capture_headers', 'disked_exfat_capture_headers', 'portable_probe', 'portable_cpp',
               'gpt_probe', 'mbr_probe', 'fat_probe', 'exfat_probe']
    if ok:
        ok = run('build', ['cmake', '--build', build, '--config', 'Release', '--target', *targets, '--parallel', '4'])
    if ok:
        run('portable-regression', ['ctest', '--test-dir', build, '-C', 'Release', '--output-on-failure',
                                   '--output-junit', output / 'portable-junit.xml',
                                   '-R', r'^(image\.(ntfs_file|exfat_file|ntfs_capture|exfat_capture)|portable\.(checked|c_cpp_linkage|ntfs_record|ntfs_boot|ntfs_attributes|ntfs_runlist|gpt|gpt_guard|mbr_ebr|mbr_guard|fat|fat_guard|exfat|exfat_guard))$'])
        compiler_files = list((build / 'CMakeFiles').glob('*/CMakeCCompiler.cmake'))
        if len(compiler_files) != 1:
            raise RuntimeError('C compiler identity absent/ambiguous')
        compiler_text = compiler_files[0].read_text(encoding='utf-8')
        compiler = Path(re.search(r'set\(CMAKE_C_COMPILER "([^"]+)"\)', compiler_text)[1])
        summary['compiler'] = str(compiler)
        summary['compiler_configuration_sha256'] = digest(compiler_files[0])
        executable = build / 'Release/ntfs_file_probe.exe'
        dumpbin = compiler.with_name('dumpbin.exe')
        run('probe-imports', [dumpbin, '/DEPENDENTS', executable])
        run('probe-headers', [dumpbin, '/HEADERS', executable])
        imports = re.findall(r'^\s+([A-Za-z0-9_.-]+\.dll)\s*$', (output / 'probe-imports.log').read_text(), re.MULTILINE)
        summary['probe_imports'] = sorted(name.lower() for name in imports)
        summary['probe_import_check'] = summary['probe_imports'] == ['kernel32.dll']
        header_text = (output / 'probe-headers.log').read_text()
        summary['probe_security_check'] = all(value in header_text for value in ['8664 machine (x64)', 'magic # (PE32+)', 'Dynamic base', 'NX compatible', 'Control Flow Guard'])
        fault = build / 'Release/ntfs_file_fault.exe'
        run('fault-imports', [dumpbin, '/DEPENDENTS', fault])
        run('fault-headers', [dumpbin, '/HEADERS', fault])
        imports = re.findall(r'^\s+([A-Za-z0-9_.-]+\.dll)\s*$', (output / 'fault-imports.log').read_text(), re.MULTILINE)
        summary['fault_imports'] = sorted(name.lower() for name in imports)
        summary['fault_import_check'] = summary['fault_imports'] == ['kernel32.dll']
        header_text = (output / 'fault-headers.log').read_text()
        summary['fault_security_check'] = all(value in header_text for value in ['8664 machine (x64)', 'magic # (PE32+)', 'Dynamic base', 'NX compatible', 'Control Flow Guard'])
        summary['artifacts'] = {path.relative_to(build).as_posix(): digest(path) for path in sorted((build / 'Release').glob('*')) if path.is_file() and path.suffix.lower() in {'.exe', '.lib'}}
        cases = json.loads((build / 'ntfs-record-cases.json').read_bytes())
        summary['ntfs_record_cases'] = cases['count']
        summary['ntfs_boot_cases'] = json.loads((build / 'ntfs-boot-cases.json').read_bytes())['count']
        summary['ntfs_runlist_cases'] = json.loads((build / 'ntfs-runlist-cases.json').read_bytes())['count']
        summary['ntfs_attribute_cases'] = json.loads((build / 'ntfs-attributes-cases.json').read_bytes())['count']
        summary['ntfs_capture_cases'] = json.loads((build / 'ntfs-capture-cases.json').read_bytes())['count']
        summary['ntfs_file_result'] = json.loads((build / 'ntfs-file-cases.json').read_bytes())
        summary['ntfs_cases'] = summary['ntfs_file_result']['cases']
    run('build-boundaries', [py, 'tools/check-build-boundaries.py', '--build', build, '--output', output / 'build-boundaries.json'])
    for compiler in ('gcc', 'clang'):
        run('wsl-' + compiler + '-identity', ['wsl', '-e', compiler, '--version'])
        linux_root = '/mnt/' + root.drive[0].lower() + root.as_posix()[2:]
        run('wsl-' + compiler + '-c90', ['wsl', '-e', compiler, '-std=c90', '-pedantic-errors', '-Wall', '-Wextra', '-Werror',
                                       '-I' + linux_root + '/source', '-fsyntax-only', linux_root + '/source/portable/ntfs/record.c', linux_root + '/source/portable/ntfs/boot.c', linux_root + '/source/portable/ntfs/attribute.c', linux_root + '/source/portable/ntfs/runlist.c'])
    for compiler in ('g++', 'clang++'):
        run('wsl-' + compiler.replace('+','p') + '-cxx14', ['wsl', '-e', compiler, '-std=c++14', '-pedantic-errors', '-Wall', '-Wextra', '-Werror',
            '-I' + linux_root + '/source', '-fsyntax-only', linux_root + '/source/runtime/capture/ntfs_capture.cpp'])
    run('source-map', [py, 'tools/check-source-map.py'])
    run('index', [py, 'spec/tools/specctl.py', 'index', '--check'])
    run('structural', [py, 'spec/tools/specctl.py', 'check'])
    run('tooling', [py, '-m', 'unittest', 'discover', '-s', 'spec/tools/tests', '-v'])
    run('manifest', [py, 'spec/tools/specctl.py', 'verify-manifest'])
    context = output / 'context'
    if run('context', [py, 'spec/tools/specctl.py', 'context', '--work', 'DE-W081', '--output', context, '--byte-budget', '700000', '--artifact-byte-budget', '16777216']):
        run('verify-context', [py, 'spec/tools/specctl.py', 'verify-context', context])
    summary['inputs_unchanged'] = all(digest(root / path) == value for path, value in before.items())
    summary['checkout_status_after'] = subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True)
    summary['status'] = 'pass' if ok and summary.get('probe_import_check') and summary.get('probe_security_check') and summary.get('fault_import_check') and summary.get('fault_security_check') and summary['inputs_unchanged'] and all(stage['exit_code'] == 0 for stage in summary['stages']) else 'fail'
    save()
    print(summary['status'], summary.get('ntfs_cases'), flush=True)
    return 0 if summary['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
