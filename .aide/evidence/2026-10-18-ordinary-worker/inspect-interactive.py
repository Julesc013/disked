"""Read-only Agents interactive-session observation; no worker qualification."""
import ctypes as C
from ctypes import wintypes as T
import json
import os
from pathlib import Path

root = Path('C:/ProgramData/DiskEd/interactive-check')
owner = json.loads((root / 'owner.json').read_bytes())
result = dict(scope=__doc__, nonce=owner['nonce'], status='running')
k, a, u = [C.WinDLL(name, use_last_error=True) for name in ('kernel32', 'advapi32', 'user32')]
P = C.c_void_p
def bind(api,name,rest,*args):
    function=getattr(api,name);function.restype=rest;function.argtypes=args;return function
def require(ok):
    if not ok:raise C.WinError(C.get_last_error())
token=T.HANDLE()
try:
    bind(k,'GetCurrentProcess',T.HANDLE)
    require(bind(a,'OpenProcessToken',T.BOOL,T.HANDLE,T.DWORD,C.POINTER(T.HANDLE))(k.GetCurrentProcess(),8,C.byref(token)))
    query=bind(a,'GetTokenInformation',T.BOOL,T.HANDLE,C.c_int,P,T.DWORD,C.POINTER(T.DWORD))
    needed=T.DWORD();query(token,1,None,0,C.byref(needed));assert 0<needed.value<=4096
    data=C.create_string_buffer(needed.value);require(query(token,1,data,needed,C.byref(needed)))
    sid=C.cast(data,C.POINTER(P))[0];text=T.LPWSTR()
    require(bind(a,'ConvertSidToStringSidW',T.BOOL,P,C.POINTER(T.LPWSTR))(sid,C.byref(text)))
    free=bind(k,'LocalFree',P,P)
    try:result['user_sid']=text.value
    finally:free(C.cast(text,P))
    name=C.create_unicode_buffer(256);count=T.DWORD(256)
    require(bind(a,'GetUserNameW',T.BOOL,T.LPWSTR,C.POINTER(T.DWORD))(name,C.byref(count)))
    result['user']=name.value
    session=T.DWORD();require(bind(k,'ProcessIdToSessionId',T.BOOL,T.DWORD,C.POINTER(T.DWORD))(os.getpid(),C.byref(session)))
    result['session_id']=session.value
    station=bind(u,'GetProcessWindowStation',T.HANDLE)()
    info=bind(u,'GetUserObjectInformationW',T.BOOL,T.HANDLE,C.c_int,P,T.DWORD,C.POINTER(T.DWORD))
    name=C.create_unicode_buffer(1024);require(info(station,2,name,C.sizeof(name),C.byref(needed)))
    result['station']=name.value
    class Flags(C.Structure):_fields_=[('inherit',T.BOOL),('reserved',T.BOOL),('flags',T.DWORD)]
    flags=Flags();require(info(station,1,C.byref(flags),C.sizeof(flags),C.byref(needed)))
    result['station_flags']=flags.flags
    security=bind(u,'GetUserObjectSecurity',T.BOOL,T.HANDLE,C.POINTER(T.DWORD),P,T.DWORD,C.POINTER(T.DWORD))
    kind=T.DWORD(4);needed=T.DWORD();security(station,C.byref(kind),None,0,C.byref(needed));assert 0<needed.value<=16384
    data=C.create_string_buffer(needed.value);require(security(station,C.byref(kind),data,needed,C.byref(needed)))
    text=T.LPWSTR();require(bind(a,'ConvertSecurityDescriptorToStringSecurityDescriptorW',T.BOOL,P,T.DWORD,T.DWORD,C.POINTER(T.LPWSTR),P)(data,1,4,C.byref(text),None))
    try:result['station_dacl']=text.value
    finally:free(C.cast(text,P))
    assert result['user_sid']==owner['user_sid'] and result['user'].casefold()=='agents'
    assert result['session_id']==owner['session_id']==3 and result['station']=='WinSta0' and result['station_flags']&1
    result['status']='pass'
except BaseException as error:
    result.update(status='fail',error=repr(error))
    raise
finally:
    if token:bind(k,'CloseHandle',T.BOOL,T.HANDLE)(token)
    (root/'observation.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
