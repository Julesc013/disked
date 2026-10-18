"""Retain bounded coordinator checks; these do not qualify guest execution."""
import io
import json
from pathlib import Path
import unittest
import sys

root = Path(__file__).resolve().parents[3]
full = sys.argv[1:] == ['--all-tools']
if sys.argv[1:] not in ([], ['--all-tools']):
    raise SystemExit('Use no arguments or --all-tools')
suite = unittest.defaultTestLoader.discover(str(root / 'tests/tools'), pattern='test_*.py' if full else 'test_vm_connection.py')
log = io.StringIO()
result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
text = log.getvalue()
if len(text.encode()) > 65536:
    raise RuntimeError('Connection checks exceeded retained output bound')
record = dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
              skipped=len(result.skipped), passed=result.wasSuccessful(),
              connection_authentication_mocked=True, guest_connection_qualified=False,
              native_tests_run=False, log=text)
Path(__file__).with_name('tooling-checks.json' if full else 'connection-checks.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8')
raise SystemExit(0 if result.wasSuccessful() else 1)
