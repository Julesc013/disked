"""Retain bounded coordinator-only fixture regression results; no native product."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time

HERE=Path(__file__).resolve().parent
label=sys.argv[1]
if label not in ('closure-red','closure-green','affected-tooling'):
    raise ValueError('Unknown retained check')
if 'DISKED_WORK_ROOT' not in os.environ:raise ValueError('Managed coordinator required')
pattern='test_source_snapshot.py' if label.startswith('closure-') else 'test_*fixture*.py'
command=[sys.executable,'-B','-m','unittest','discover','-s','tests/tools','-p',pattern,'-v']
started=time.monotonic();out=subprocess.run(command,capture_output=True,timeout=180)
if len(out.stdout)+len(out.stderr)>131072:raise ValueError('Regression diagnostic bound')
row=dict(label=label,command=command,exit_code=out.returncode,seconds=time.monotonic()-started,
         stdout=out.stdout.decode(errors='replace'),stderr=out.stderr.decode(errors='replace'),native_product_executed=False)
p=HERE/'fixture-repair-checks.json';rows=json.loads(p.read_bytes()) if p.exists() else []
rows.append(row);p.write_text(json.dumps(rows,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(label=label,exit_code=out.returncode,seconds=row['seconds'])))
raise SystemExit(out.returncode)
