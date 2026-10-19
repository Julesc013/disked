"""Stage pinned spec-tool dependencies in managed storage, never globally."""
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import stat
import subprocess
import sys
import zipfile


def prepare(root, stage, work):
    target=work/'schema-dependencies';report=work/'schema-pip-report.json'
    requirement=root/'spec/tools/requirements.txt'
    command=[sys.executable,'-B','-m','pip','--isolated','install','--disable-pip-version-check',
        '--no-cache-dir','--no-compile','--only-binary=:all:','--ignore-installed',
        '--platform','win_amd64','--python-version','3.14','--implementation','cp','--abi','cp314',
        '--no-warn-script-location','--index-url','https://pypi.org/simple',
        '--target',str(target),'--report',str(report),'-r',str(requirement)]
    call=subprocess.run(command,capture_output=True,timeout=180,env=dict(os.environ,PYTHONDONTWRITEBYTECODE='1'))
    if len(call.stdout)+len(call.stderr)>65536:raise ValueError('Dependency setup log bound')
    if call.returncode:raise RuntimeError('Pinned schema dependency setup failed: '+call.stderr[-4096:].decode(errors='replace'))
    files=[];total=0
    destination=stage/'pydeps.zip'
    with zipfile.ZipFile(destination,'x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in sorted(target.rglob('*')):
            info=path.lstat()
            if getattr(info,'st_file_attributes',0)&0x400 or path.is_symlink():raise ValueError('Linked dependency input')
            if path.is_dir():continue
            relative=path.relative_to(target).as_posix()
            if path.suffix in ('.exe','.pyc') or '__pycache__' in path.parts:continue
            if path.suffix=='.pth':raise ValueError('Implicit dependency startup hook is outside this recipe')
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or info.st_size>4*1024*1024:raise ValueError('Dependency file shape/bound')
            data=path.read_bytes();total+=len(data)
            if len(files)>=2000 or total>16*1024*1024:raise ValueError('Dependency closure bound')
            archive.writestr(relative,data)
            files.append(dict(path=relative,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    if destination.stat().st_size>8*1024*1024:raise ValueError('Dependency transfer bound')
    metadata=json.loads(report.read_bytes())
    value=dict(schema='org.disked.guest-schema-tools/1',requirements_sha256=hashlib.sha256(requirement.read_bytes()).hexdigest(),
        preparer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),installer_command=command,pip_version=metadata['pip_version'],
        files=files,bytes=total,archive_sha256=hashlib.sha256(destination.read_bytes()).hexdigest(),
        distributions=sorted([dict(name=d.metadata['Name'],version=d.version) for d in importlib.metadata.distributions(path=[str(target)])],key=lambda d:d['name'].lower()),
        wheels=[dict(name=d['metadata']['name'],version=d['metadata']['version'],sha256=d['download_info']['archive_info']['hashes']['sha256']) for d in metadata['install']],
        scope='Temporary modern Python schema-test tools only; not DiskEd runtime or platform qualification')
    (stage/'pydeps.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
    return value
