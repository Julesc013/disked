"""Windows coordinator for the explicitly unprivileged installed WSL profiles."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path


def sha(path): return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    p = argparse.ArgumentParser()
    for key in ['output', 'mbr-probe', 'gpt-probe', 'probe-identity']: p.add_argument('--'+key, required=True)
    p.add_argument('--iterations', type=int, default=10000)
    a = p.parse_args(); root = Path(__file__).resolve().parents[2]
    if os.name != 'nt': raise RuntimeError('WSL coordinator requires Windows; use the individual Linux adapters directly')
    out = Path(a.output).resolve()
    if not out.is_relative_to(root/'.aide-local'): raise ValueError('Campaign output must be within this checkout .aide-local')
    out.mkdir(parents=True, exist_ok=False)
    identity = json.loads(Path(a.probe_identity).read_text(encoding='utf-8'))
    for name, expected in identity['inputs'].items():
        if sha(root/name) != expected: raise ValueError('Native evidence no longer applicable: '+name)
    # Exact probe artifacts must come from that identity's generated build tree.
    build = Path(a.probe_identity).resolve().parent.parent
    for path, name in [(a.mbr_probe, 'mbr_probe.exe'), (a.gpt_probe, 'gpt_probe.exe')]:
        if Path(path).resolve() != build/'Release'/name: raise ValueError('Probe/identity build tree mismatch')
    commands = []
    def write(name, value): (out/name).write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8', newline='\n')
    def run(name, args):
        argv = [str(x) for x in args]; print('Running '+name, flush=True)
        result = subprocess.run(argv, cwd=root, capture_output=True, timeout=600)
        (out/(name+'.log')).write_bytes(result.stdout+result.stderr)
        commands.append(dict(argv=argv, cwd=str(root), exit_code=result.returncode, log=name+'.log'))
        write('commands.json', commands)
        if result.returncode: raise RuntimeError(name+' failed; retained log')
        return result
    def linux(path):
        value = Path(path).resolve().as_posix(); drive, rest = value.split(':', 1)
        if len(drive)!=1: raise ValueError('Only local drive paths are supported by this coordinator')
        return '/mnt/'+drive.lower()+rest
    def wsl(distro, script, *args):
        return ['wsl', '-d', distro, '--user', 'nobody', '--exec', '/usr/bin/python3', linux(root/script), *args]
    tracked = subprocess.check_output(['git','status','--porcelain'], cwd=root)
    source = dict(revision=subprocess.check_output(['git','rev-parse','HEAD'], cwd=root, text=True).strip(),
                  state='dirty' if tracked else 'clean',
                  inputs={p.relative_to(root).as_posix():sha(p) for folder in ['tests/corpus','tests/differential','tests/fuzz']
                          for p in sorted((root/folder).iterdir()) if p.is_file()},
                  reused_native_identity=identity, probe_hashes={str(Path(path).resolve()):sha(Path(path)) for path in [a.mbr_probe,a.gpt_probe]})
    write('source.json', source)
    run('generate', [sys.executable, root/'tests/corpus/partition_images.py', '--output', out/'corpus'])
    run('native', [sys.executable, root/'tests/differential/observe_native.py', '--corpus', out/'corpus',
                   '--mbr-probe', a.mbr_probe, '--gpt-probe', a.gpt_probe, '--output', out/'native'])
    run('adapter-controls', ['wsl','-d','Ubuntu-24.04','--user','nobody','--exec','/usr/bin/python3',
                             '-m','unittest','discover','-s',linux(root/'tests/differential'),'-v'])
    for distro, name in [('Ubuntu-24.04','ubuntu'), ('Debian','debian')]:
        args = wsl(distro, 'tests/differential/observe_external.py', '--corpus', linux(out/'corpus'),
                    '--output', linux(out/name))
        if name == 'ubuntu': args.append('--sgdisk')
        run(name, args)
    run('compare', [sys.executable, root/'tests/differential/compare.py', '--manifest', out/'corpus/manifest.json',
                    '--native', out/'native/results.json', '--external', out/'ubuntu/results.json',
                    '--external', out/'debian/results.json', '--output', out/'comparisons.json'])
    run('sanitizers', wsl('Ubuntu-24.04', 'tests/fuzz/run_campaign.py', '--corpus', linux(out/'corpus'),
                         '--output', linux(out/'faults'), '--iterations', str(a.iterations)))
    for name, expected in source['inputs'].items(): assert sha(root/name) == expected
    for name, expected in identity['inputs'].items(): assert sha(root/name) == expected
    for name, expected in source['probe_hashes'].items(): assert sha(Path(name)) == expected
    faults = json.loads((out/'faults/results.json').read_text(encoding='utf-8')); assert faults['passed']
    comparison = json.loads((out/'comparisons.json').read_text(encoding='utf-8')); assert comparison['adapter_controls_passed']
    native = json.loads((out/'native/results.json').read_text(encoding='utf-8')); assert native['passed']
    external_count = sum(len(json.loads((out/name/'results.json').read_text(encoding='utf-8'))['observations']) for name in ['ubuntu','debian'])
    write('results.json', dict(passed=True, source=source, native_cases=native['cases'], external_observations=external_count,
        comparisons=len(comparison['comparisons']), retained_discrepancies=sum(bool(x['discrepancy']) for x in comparison['comparisons']),
        fault_cases=faults['summary']['cases'], coverage=faults['coverage'],
        limitations=['Native probes reused only after all recorded build inputs match',
                     'External source-package versions recorded; source bytes not rebuilt',
                     'Synthetic ordinary files and private readers only; no product image-provider admission']))
    print('W023 campaign PASS:', out, flush=True)


if __name__ == '__main__': main()
