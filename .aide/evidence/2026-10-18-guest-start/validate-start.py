"""Four mocked refusal scenarios; never start, reset, stop or authenticate a VM."""
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

HERE = Path(__file__).resolve().parent
SCRIPT = HERE / 'finish-start.ps1'
CASES = (
    ('different_vm', "@{Name='Different';State='Off';ProcessorCount=2}",
     "@{Startup=2GB;Maximum=3GB}", 'VM identity changed'),
    ('paused_vm', "@{Name='Windows 10';State='Paused';ProcessorCount=2}",
     "@{Startup=2GB;Maximum=3GB}", 'Unexpected VM state'),
    ('changed_configuration', "@{Name='Windows 10';State='Off';ProcessorCount=8}",
     "@{Startup=8GB;Maximum=32GB}", 'Shared VM configuration changed'),
    ('insufficient_reserve', "@{Name='Windows 10';State='Off';ProcessorCount=2}",
     "@{Startup=2GB;Maximum=3GB}", 'Host resource reserve too low'),
)


def main():
    rows = []
    for name, vm, memory, expected in CASES:
        with tempfile.TemporaryDirectory(prefix='startup-refusal-') as directory:
            root = Path(directory)
            copy = root / 'finish-start.ps1'
            shutil.copyfile(SCRIPT, copy)
            command = (
                "function Get-VM { " + vm + " }; "
                "function Get-VMMemory { " + memory + " }; "
                "function Get-CimInstance { @{FreePhysicalMemory=4GB/1KB} }; "
                "function Get-PSDrive { throw 'UNEXPECTED_DRIVE_QUERY' }; "
                "function Start-VM { throw 'UNEXPECTED_VM_START' }; "
                "function New-PSSession { throw 'UNEXPECTED_AUTHENTICATION' }; "
                "& '" + str(copy).replace("'", "''") + "'")
            result = subprocess.run(['pwsh', '-NoProfile', '-NonInteractive', '-Command', command],
                                    env=dict(os.environ, DISKED_WORK_ROOT=str(root)),
                                    capture_output=True, timeout=20)
            report = json.loads((root / 'startup-result.json').read_bytes())
            assert result.returncode == 1, (name, result.returncode, result.stderr)
            assert report['phase'] == 'requires_inspection', (name, report)
            assert expected in report['error'], (name, report)
            assert report['starts_issued'] == report['authentication_attempts'] == 0
            rows.append({'case': name, 'status': 'pass', 'expected_refusal': expected})
    value = {'schema': 'org.disked.guest-start-refusal-tests/1',
             'script_sha256': hashlib.sha256(SCRIPT.read_bytes()).hexdigest(),
             'cases': rows, 'actual_vm_actions': False,
             'guest_connection_qualified': False, 'native_tests_run': False}
    (HERE / 'start-refusal-validation.json').write_bytes((json.dumps(value, indent=2) + '\n').encode())
    print(json.dumps({'refusal_cases_passed': len(rows), 'actual_vm_actions': False}))


if __name__ == '__main__':
    main()
