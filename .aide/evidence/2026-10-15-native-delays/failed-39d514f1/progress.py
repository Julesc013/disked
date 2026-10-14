import json
import re
from pathlib import Path

root = Path(__file__).resolve().parent
lines = (root / 'native.log').read_text(encoding='utf8', errors='replace').splitlines()
rows = [line.strip() for line in lines if re.match(r'\s*\d+/145 Test', line)]
failed = [line for line in rows if 'Passed' not in line]
print(json.dumps(dict(completed=len(rows), failed=len(failed), failures=failed,
    latest=rows[-1] if rows else None, stage=json.loads((root / 'current-stage.json').read_bytes())), indent=2))
