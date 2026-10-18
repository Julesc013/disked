"""Copy a bounded local Python runtime into the authorized guest, without an installer."""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[3]
LIMIT = 64 * 1024 * 1024
EXCLUDED = {'site-packages', '__pycache__', 'test', 'tests', 'idlelib',
            'tkinter', 'turtledemo', 'ensurepip'}


def main():
    work = Path(os.environ['DISKED_WORK_ROOT']).resolve(strict=True)
    base = Path(sys.base_prefix).resolve(strict=True)
    if os.name != 'nt' or sys.version_info[:3] != (3, 14, 7) or base != Path('C:/Program Files/Python314'):
        raise RuntimeError('Expected installed host Python 3.14.7; do not substitute silently')
    selected = [p for p in base.iterdir() if p.is_file() and p.name in {
        'LICENSE.txt', 'python.exe', 'pythonw.exe', 'python3.dll',
        'python314.dll', 'vcruntime140.dll', 'vcruntime140_1.dll'}]
    for folder in ('DLLs', 'Lib'):
        for current, directories, names in os.walk(base / folder, followlinks=False):
            directories[:] = [name for name in directories if name not in EXCLUDED]
            for name in directories + names:
                p = Path(current) / name
                if p.is_symlink() or p.lstat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT:
                    raise RuntimeError('Linked runtime input: ' + str(p))
            selected.extend(Path(current) / name for name in names if not name.endswith(('.pyc', '.pyo')))
    selected.sort(key=lambda p: p.relative_to(base).as_posix())
    if len(selected) > 1000 or sum(p.stat().st_size for p in selected) > LIMIT:
        raise RuntimeError('Runtime selection exceeds its declared bound')
    archive = work / 'python314.zip'
    manifest = {'schema': 'org.disked.python-runtime/1', 'version': sys.version,
                'base_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
                'maximum_bytes': LIMIT, 'files': [], 'content_bytes': 0}
    with zipfile.ZipFile(archive, 'x', compression=zipfile.ZIP_DEFLATED, compresslevel=6) as output:
        for p in selected:
            data = p.read_bytes()
            manifest['content_bytes'] += len(data)
            if manifest['content_bytes'] > LIMIT:
                raise RuntimeError('Runtime changed beyond its bound during selection')
            name = p.relative_to(base).as_posix()
            output.writestr(name, data)
            manifest['files'].append({'path': name, 'bytes': len(data), 'sha256': hashlib.sha256(data).hexdigest()})
            if archive.stat().st_size > LIMIT:
                raise RuntimeError('Runtime transfer exceeds its declared bound')
    manifest['archive_sha256'] = hashlib.file_digest(archive.open('rb'), 'sha256').hexdigest()
    manifest['archive_bytes'] = archive.stat().st_size
    manifest_file = work / 'python314.json'
    manifest_file.write_text(json.dumps(manifest, separators=(',', ':')), encoding='utf-8', newline='\n')
    if manifest_file.stat().st_size > 262144:
        raise RuntimeError('Runtime manifest exceeds its bound')
    result = subprocess.run(['pwsh', '-NoProfile', '-File', str(Path(__file__).with_name('copy-runtime.ps1')),
                             '-Archive', str(archive), '-Manifest', str(manifest_file)],
                            cwd=ROOT, timeout=180, check=False)
    raise SystemExit(result.returncode)


if __name__ == '__main__':
    main()
