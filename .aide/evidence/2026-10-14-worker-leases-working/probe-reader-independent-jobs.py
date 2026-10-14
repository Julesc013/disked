import json
import argparse
import sys
from pathlib import Path
root = Path.cwd()
sys.path.insert(0, str(root / 'tests/resilience'))
sys.path.insert(0, str(root / 'tests/frontend'))
from memory_fixture import Job, AssignedProcess, MIB, limits
from test_image_commands import Gate
parser = argparse.ArgumentParser()
parser.add_argument('--probe', type=Path, default=root / '.aide-local/launch-attributes/build-v143/Release/launch_attributes.exe')
parser.add_argument('--output', type=Path, default=root / '.aide-local/reader-independent-jobs.json')
args = parser.parse_args()
exe = args.probe.resolve()
target = root / '.aide-local/exfat-command-exact-60376a0e/build/Release/disked_fat_test.exe'
source = root / '.aide-local/exfat-command-exact-60376a0e/source/.aide-local/launch-source-probe.img'
gate = Gate()
records = []
try:
    with Job(512 * MIB) as host_a, Job(512 * MIB) as host_b:
        before_a, before_b = limits(host_a.handle), limits(host_b.handle)
        with AssignedProcess([exe, target, source, gate.name], host_a) as first:
            gate.entered()
            with AssignedProcess([exe, target, source], host_b) as second:
                code, output, error = second.result()
                assert code == 0 and not error, (code, output, error)
                records.append(dict(host='B', response=json.loads(output)))
            gate.release()
            code, output, error = first.result()
            assert code == 0 and not error, (code, output, error)
            records.append(dict(host='A', response=json.loads(output)))
        for before, after in [(before_a, limits(host_a.handle)), (before_b, limits(host_b.handle))]:
            assert all(before[k] == after[k] for k in ['flags', 'process_bytes', 'job_bytes', 'active_limit'])
finally:
    gate.release(); gate.close()
    args.output.write_text(json.dumps(records, indent=2) + '\n', encoding='utf-8')
print(json.dumps(records, indent=2))
