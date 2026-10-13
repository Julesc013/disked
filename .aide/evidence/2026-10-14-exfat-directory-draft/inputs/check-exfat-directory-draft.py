import json,subprocess
from pathlib import Path
root=Path.cwd();api=(root/'.aide-local/exfat-directory-api.txt').read_text()
header=(root/'source/portable/exfat/exfat.h').read_text()
header=header.replace('#ifdef __cplusplus\nextern "C" {',api+'#ifdef __cplusplus\nextern "C" {',1)
header=header.replace('/* Exactly one supplied little-endian cell', 'int de_exfat_slot_read(const de_view *, de_exfat_slot *);\nint de_exfat_file_set_read(const de_view *, de_u32, unsigned int, size_t, de_exfat_file_set *);\n/* Exactly one supplied little-endian cell',1)
(root/'.aide-local/exfat.h').write_text(header,encoding='utf-8')
gcc=json.loads((root/'.aide/evidence/2026-10-14-fat-recursive-qualification/gcc-identity.json').read_bytes())['path']
result=subprocess.run([gcc,'-std=c90','-pedantic-errors','-Wall','-Wextra','-Werror','-I','source','-fsyntax-only','.aide-local/exfat-directory.c'],capture_output=True)
(root/'.aide-local/exfat-directory-draft-c90.log').write_bytes(result.stdout+result.stderr)
raise SystemExit(result.returncode)
