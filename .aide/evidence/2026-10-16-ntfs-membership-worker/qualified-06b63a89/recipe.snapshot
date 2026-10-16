"""Exact-source owned NTFS correspondence worker qualification; selected gates only."""
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
    args = parser.parse_args()
    root, output = args.root.resolve(), args.output.resolve()
    output.mkdir()
    build = output / 'build'
    inputs = set(json.loads((root / 'tools/build-inputs.json').read_bytes())['files'])
    inputs.update(row['path'] for row in json.loads((root / 'spec/catalog/input-dependencies.json').read_bytes())['inputs'])
    inputs.update(path.relative_to(root).as_posix() for path in (root / 'source').rglob('*') if path.is_file())
    before = {name: sha(root / name) for name in sorted(inputs)}
    (output / 'inputs.json').write_text(json.dumps(before, indent=2) + '\n', encoding='utf-8', newline='\n')
    summary = dict(status='running', work_id='DE-W097', observed_at=datetime.now(timezone.utc).isoformat(),
                   source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                   source_status_before=subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True),
                   host=platform.platform(), python=sys.version, stages=[], owner_accepted=False,
                   full_0_1_0_complete=False, original_delay_cause_established=False,
                   scope='Current Windows x64 image prototype, all targets built and the predefined 34 affected native regression groups from 167 registered and independent tooling/build/import/context evidence. Private owned-worker directory/name correspondence and unchanged common command path only. Not public membership admission, full NTFS, all original platforms/storage or release qualification.')
    summary['qualification_recipe_sha256'] = sha(Path(__file__).resolve())
    summary['source_qualification_recipe_sha256'] = before['.aide/evidence/2026-10-16-ntfs-membership-worker/reproduce.py']
    def save():
        (output / 'summary.json').write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8', newline='\n')

    def run(name, command):
        command = list(map(str, command))
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
        expected = set(json.loads((root/'spec/catalog/ntfs-membership-worker-prototype.json').read_bytes())['qualification']['selected_native_groups'])
        assert len(registered)==167 and len(expected)==34 and {'image.ntfs_membership','image.ntfs_names','image.ntfs_stream','image.ntfs_commands','image.ntfs_directory_commands','image.ntfs_directory_worker','build.boundaries','build.boundary_checker'}<=expected
        summary['registered_native_groups'] = len(registered)
        summary['full_native_suite_run'] = False
        summary['selected_native_groups'] = sorted(expected)
        selected_pattern = '^(' + '|'.join(re.escape(n) for n in sorted(expected)) + ')$'
        assert run('selected-registration', ['ctest','--test-dir',build,'-C','Release','--show-only=json-v1','-R',selected_pattern])==0
        selected=json.loads((output/'selected-registration.log').read_bytes())['tests']
        assert len(selected)==len(expected) and {r['name'] for r in selected}==expected
        summary['native_exit_code'] = run('native', ['ctest', '--test-dir', build, '-C', 'Release', '--parallel', '1',
                                                    '--output-on-failure', '--stop-on-failure', '-R', selected_pattern, '--output-junit', output / 'native-junit.xml'])
        tests = ET.parse(output / 'native-junit.xml').getroot().findall('.//testcase')
        actual_names = {t.attrib['name'] for t in tests}
        summary['full_native_suite_run'] = len(tests) == len(registered) and actual_names == registered
        summary['selected_native_suite_complete'] = len(tests) == len(expected) and actual_names == expected
        summary['native_not_run'] = sorted(expected - actual_names)
        summary['native_groups'] = len(tests)
        summary['native_failed'] = [t.attrib['name'] for t in tests if t.find('failure') is not None or t.find('error') is not None]
        summary['native_skipped'] = [t.attrib['name'] for t in tests if t.find('skipped') is not None]
        summary['native_passed'] = len(tests) - len(summary['native_failed']) - len(summary['native_skipped'])
        assert summary['native_exit_code'] == 0, 'Native campaign failed; remaining qualification not run'
        assert summary['selected_native_suite_complete'] and not summary['full_native_suite_run'] and not summary['native_failed'] and not summary['native_skipped']
        summary['ntfs_cases'] = {p.name: json.loads(p.read_bytes()).get('count', json.loads(p.read_bytes()).get('cases')) for p in build.glob('ntfs-*-cases.json')}
        identity = json.loads((build / 'generated/build-identity.json').read_bytes())
        summary['build_identity'] = identity
        dumpbin = Path(identity['compiler_path']).with_name('dumpbin.exe')
        summary['artifacts'] = []
        for name in ('disked', 'ntfs_block_probe', 'ntfs_record_probe', 'ntfs_attributes_probe', 'ntfs_capture_probe', 'ntfs_file_probe', 'ntfs_file_fault', 'ntfs_worker_probe', 'ntfs_worker_fault', 'disked_ntfs_test', 'ntfs_inspection_probe', 'ntfs_stream_probe', 'ntfs_names_probe'):
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
        assert len(summary['artifacts'])==len({v['path'] for v in summary['artifacts']})==13
        assert len(directory_command['source_receipts'])==22
        assert all(v['before_sha256']==v['after_sha256'] for v in directory_command['source_receipts'])
        assert any(v['bytes']>2**32 for v in directory_command['source_receipts'])
        names=json.loads((build/'ntfs-names-cases.json').read_bytes())
        assert names['passed'] and names['count']==247
        summary['filename_cases']=names['count']
        membership=json.loads((build/'ntfs-membership-cases.json').read_bytes())
        assert membership['count']==193 and all(c['passed'] for c in membership['cases'])
        summary['membership_cases']=membership['count']
        held_membership=json.loads((build/'ntfs-membership-file-cases.json').read_bytes())
        assert held_membership['methods']==11 and not held_membership['failures'] and not held_membership['errors']
        assert held_membership['cases']==496
        assert all(r['before_sha256']==r['after_sha256'] for r in held_membership['source_receipts'])
        summary['membership_file_cases']=held_membership['cases']
        member_worker=json.loads((build/'ntfs-membership-worker-cases.json').read_bytes())
        assert member_worker['status']=='pass' and member_worker['methods']==12 and member_worker['cases']==310
        assert not member_worker['failures'] and not member_worker['errors'] and not member_worker['unexpected_outputs']
        assert all(r['before_sha256']==r['after_sha256'] for r in member_worker['source_receipts'])
        summary['membership_worker_cases']=member_worker['cases']
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
        assert len(objects)==67
        summary['header_artifacts'] = [dict(path=str(p), sha256=sha(p)) for p in sorted(objects)]
        run('boundaries', [sys.executable, 'tools/check-build-boundaries.py', '--build', build, '--output', output / 'build-boundaries.json'])
        for name, args in [('source-map', ['tools/check-source-map.py']), ('index', ['spec/tools/specctl.py', 'index', '--check']),
                           ('structural', ['spec/tools/specctl.py', 'check']), ('tooling', ['-m', 'unittest', 'discover', '-s', 'spec/tools/tests', '-v']),
                           ('manifest', ['spec/tools/specctl.py', 'verify-manifest'])]:
            run(name, [sys.executable, *args])
        matches = re.findall(r'Ran (\d+) tests in ', (output / 'tooling.log').read_text())
        summary['tooling_tests_run'] = int(matches[-1]) if matches else None
        run('context', [sys.executable, 'spec/tools/specctl.py', 'context', '--work', 'DE-W097', '--output', output / 'context',
                        '--byte-budget', '1200000', '--artifact-byte-budget', '16777216'])
        run('verify-context', [sys.executable, 'spec/tools/specctl.py', 'verify-context', output / 'context'])
        summary['inputs_unchanged'] = all(sha(root / name) == digest for name, digest in before.items())
        summary['source_status_after'] = subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True)
        summary['status'] = 'pass' if not summary['native_failed'] and not summary['native_skipped'] and all(s['exit_code'] == 0 for s in summary['stages']) and summary['inputs_unchanged'] and not summary['source_status_after'] else 'fail'
    except BaseException as error:
        summary['status'] = 'fail'
        summary['error'] = repr(error)
        summary['inputs_unchanged'] = all(sha(root / name) == digest for name, digest in before.items())
        summary['source_status_after'] = subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True)
        save()
        raise
    save()
    print(summary['status'], summary.get('native_passed'), summary.get('native_failed'), flush=True)
    return 0 if summary['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
