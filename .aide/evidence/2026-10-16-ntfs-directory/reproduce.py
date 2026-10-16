"""Single clean-source native/tooling campaign for source-bound NTFS directory index graphs."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import platform
import re
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
    output.mkdir(exist_ok=False)
    build = output / 'build'
    inputs = set(json.loads((root / 'tools/build-inputs.json').read_bytes())['files'])
    inputs.update(row['path'] for row in json.loads((root / 'spec/catalog/input-dependencies.json').read_bytes())['inputs'])
    inputs.update(path.relative_to(root).as_posix() for path in (root / 'source').rglob('*') if path.is_file())
    before = {name: sha(root / name) for name in sorted(inputs)}
    (output / 'inputs.json').write_text(json.dumps(before, indent=2) + '\n', encoding='utf-8', newline='\n')
    summary = dict(status='running', work_id='DE-W089', observed_at=datetime.now(timezone.utc).isoformat(),
                   source_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                   source_status_before=subprocess.check_output(['git', 'status', '--porcelain'], cwd=root, text=True),
                   host=platform.platform(), python=sys.version, stages=[], owner_accepted=False,
                   full_0_1_0_complete=False, original_delay_cause_established=False,
                   scope='Current Windows x64 image prototype, one complete registered native campaign and independent tooling/build/import/context evidence. Not full NTFS, all original platforms/storage or release qualification.')

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
        expected = {row['name'] for row in json.loads((output / 'registered.log').read_bytes())['tests']}
        summary['native_exit_code'] = run('native', ['ctest', '--test-dir', build, '-C', 'Release', '--parallel', '1',
                                                    '--output-on-failure', '--output-junit', output / 'native-junit.xml'])
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
        for name in ('disked', 'ntfs_block_probe', 'ntfs_record_probe', 'ntfs_attributes_probe', 'ntfs_capture_probe', 'ntfs_file_probe', 'ntfs_worker_probe'):
            path = build / 'Release' / (name + '.exe')
            summary['artifacts'].append(dict(path=str(path), bytes=path.stat().st_size, sha256=sha(path)))
            for mode in ('headers', 'imports', 'dependents'):
                run(name + '-' + mode, [dumpbin, '/' + mode, path])
            headers = (output / (name + '-headers.log')).read_text()
            assert all(value in headers for value in ('8664 machine (x64)', 'Dynamic base', 'NX compatible', 'Control Flow Guard'))
        assert summary['ntfs_cases']['ntfs-block-cases.json'] == 1230
        assert summary['ntfs_cases']['ntfs-directory-cases.json'] == 227
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
        run('context', [sys.executable, 'spec/tools/specctl.py', 'context', '--work', 'DE-W089', '--output', output / 'context',
                        '--byte-budget', '1200000', '--artifact-byte-budget', '16777216'])
        run('verify-context', [sys.executable, 'spec/tools/specctl.py', 'verify-context', output / 'context'])
        summary['inputs_unchanged'] = all(sha(root / name) == digest for name, digest in before.items())
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
