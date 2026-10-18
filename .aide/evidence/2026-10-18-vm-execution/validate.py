"""Retain bounded coordinator-tool results; no guest authentication or product tests."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import unittest

ROOT = Path(__file__).resolve().parents[3]
OUTPUT = Path(__file__).resolve().parent


class BoundedLog(io.StringIO):
    def write(self, text):
        if self.tell() + len(text) > 131072:
            raise RuntimeError('Tooling log exceeded its explicit retention budget')
        return super().write(text)


def main():
    log = BoundedLog()
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests/tools'))
    result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
    log_bytes = log.getvalue().encode('utf-8')
    if len(log_bytes) > 131072:
        raise RuntimeError('Encoded tooling log exceeded its retention budget')
    (OUTPUT / 'tooling.log').write_bytes(log_bytes)
    value = {
        'schema': 'org.disked.vm-connection-validation/1',
        'base_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
        'command': 'python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-18-vm-execution/validate.py',
        'execution_scope': 'Host coordinator tooling, including tiny owned isolation stand-ins; no product storage tests or guest login.',
        'tests_run': result.testsRun,
        'failures': len(result.failures),
        'errors': len(result.errors),
        'skipped': [{'test': str(test), 'reason': reason} for test, reason in result.skipped],
        'successful': result.wasSuccessful(),
        'tested_source_hashes': {
            path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
            for path in ('tools/connect-vm.ps1', 'tests/tools/test_vm_connection.py',
                         'tools/workspace.py', 'tools/windows-worker.py',
                         '.aide/evidence/2026-10-18-vm-execution/validate.py')
        },
        'log_sha256': hashlib.sha256(log_bytes).hexdigest(),
        'guest_connection_verified': False,
        'guest_uac_change_verified': False,
        'native_build_run': False,
    }
    (OUTPUT / 'tooling.json').write_bytes((json.dumps(value, indent=2) + '\n').encode())
    return 0 if result.wasSuccessful() else 1


if __name__ == '__main__':
    raise SystemExit(main())
