"""Adapt synthetic raw files to the existing private native observation probes."""
import argparse
import hashlib
import json
import stat
import struct
import subprocess
from pathlib import Path

from projections import native_request as request, field, native_projection as projection


def sha(data):
    return 'sha256:'+hashlib.sha256(data).hexdigest()


def load_case(root, case):
    path = root/case['file']
    if path.name != case['file'] or path.is_symlink() or path.resolve().parent != root:
        raise ValueError('Fixture must be an immediate ordinary corpus file')
    st = path.stat()
    if not stat.S_ISREG(st.st_mode) or st.st_size > 2*1024*1024:
        raise ValueError('Fixture type or byte budget')
    data = path.read_bytes()
    if len(data) != case['bytes'] or sha(data) != case['sha256']:
        raise ValueError('Fixture identity changed')
    return data


def observe(corpus, mbr_probe, gpt_probe, output):
    root = Path(corpus).resolve(); manifest = json.loads((root/'manifest.json').read_text(encoding='utf-8'))
    results = []; output = Path(output); output.mkdir(parents=True, exist_ok=False)
    failures = []
    for case in manifest['cases']:
        data = load_case(root, case); value = request(data, case)
        probe = Path(mbr_probe if case['family'] == 'mbr' else gpt_probe).resolve()
        payload = (json.dumps(value, separators=(',', ':'))+'\n').encode()
        process = subprocess.run([str(probe)], input=payload, capture_output=True, timeout=15)
        (output/(case['name']+'.stdout.json')).write_bytes(process.stdout)
        (output/(case['name']+'.stderr.log')).write_bytes(process.stderr)
        checks = []; observed = None
        if process.returncode == 0:
            observed = json.loads(process.stdout)
            for key, expected in case['checks'].items():
                actual = field(observed, key); matched = actual == expected and type(actual) is type(expected)
                checks.append(dict(path=key, expected=expected, actual=actual, matched=matched))
                if not matched: failures.append(case['name']+': '+key)
        else: failures.append(case['name']+': process exit')
        assert load_case(root, case) == data
        results.append(dict(name=case['name'], sha256=case['sha256'], probe=str(probe), probe_sha256=sha(probe.read_bytes()),
                            argv=[str(probe)], exit_code=process.returncode, checks=checks,
                            input_sha256=sha(payload), output_sha256=sha(process.stdout),
                            projection=projection(observed, case['family']) if observed is not None else None))
    receipt = dict(passed=not failures, cases=len(results), failures=failures, observations=results)
    (output/'results.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8', newline='\n')
    if failures: raise AssertionError(failures)
    return receipt


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    for key in ['corpus', 'mbr-probe', 'gpt-probe', 'output']: parser.add_argument('--'+key, required=True)
    args = parser.parse_args(); result = observe(args.corpus, args.mbr_probe, args.gpt_probe, args.output)
    print('Native file-view contract checks PASS:', result['cases'])
