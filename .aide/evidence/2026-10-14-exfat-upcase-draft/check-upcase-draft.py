import json,subprocess
from pathlib import Path
root=Path.cwd();p=root/'.aide-local/exfat-upcase-draft.h';p.write_text('#include "portable/exfat/exfat.h"\n'+(root/'.aide-local/exfat-upcase-api.txt').read_text(),encoding='utf-8')
gcc=json.loads((root/'.aide/evidence/2026-10-14-fat-recursive-qualification/gcc-identity.json').read_bytes())['path'];r=subprocess.run([gcc,'-std=c90','-pedantic-errors','-Wall','-Wextra','-Werror','-I','source','-fsyntax-only','.aide-local/exfat-upcase.c'],capture_output=True);(root/'.aide-local/exfat-upcase-c90-draft.log').write_bytes(r.stdout+r.stderr);raise SystemExit(r.returncode)
