"""Hash-bind a temporary copy of the existing host PowerShell 7 runtime."""
import hashlib
import json
from pathlib import Path
import stat
import zipfile


def prepare(stage):
    source=Path('C:/Program Files/PowerShell/7')
    modules=('Microsoft.PowerShell.Management','Microsoft.PowerShell.Utility','Microsoft.PowerShell.Security')
    selected=sorted([p for p in source.iterdir() if p.is_file()]+
        [p for module in modules for p in (source/'Modules'/module).rglob('*') if p.is_file()])
    if not (source/'pwsh.exe').is_file() or len(selected)>1024:raise ValueError('Existing runtime closure required')
    files=[];total=0
    with zipfile.ZipFile(stage/'pwsh7.zip','x',compression=zipfile.ZIP_DEFLATED,compresslevel=9) as archive:
        for path in selected:
            for parent in (path.parent,*path.parent.parents):
                if getattr(parent.lstat(),'st_file_attributes',0)&0x400:raise ValueError('Linked runtime ancestor')
                if parent==source:break
            info=path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or getattr(info,'st_file_attributes',0)&0x400:
                raise ValueError('Linked/non-file runtime input')
            if info.st_size>64*1024*1024:raise ValueError('Runtime file bound')
            data=path.read_bytes();after=path.stat()
            identity=lambda s:(s.st_dev,s.st_ino,s.st_size,s.st_mtime_ns)
            if identity(info)!=identity(after):raise ValueError('Runtime changed during transfer preparation')
            total+=len(data)
            if total>256*1024*1024:raise ValueError('Runtime content bound')
            name=path.relative_to(source).as_posix()
            archive.writestr(name,data)
            files.append(dict(path=name,bytes=len(data),sha256=hashlib.sha256(data).hexdigest()))
    if (stage/'pwsh7.zip').stat().st_size>128*1024*1024:raise ValueError('Runtime transfer bound')
    for row in files:
        if hashlib.sha256((source/row['path']).read_bytes()).hexdigest()!=row['sha256']:
            raise ValueError('Runtime closure changed before handoff')
    record=dict(schema='org.disked.guest-powershell-tool/1',source=str(source),modules=list(modules),
        files=files,bytes=total,archive_sha256=hashlib.sha256((stage/'pwsh7.zip').read_bytes()).hexdigest(),
        preparer_sha256=hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        scope='Existing tool copied temporarily into bounded guest scratch; no installation or retained runtime')
    (stage/'pwsh7.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
    return record
