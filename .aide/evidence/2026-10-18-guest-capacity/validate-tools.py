"""Retain this checkpoint's host tooling results without replacing old receipts."""
import hashlib
import io
import json
from pathlib import Path
import subprocess
import unittest

root = Path(__file__).resolve().parents[3]
log = io.StringIO()
suite = unittest.defaultTestLoader.discover(str(root / 'tests/tools'))
result = unittest.TextTestRunner(stream=log, verbosity=2).run(suite)
text = log.getvalue()
if len(text.encode()) > 65536:
    raise RuntimeError('Tooling log exceeds retained bound')
record = dict(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
              skipped=len(result.skipped), passed=result.wasSuccessful(), scope='Host tooling only',
              base_revision=subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
              source_hashes={p: hashlib.sha256((root / p).read_bytes()).hexdigest()
                             for p in ('tools/windows-worker.py', 'tools/workspace.py', 'tools/qualify-storage.py',
                                       'tests/tools/test_windows_worker.py', 'tests/tools/test_storage_setup.py')},
              log=text)
Path(__file__).with_name('tooling-checks.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8', newline='\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
