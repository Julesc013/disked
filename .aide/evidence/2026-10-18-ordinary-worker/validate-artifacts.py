"""Bounded staging-tool regressions; inert fixture bytes, no DiskEd execution."""
import json
from pathlib import Path
import subprocess
import sys

here=Path(__file__).resolve().parent
command=[sys.executable,'-B','tests/artifacts/test_artifact_check.py','--evidence',str(here/'artifact-inventory-retest.json')]
result=subprocess.run(command,cwd=here.parents[2],capture_output=True,timeout=90)
raw=result.stdout+result.stderr
if len(raw)>65536:raise ValueError('Artifact-test diagnostic bound')
(here/'artifact-inventory-retest.log').write_bytes(raw)
raise SystemExit(result.returncode)
