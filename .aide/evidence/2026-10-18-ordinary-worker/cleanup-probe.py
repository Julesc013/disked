"""Observe deletion of tiny owned files with FAT-style attributes; no ACL edits."""
import ctypes as C
from ctypes import wintypes as T
import json
import importlib.util
import os
from pathlib import Path
import stat
import sys
import tempfile
import time

k=C.WinDLL('kernel32',use_last_error=True);a=C.WinDLL('advapi32',use_last_error=True)
P=C.c_void_p
def bind(dll,name,result,*args):
    f=getattr(dll,name);f.restype=result;f.argtypes=args;return f
create=bind(k,'CreateFileW',T.HANDLE,T.LPCWSTR,T.DWORD,T.DWORD,P,T.DWORD,T.DWORD,T.HANDLE)
close=bind(k,'CloseHandle',T.BOOL,T.HANDLE)
attrs=bind(k,'GetFileAttributesW',T.DWORD,T.LPCWSTR)
setattrs=bind(k,'SetFileAttributesW',T.BOOL,T.LPCWSTR,T.DWORD)
delete=bind(k,'DeleteFileW',T.BOOL,T.LPCWSTR)
getsd=bind(a,'GetNamedSecurityInfoW',T.DWORD,T.LPWSTR,C.c_int,T.DWORD,P,P,P,P,C.POINTER(P))
tostr=bind(a,'ConvertSecurityDescriptorToStringSecurityDescriptorW',T.BOOL,P,T.DWORD,T.DWORD,C.POINTER(T.LPWSTR),P)
free=bind(k,'LocalFree',P,P)
def security(path):
    sd=P();text=T.LPWSTR();code=getsd(str(path),1,7,None,None,None,None,C.byref(sd))
    if code:return dict(error=code)
    try:
        if not tostr(sd,1,7,C.byref(text),None):raise C.WinError(C.get_last_error())
        return dict(sddl=text.value)
    finally:
        if text:free(C.cast(text,P))
        free(sd)

parent=Path(sys.argv[1]).absolute()
if parent!=Path(os.environ['TEMP']).absolute() or parent.parent!=Path(os.environ['DISKED_WORK_ROOT'])/'native-x64':raise ValueError('Unowned diagnostic parent')
folder=Path(tempfile.mkdtemp(prefix='owned-attribute-delete-',dir=parent));rows=[]
for flags in (0x80,1,2,4,0x27):
    path=folder/(str(flags)+'.bin')
    handle=create(str(path),0xc0000000,0,None,1,0x80,None)
    if handle==P(-1).value:raise C.WinError(C.get_last_error())
    close(handle)
    if not setattrs(str(path),flags):raise C.WinError(C.get_last_error())
    row=dict(flags=flags,before_attributes=attrs(str(path)),security=security(path),attempts=[])
    for action in ('initial-delete','chmod-read-write','native-normal-attributes','native-delete'):
        try:
            if action=='chmod-read-write':path.chmod(path.stat().st_mode|stat.S_IWUSR|stat.S_IRUSR)
            elif action=='native-normal-attributes':
                if not setattrs(str(path),0x80):raise C.WinError(C.get_last_error())
            if action=='native-delete':
                if not delete(str(path)):raise C.WinError(C.get_last_error())
            else:os.unlink(path)
            row['attempts'].append(dict(action=action,deleted=True));break
        except OSError as error:
            row['attempts'].append(dict(action=action,deleted=False,winerror=error.winerror,attributes=attrs(str(path))))
    row['remains']=path.exists();rows.append(row)
if not list(folder.iterdir()):folder.rmdir()
owned=Path(tempfile.mkdtemp(prefix='owned-cleanup-regression-',dir=parent))
for flags in (1,0x27):
    path=owned/(str(flags)+'.bin');path.write_bytes(b'owned disposable output')
    if not setattrs(str(path),flags):raise C.WinError(C.get_last_error())
write=bind(k,'WriteFile',T.BOOL,T.HANDLE,P,T.DWORD,C.POINTER(T.DWORD),P)
flush=bind(k,'FlushFileBuffers',T.BOOL,T.HANDLE)
buffer=C.create_string_buffer(b'x'*512);io=[]
for per_write_flush in (False,True):
    path=owned/('flush-'+str(per_write_flush)+'.bin')
    handle=create(str(path),0xc0000000,0,None,1,0x80,None)
    if handle==P(-1).value:raise C.WinError(C.get_last_error())
    started=time.monotonic();cpu=time.process_time()
    try:
        for number in range(32):
            count=T.DWORD()
            if not write(handle,buffer,512,C.byref(count),None) or count.value!=512:raise C.WinError(C.get_last_error())
            if per_write_flush and not flush(handle):raise C.WinError(C.get_last_error())
        if not flush(handle):raise C.WinError(C.get_last_error())
        io.append(dict(per_write_flush=per_write_flush,writes=32,bytes=16384,
            seconds=time.monotonic()-started,process_cpu_seconds=time.process_time()-cpu))
    finally:close(handle)
definition=importlib.util.spec_from_file_location('owned_workspace',Path(__file__).parent/'source/tools/workspace.py')
workspace=importlib.util.module_from_spec(definition);definition.loader.exec_module(workspace)
workspace.remove_owned_work(owned,parent,'owned-cleanup-regression-')
if owned.exists():raise ValueError('Owned cleanup regression left output')
print(json.dumps(dict(scope=__doc__,rows=rows,all_removed=all(not r['remains'] for r in rows),
    production_cleanup_regression=dict(flags=[1,0x27],removed=True,acl_changes=False),
    owned_io_diagnostic=io)))
