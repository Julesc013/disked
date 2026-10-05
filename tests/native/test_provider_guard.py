"""Positive control: establish that provider initialization instrumentation works."""
import subprocess
import sys
import tempfile

with tempfile.TemporaryDirectory(prefix="disked-provider-control-") as directory:
    result = subprocess.run([sys.argv[1]], cwd=directory, stdin=subprocess.DEVNULL,
        capture_output=True, timeout=10)
    if result.returncode != 97 or result.stdout or result.stderr:
        raise SystemExit("Poison provider did not produce its exact expected refusal")
print("PASS: provider initialization boundary exits 97")
