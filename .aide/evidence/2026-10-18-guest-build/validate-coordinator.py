"""Retain coordinator regressions without overwriting earlier checkpoints."""
import hashlib
import io
import json
from pathlib import Path
import unittest

root = Path(__file__).resolve().parents[3]
log = io.StringIO()
result = unittest.TextTestRunner(stream=log, verbosity=2).run(unittest.defaultTestLoader.discover(str(root / 'tests/tools')))
record = {'tests_run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
          'skipped': len(result.skipped), 'passed': result.wasSuccessful(), 'log': log.getvalue(),
          'source_hashes': {p: hashlib.sha256((root / p).read_bytes()).hexdigest()
                            for p in ('tools/source-snapshot.py', 'tests/tools/test_source_snapshot.py')}}
if len(record['log'].encode()) > 65536:
    raise RuntimeError('Coordinator log exceeds retention bound')
Path(__file__).with_name('coordinator-checks.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8', newline='\n')
raise SystemExit(0 if result.wasSuccessful() else 1)
