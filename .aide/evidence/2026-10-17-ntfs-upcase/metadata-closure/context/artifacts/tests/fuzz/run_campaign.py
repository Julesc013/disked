"""Linux installed-GCC sanitizer/coverage campaign; no downloads or installation."""
import argparse
import gzip
import hashlib
import json
import os
import re
import resource
import subprocess
import zlib
from pathlib import Path


def sha(path):
    return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--corpus', required=True); parser.add_argument('--output', required=True)
    parser.add_argument('--iterations', type=int, default=10000); parser.add_argument('--seed', type=int, default=0xde0023)
    args = parser.parse_args()
    if os.geteuid() == 0: raise PermissionError('Unprivileged campaign required')
    assert 0 <= args.iterations <= 1000000 and 0 < args.seed <= 0xffffffff
    root = Path(__file__).resolve().parents[2]; corpus = Path(args.corpus).resolve()
    output = Path(args.output).resolve(); output.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((corpus/'manifest.json').read_text(encoding='utf-8'))
    images = []
    for case in manifest['cases']:
        path = corpus/case['file']
        assert path.name == case['file'] and not path.is_symlink() and path.is_file()
        assert path.resolve().parent == corpus and sha(path) == case['sha256'] and path.stat().st_size <= 2097152
        assert case['unit'] == 512 and case['blocks'] == 256
        images.append(path)
    sources = ['source/portable/primitives/checked.c', 'source/portable/primitives/view.c',
               'source/portable/primitives/extent.c', 'source/portable/mbr/mbr.c', 'source/portable/ebr/ebr.c',
               'source/portable/gpt/encoding.c', 'source/portable/gpt/gpt.c']
    headers = ['source/portable/primitives/checked.h', 'source/portable/primitives/view.h',
               'source/portable/primitives/extent.h', 'source/portable/mbr/mbr.h',
               'source/portable/ebr/ebr.h', 'source/portable/gpt/gpt.h']
    harness = ['tests/fuzz/partition_faults.cpp', 'tests/fuzz/sanitizer_control.cpp', 'tests/fuzz/run_campaign.py']
    # This explicit local checkout is owned by the Windows developer, while the
    # Linux campaign deliberately runs as nobody. Scope the read-only exception
    # to these invocations; do not change any user's Git configuration.
    git = ['git', '-c', 'safe.directory='+str(root)]
    identity = dict(uid=os.geteuid(), source_revision=subprocess.check_output([*git, 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
                    source_state='dirty' if subprocess.check_output([*git, 'status', '--porcelain'], cwd=root) else 'clean',
                    inputs={path:sha(root/path) for path in sources+headers+harness}, seed=args.seed, iterations=args.iterations,
                    corpus_manifest_sha256=sha(corpus/'manifest.json'), tool_files={})
    env = dict(os.environ, ASAN_OPTIONS='abort_on_error=1:detect_leaks=1', UBSAN_OPTIONS='halt_on_error=1:print_stacktrace=1', LC_ALL='C')
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    commands = []
    def write(name, value):
        (output/name).write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8')
    def run(name, argv, timeout=120, expected_failure=None):
        argv = [str(x) for x in argv]
        print('Running '+name, flush=True)
        try:
            process = subprocess.run(argv, cwd=output, env=env, capture_output=True, timeout=timeout)
            stdout, stderr, code = process.stdout, process.stderr, process.returncode
        except subprocess.TimeoutExpired as error:
            stdout, stderr, code = error.stdout or b'', error.stderr or b'', None
        (output/(name+'.stdout.log')).write_bytes(stdout); (output/(name+'.stderr.log')).write_bytes(stderr)
        matched = code == 0 if expected_failure is None else code is not None and code != 0 and expected_failure in stderr
        commands.append(dict(argv=argv, cwd=str(output), exit_code=code,
                             expected='success' if expected_failure is None else 'positive-control failure',
                             matched=matched, stdout=name+'.stdout.log', stderr=name+'.stderr.log'))
        write('commands.json', commands)
        if not matched: raise RuntimeError(name+' failed; logs retained')
        return stdout
    write('identity.json', identity); write('results.json', dict(passed=False, stage='build', source=identity))
    compiler = '/usr/bin/gcc'; cpp = '/usr/bin/g++'; gcov = '/usr/bin/gcov'
    for tool in [compiler, cpp, gcov]:
        path = Path(tool).resolve(); identity['tool_files'][str(path)] = sha(path)
        run(path.name+'-version', [tool, '--version'])
    includes = sorted({str((root/path).parent) for path in headers})
    flags = ['-g', '-O1', '-fno-omit-frame-pointer', '-fno-sanitize-recover=all', '-fsanitize=address,undefined', '--coverage',
             '-Wall', '-Wextra', '-Werror', '-pedantic-errors']
    objects = []
    for i, source in enumerate(sources+['tests/fuzz/partition_faults.cpp']):
        obj = output/(str(i)+'.o'); objects.append(obj)
        run('compile-'+str(i), [compiler if source in sources else cpp,
            '-std=c90' if source in sources else '-std=c++14', *flags,
            *['-I'+item for item in includes], '-c', root/source, '-o', obj])
    exe = output/'partition-faults'
    run('link', [cpp, *flags, *objects, '-o', exe])
    controls = []
    for sanitizer in ['address', 'undefined']:
        control = output/('control-'+sanitizer); controls.append(control)
        control_flags = [flag for flag in flags if not flag.startswith('-fsanitize=')]
        run('control-build-'+sanitizer, [cpp, '-std=c++14', *control_flags, '-fsanitize='+sanitizer,
                                       root/'tests/fuzz/sanitizer_control.cpp', '-o', control])
    for tool in [exe, *controls]:
        linked = run(tool.name+'-libraries', ['/usr/bin/ldd', tool])
        for name in re.findall(rb'(?:=>\s*)?(/[^\s()]+)', linked):
            path = Path(os.fsdecode(name)).resolve()
            if path.is_file(): identity['tool_files'][str(path)] = sha(path)
    for name in ['cc1', 'cc1plus', 'ld', 'libgcov.a']:
        path = Path(run('tool-'+name, [compiler, '-print-file-name='+name]).decode().strip()).resolve()
        if path.is_file(): identity['tool_files'][str(path)] = sha(path)
    identity['executables'] = {str(path): sha(path) for path in [exe, *controls]}; write('identity.json', identity)
    run('positive-asan', [controls[0], 'bounds'], expected_failure=b'AddressSanitizer: heap-buffer-overflow')
    run('positive-ubsan', [controls[1], 'overflow'], expected_failure=b'runtime error: signed integer overflow')
    run('positive-invariant', [exe, '--control-failure'], expected_failure=b'campaign invariant')
    def retain_failure(name):
        log = (output/(name+'.stdout.log')).read_bytes()
        checkpoints = re.findall(rb'^case (\d+) seed (\d+) bytes (\d+) crc32 (\d+)$', log, re.M)
        if not checkpoints: return None
        iteration, index, size, crc = map(int, checkpoints[-1]); failure = output/(name+'-failure.img')
        run(name+'-reproduce-input', [exe, '--emit', iteration, args.seed, 256, failure, *images])
        data = failure.read_bytes(); assert len(data)==size and zlib.crc32(data)==crc
        receipt = dict(iteration=iteration, seed_index=index, bytes=size, checkpoint_crc32=crc,
                       image_sha256=sha(failure), source=identity)
        write(name+'-failure.json', receipt); return receipt
    run('positive-replay', [exe, '--control', 1, args.seed, 256, *images], expected_failure=b'campaign invariant')
    assert retain_failure('positive-replay')['iteration']==len(images)
    write('results.json', dict(passed=False, stage='campaign', source=identity))
    campaign = [exe, '--run', args.iterations, args.seed, 256, *images]
    try: data = run('campaign', campaign, timeout=240)
    except RuntimeError:
        retain_failure('campaign')
        write('results.json', dict(passed=False, stage='campaign', source=identity)); raise
    summary = json.loads(data.splitlines()[-1]); assert summary['cases'] == args.iterations+len(images)
    assert all(summary[key]>0 for key in ['mbr_signatures', 'ebr_feeds', 'consistent_headers', 'complete_arrays', 'agree', 'disagree'])
    coverage = []
    for i, source in enumerate(sources):
        run('coverage-'+str(i), [gcov, '--json-format', '--branch-counts', '--branch-probabilities', output/(str(i)+'.gcda')])
        compressed = output/(str(i)+'.gcov.json.gz'); value = json.loads(gzip.decompress(compressed.read_bytes()))
        write('coverage-'+str(i)+'.json', value)
        for file in value['files']:
            lines = file['lines']; branches = [b for line in lines for b in line.get('branches', [])]
            reported = Path(file['file']).resolve()
            reported_path = reported.relative_to(root).as_posix() if reported.is_relative_to(root) else str(reported)
            coverage.append(dict(path=reported_path, translation_unit=source, lines=len(lines), lines_executed=sum(x['count']>0 for x in lines),
                                 branches=len(branches), branches_taken=sum(x['count']>0 for x in branches)))
    for case in manifest['cases']: assert sha(corpus/case['file']) == case['sha256']
    for path, expected in identity['inputs'].items(): assert sha(root/path) == expected
    for path, expected in identity['tool_files'].items(): assert sha(Path(path)) == expected
    write('results.json', dict(passed=True, source=identity, summary=summary, coverage=coverage,
         limitations=['Bounded deterministic mutation, not coverage-guided or exhaustive fuzzing',
                      'Linux x64 installed GCC sanitizer host only; historical and physical storage qualification remain open']))
    print('Sanitizer campaign PASS', summary, flush=True)


if __name__ == '__main__': main()
