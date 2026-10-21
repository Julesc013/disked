"""One owned HKCU write and documented profile/known-folder observations."""
import ctypes as C
from ctypes import wintypes as T
import json
import os
from pathlib import Path
import sys
import uuid
import winreg

assert os.name=='nt' and os.environ['COMPUTERNAME']=='BLACKGLASS-HYPE'
profile,sid,nonce=sys.argv[1:]
assert Path(profile).drive.upper()=='R:' and sid.startswith('S-1-5-21-') and len(nonce)==32
k=C.WinDLL('kernel32',use_last_error=True);a=C.WinDLL('advapi32',use_last_error=True)
u=C.WinDLL('userenv',use_last_error=True);shell=C.WinDLL('shell32',use_last_error=True);ole=C.WinDLL('ole32')
k.GetCurrentProcess.restype=T.HANDLE
a.OpenProcessToken.argtypes=[T.HANDLE,T.DWORD,C.POINTER(T.HANDLE)];a.OpenProcessToken.restype=T.BOOL
k.CloseHandle.argtypes=[T.HANDLE]
u.GetUserProfileDirectoryW.argtypes=[T.HANDLE,T.LPWSTR,C.POINTER(T.DWORD)];u.GetUserProfileDirectoryW.restype=T.BOOL
shell.SHGetKnownFolderPath.argtypes=[C.c_void_p,T.DWORD,T.HANDLE,C.POINTER(T.LPWSTR)];shell.SHGetKnownFolderPath.restype=T.LONG
ole.CoTaskMemFree.argtypes=[C.c_void_p]
token=T.HANDLE()
if not a.OpenProcessToken(k.GetCurrentProcess(),8,C.byref(token)):raise C.WinError(C.get_last_error())
try:
    buf=C.create_unicode_buffer(32768);size=T.DWORD(len(buf))
    if not u.GetUserProfileDirectoryW(token,buf,C.byref(size)):raise C.WinError(C.get_last_error())
    assert Path(buf.value)==Path(profile)
    folders={}
    for name,identifier in [('profile','5e6c858f-0e22-4760-9afe-ea3317b67173'),
                            ('local','f1b32785-6fba-4fcf-9d55-7b8e7f157091'),
                            ('roaming','3eb685db-65f9-4cf6-a03a-e3ef65729f3d')]:
        guid=C.create_string_buffer(uuid.UUID(identifier).bytes_le);path=T.LPWSTR()
        status=shell.SHGetKnownFolderPath(guid,0,None,C.byref(path))
        if status<0:raise OSError('Known folder failed: '+hex(status&0xffffffff))
        try:folders[name]=path.value
        finally:ole.CoTaskMemFree(C.cast(path,C.c_void_p))
        assert Path(folders[name]).is_relative_to(Path(profile))
    with winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,r'Software\DiskEdProfileProof',0,winreg.KEY_SET_VALUE) as key:
        winreg.SetValueEx(key,'nonce',0,winreg.REG_SZ,nonce)
    print(json.dumps(dict(profile=buf.value,known_folders=folders,temp=os.environ['TEMP'],nonce=nonce,
                         expected_actor_sid=sid,environment_profile=os.environ.get('USERPROFILE'))))
finally:k.CloseHandle(token)
