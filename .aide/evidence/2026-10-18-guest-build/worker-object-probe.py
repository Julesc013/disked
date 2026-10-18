"""Own disposable named-job DACL observations inside the confined worker."""
import ctypes
from ctypes import wintypes as T
import json
import sys
import uuid

k=ctypes.WinDLL('kernel32',use_last_error=True)
a=ctypes.WinDLL('advapi32',use_last_error=True)
k.GetCurrentProcess.restype=T.HANDLE
k.CloseHandle.argtypes=[T.HANDLE]
k.LocalFree.argtypes=[ctypes.c_void_p]
a.OpenProcessToken.argtypes=[T.HANDLE,T.DWORD,ctypes.POINTER(T.HANDLE)]
a.GetTokenInformation.argtypes=[T.HANDLE,ctypes.c_int,ctypes.c_void_p,T.DWORD,ctypes.POINTER(T.DWORD)]
a.ConvertSidToStringSidW.argtypes=[ctypes.c_void_p,ctypes.POINTER(T.LPWSTR)]
a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[T.LPCWSTR,T.DWORD,ctypes.POINTER(ctypes.c_void_p),ctypes.POINTER(T.DWORD)]
class Attributes(ctypes.Structure):
    _fields_=[('size',T.DWORD),('descriptor',ctypes.c_void_p),('inherit',T.BOOL)]
k.CreateJobObjectW.argtypes=[ctypes.POINTER(Attributes),T.LPCWSTR]
k.CreateJobObjectW.restype=T.HANDLE
k.OpenJobObjectW.argtypes=[T.DWORD,T.BOOL,T.LPCWSTR]
k.OpenJobObjectW.restype=T.HANDLE

def need(value):
    if not value:raise ctypes.WinError(ctypes.get_last_error())

def token_sid(token,kind):
    size=T.DWORD()
    a.GetTokenInformation(token,kind,None,0,ctypes.byref(size))
    assert 0<size.value<=65536
    buffer=ctypes.create_string_buffer(size.value)
    need(a.GetTokenInformation(token,kind,buffer,len(buffer),ctypes.byref(size)))
    sid=ctypes.cast(buffer,ctypes.POINTER(ctypes.c_void_p))[0]
    text=T.LPWSTR();need(a.ConvertSidToStringSidW(sid,ctypes.byref(text)))
    try:return text.value
    finally:k.LocalFree(text)

token=T.HANDLE();need(a.OpenProcessToken(k.GetCurrentProcess(),8,ctypes.byref(token)))
try:
    size=T.DWORD();container=T.DWORD()
    need(a.GetTokenInformation(token,29,ctypes.byref(container),4,ctypes.byref(size)))
    assert container.value==1
    user,package=token_sid(token,1),token_sid(token,31)
finally:k.CloseHandle(token)
other=sys.argv[1];assert other.startswith('S-1-15-2-') and other!=package
result=dict(scope='Fresh own named jobs only; no DiskEd execution or existing object mutation',
            user_sid=user,package_sid=package,other_package_sid=other,objects=[])
for label,selected in [('user_only',None),('same_package',package),('other_package',other)]:
    descriptor=ctypes.c_void_p()
    sddl='D:P(A;;FA;;;'+user+')'+('(A;;FA;;;'+selected+')' if selected else '')
    need(a.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,ctypes.byref(descriptor),None))
    created=opened=None
    try:
        attributes=Attributes(ctypes.sizeof(Attributes),descriptor,False)
        name='Local\\DiskEd.OwnDaclProbe.'+uuid.uuid4().hex
        ctypes.set_last_error(0);created=k.CreateJobObjectW(ctypes.byref(attributes),name)
        create_error=ctypes.get_last_error()
        ctypes.set_last_error(0);opened=k.OpenJobObjectW(4,False,name) if created else None
        open_error=ctypes.get_last_error()
        result['objects'].append(dict(dacl=label,created=bool(created),create_error=create_error,
            query_opened=bool(opened),query_error=open_error))
    finally:
        if opened:k.CloseHandle(opened)
        if created:k.CloseHandle(created)
        k.LocalFree(descriptor)
result['owned_handles_closed']=True
print(json.dumps(result))
