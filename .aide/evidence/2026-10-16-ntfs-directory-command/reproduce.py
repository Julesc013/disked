"""Clean-source build and selected native/tooling campaign for NTFS directory command and shared presentation."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
import shutil
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--resume-counter-error', action='store_true')
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    output.mkdir(exist_ok=args.resume_counter_error)
    build = output / 'build'
    inputs = set(json.loads((root / 'tools/build-inputs.json').read_bytes())['files'])
    inputs.update(row['path'] for row in json.loads((root / 'spec/catalog/input-dependencies.json').read_bytes())['inputs'])
    inputs.update(path.relative_to(root).as_posix() for path in (root / 'source').rglob('*') if path.is_file())
    before = {name: sha(root / name) for name in sorted(inputs)}
    if args.resume_counter_error:
        assert before == json.loads((output / 'inputs.json').read_bytes())
    else:
        (output / 'inputs.json').write_text(json.dumps(before, indent=2) + '\n', encoding='utf-8', newline='\n')
    summary = dict(status='running', work_id='DE-W093', observed_at=datetime.now(timezone.utc).isoformat(),
                   source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                   source_status_before=subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True),
                   host=platform.platform(), python=sys.version, stages=[], owner_accepted=False,
                   full_0_1_0_complete=False, original_delay_cause_established=False,
                   scope='Current Windows x64 image prototype, all targets built and complete registered native regressions and independent tooling/build/import/context evidence. Not full NTFS, all original platforms/storage or release qualification.')
    summary['qualification_recipe_sha256'] = sha(Path(__file__).resolve())
    summary['source_qualification_recipe_sha256'] = before['.aide/evidence/2026-10-16-ntfs-directory-command/reproduce.py']
    reused = {}
    built_artifacts = {}
    if args.resume_counter_error:
        previous = json.loads((output / 'summary.json').read_bytes())
        assert previous['status'] == 'fail' and previous['error'] == 'AssertionError()'
        assert previous['source_revision'] == summary['source_revision']
        assert previous['native_passed'] == previous['native_groups'] == previous['registered_native_groups'] == 163
        assert previous['native_exit_code'] == 0 and not previous['native_failed'] and not previous['native_skipped']
        assert all(s['exit_code'] == 0 for s in previous['stages'])
        native = ET.parse(output / 'native-junit.xml').getroot().findall('.//testcase')
        assert len(native) == 163 and all(t.find('failure') is None and t.find('error') is None and t.find('skipped') is None for t in native)
        command = json.loads((build / 'ntfs-command-cases.json').read_bytes())
        directory = json.loads((build / 'ntfs-directory-command-cases.json').read_bytes())
        assert command['passed'] and command['cases'] == len(command['records']) == 58
        assert directory['passed'] and directory['cases'] == 100
        assert len(previous['artifacts']) == len({p['path'] for p in previous['artifacts']}) == 11
        assert all(sha(Path(p['path'])) == p['sha256'] for p in previous['artifacts'])
        assert previous['stages'][-1]['name'] == 'ntfs_inspection_probe-dependents'
        history = output / 'failed-counter'
        history.mkdir()
        for p in list(output.iterdir()):
            if p.is_file():
                shutil.copyfile(p, history / p.name)
        summary['stages'] = previous['stages']
        reused = {s['name']: s for s in summary['stages']}
        assert len(reused) == len(summary['stages'])
        built_artifacts = {p.relative_to(build).as_posix(): sha(p) for p in build.rglob('*') if p.is_file() and p.suffix in {'.exe', '.lib', '.obj'}}
        summary['resumed_after'] = 'failed-counter/summary.json'
        summary['reused_build_artifacts'] = built_artifacts

    def save():
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8', newline='\n')

    def run(name, command):
        command = list(map(str, command))
        if name in reused:
            assert reused[name]['command'] == command and reused[name]['cwd'] == str(root)
            print('REUSE verified', name, flush=True)
            return reused[name]['exit_code']
        print('BEGIN', name, flush=True)
        start = time.monotonic()
        with (output / (name + '.log')).open('wb') as log:
            result = subprocess.run(command, cwd=root, stdout=log, stderr=subprocess.STDOUT)
        summary['stages'].append(dict(name=name, command=command, cwd=str(root), exit_code=result.returncode,
                                      seconds=time.monotonic() - start, log=name + '.log'))
        save()
        print('END', name, result.returncode, flush=True)
        return result.returncode

    try:
        assert not summary['source_status_before'], 'Clean source checkout required'
        assert run('configure', ['cmake', '--preset', 'windows-bootstrap', '-B', build, '-DPython3_EXECUTABLE=' + sys.executable]) == 0
        assert run('build', ['cmake', '--build', build, '--config', 'Release', '--parallel', '4']) == 0
        assert run('registered', ['ctest', '--test-dir', build, '-C', 'Release', '--show-only=json-v1']) == 0
        registered = {row['name'] for row in json.loads((output / 'registered.log').read_bytes())['tests']}
        expected = registered
        assert len(expected)==163 and {'image.ntfs_commands','image.ntfs_directory_commands','image.ntfs_directory_worker','build.boundaries','build.boundary_checker'}<=expected
        summary['registered_native_groups'] = len(registered)
        summary['full_native_suite_run'] = True
        summary['selected_native_groups'] = sorted(expected)
        selected_pattern = '^(' + '|'.join(re.escape(n) for n in sorted(expected)) + ')$'
        assert run('selected-registration', ['ctest','--test-dir',build,'-C','Release','--show-only=json-v1','-R',selected_pattern])==0
        selected=json.loads((output/'selected-registration.log').read_bytes())['tests']
        assert len(selected)==len(expected) and {r['name'] for r in selected}==expected
        summary['native_exit_code'] = run('native', ['ctest', '--test-dir', build, '-C', 'Release', '--parallel', '1',
                                                    '--output-on-failure', '-R', selected_pattern, '--output-junit', output / 'native-junit.xml'])
        tests = ET.parse(output / 'native-junit.xml').getroot().findall('.//testcase')
        assert len(tests) == len(expected) and {t.attrib['name'] for t in tests} == expected
        summary['native_groups'] = len(tests)
        summary['native_failed'] = [t.attrib['name'] for t in tests if t.find('failure') is not None or t.find('error') is not None]
        summary['native_skipped'] = [t.attrib['name'] for t in tests if t.find('skipped') is not None]
        summary['native_passed'] = len(tests) - len(summary['native_failed']) - len(summary['native_skipped'])
        summary['ntfs_cases'] = {p.name: json.loads(p.read_bytes()).get('count', json.loads(p.read_bytes()).get('cases')) for p in build.glob('ntfs-*-cases.json')}
        identity = json.loads((build / 'generated/build-identity.json').read_bytes())
        summary['build_identity'] = identity
        dumpbin = Path(identity['compiler_path']).with_name('dumpbin.exe')
        summary['artifacts'] = []
        for name in ('disked', 'ntfs_block_probe', 'ntfs_record_probe', 'ntfs_attributes_probe', 'ntfs_capture_probe', 'ntfs_file_probe', 'ntfs_file_fault', 'ntfs_worker_probe', 'ntfs_worker_fault', 'disked_ntfs_test', 'ntfs_inspection_probe'):
            path = build / 'Release' / (name + '.exe')
            summary['artifacts'].append(dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path)))
            for mode in ('headers', 'imports', 'dependents'):
                run(name + '-' + mode, [dumpbin, '/' + mode, path])
            headers = (output / (name + '-headers.log')).read_text()
            assert all(value in headers for value in ('8664 machine (x64)', 'Dynamic base', 'NX compatible', 'Control Flow Guard'))
        assert summary['ntfs_cases']['ntfs-block-cases.json'] == 1230
        assert summary['ntfs_cases']['ntfs-directory-cases.json'] == 227
        assert summary['ntfs_cases']['ntfs-directory-file-cases.json'] == 550
        assert summary['ntfs_cases']['ntfs-file-cases.json'] == 79
        assert summary['ntfs_cases']['ntfs-directory-worker-cases.json'] == 235
        directory_command=json.loads((build/'ntfs-directory-command-cases.json').read_bytes())
        bootstrap_command=json.loads((build/'ntfs-command-cases.json').read_bytes())
        assert directory_command['passed'] and bootstrap_command['passed']
        assert directory_command['cases']==100 and bootstrap_command['cases']==58
        assert len(summary['artifacts'])==len({v['path'] for v in summary['artifacts']})==11
        assert len(directory_command['source_receipts'])==22
        assert all(v['before_sha256']==v['after_sha256'] for v in directory_command['source_receipts'])
        assert any(v['bytes']>2**32 for v in directory_command['source_receipts'])
        summary['directory_command_cases']=directory_command['cases']
        summary['bootstrap_command_cases']=bootstrap_command['cases']
        worker_cases=json.loads((build/'ntfs-directory-worker-cases.json').read_bytes())
        assert worker_cases['methods']==12 and not worker_cases['failures'] and not worker_cases['errors']
        assert summary['ntfs_cases']['ntfs-index-cases.json'] == 1502
        assert run('c90-version', ['gcc', '--version']) == 0
        assert run('c90', ['gcc', '-std=c90', '-pedantic-errors', '-Wall', '-Wextra', '-Werror', '-fsyntax-only', '-Isource',
                           *sorted(str(p.relative_to(root)) for p in (root / 'source/portable/ntfs').glob('*.c'))]) == 0
        for header in ('ntfs.h', 'fixup.h'):
            path = output / (header + '.c')
            path.write_text('#include "portable/ntfs/' + header + '"\n', encoding='utf-8', newline='\n')
            assert run('c90-header-' + header, ['gcc', '-std=c90', '-pedantic-errors', '-Wall', '-Wextra', '-Werror', '-fsyntax-only', '-Isource', path]) == 0
        objects = [p for directory in build.glob('*_headers.dir') for p in (directory / 'Release').glob('*.obj')]
        summary['standalone_headers'] = len(objects)
        summary['header_artifacts'] = [dict(path=str(p), sha256=sha(p)) for p in sorted(objects)]
        run('boundaries', [sys.executable, 'tools/check-build-boundaries.py', '--build', build, '--output', output / 'build-boundaries.json'])
        for name, args in [('source-map', ['tools/check-source-map.py']), ('index', ['spec/tools/specctl.py', 'index', '--check']),
                           ('structural', ['spec/tools/specctl.py', 'check']), ('tooling', ['-m', 'unittest', 'discover', '-s', 'spec/tools/tests', '-v']),
                           ('manifest', ['spec/tools/specctl.py', 'verify-manifest'])]:
            run(name, [sys.executable, *args])
        matches = re.findall(r'Ran (\d+) tests in ', (output / 'tooling.log').read_text())
        summary['tooling_tests_run'] = int(matches[-1]) if matches else None
        run('context', [sys.executable, 'spec/tools/specctl.py', 'context', '--work', 'DE-W093', '--output', output / 'context',
                        '--byte-budget', '1200000', '--artifact-byte-budget', '16777216'])
        run('verify-context', [sys.executable, 'spec/tools/specctl.py', 'verify-context', output / 'context'])
        summary['inputs_unchanged'] = all(sha(root / name) == digest for name, digest in before.items())
        if built_artifacts:
            summary['reused_artifacts_unchanged'] = all(sha(build / name) == digest for name, digest in built_artifacts.items())
            assert summary['reused_artifacts_unchanged']
        summary['source_status_after'] = subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True)
        summary['status'] = 'pass' if not summary['native_failed'] and not summary['native_skipped'] and all(s['exit_code'] == 0 for s in summary['stages']) and summary['inputs_unchanged'] and not summary['source_status_after'] else 'fail'
    except BaseException as error:
        summary['status'] = 'fail'
        summary['error'] = repr(error)
        save()
        raise
    save()
    print(summary['status'], summary.get('native_passed'), summary.get('native_failed'), flush=True)
    return 0 if summary['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
