"""Trusted, finite payload for the owned ordinary-token storage proof."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time

k, a = [C.WinDLL(n, use_last_error=True) for n in ('kernel32', 'advapi32')]
P = C.c_void_p

def bind(dll, name, result, *args):
    f = getattr(dll, name); f.restype, f.argtypes = result, list(args); return f

def require(ok):
    if not ok: raise C.WinError(C.get_last_error())
    return ok

bind(k, 'GetCurrentProcess', T.HANDLE)
bind(k, 'CloseHandle', T.BOOL, T.HANDLE)
bind(k, 'LocalFree', P, P)
bind(k, 'CreateFileW', T.HANDLE, T.LPCWSTR, T.DWORD, T.DWORD, P, T.DWORD, T.DWORD, T.HANDLE)
bind(k, 'WriteFile', T.BOOL, T.HANDLE, P, T.DWORD, C.POINTER(T.DWORD), P)
bind(k, 'GetTempPathW', T.DWORD, T.DWORD, T.LPWSTR)
bind(k, 'GetStdHandle', T.HANDLE, T.DWORD)
bind(k, 'GetFileType', T.DWORD, T.HANDLE)
bind(k, 'GetFileInformationByHandleEx', T.BOOL, T.HANDLE, C.c_int, P, T.DWORD)
bind(a, 'OpenProcessToken', T.BOOL, T.HANDLE, T.DWORD, C.POINTER(T.HANDLE))
bind(a, 'GetTokenInformation', T.BOOL, T.HANDLE, C.c_int, P, T.DWORD, C.POINTER(T.DWORD))
bind(a, 'ConvertSidToStringSidW', T.BOOL, P, C.POINTER(T.LPWSTR))
bind(a, 'IsTokenRestricted', T.BOOL, T.HANDLE)
bind(a, 'LookupPrivilegeNameW', T.BOOL, T.LPCWSTR, P, T.LPWSTR, C.POINTER(T.DWORD))
bind(a, 'ConvertStringSecurityDescriptorToSecurityDescriptorW', T.BOOL, T.LPCWSTR, T.DWORD, C.POINTER(P), P)
bind(a, 'GetNamedSecurityInfoW', T.DWORD, T.LPWSTR, C.c_int, T.DWORD, P, P, P, P, C.POINTER(P))
bind(a, 'ConvertSecurityDescriptorToStringSecurityDescriptorW', T.BOOL, P, T.DWORD, T.DWORD, C.POINTER(T.LPWSTR), P)

class Sid(C.Structure):
    _fields_ = [('sid', P), ('attributes', T.DWORD)]

class Groups(C.Structure):
    _fields_ = [('count', T.DWORD), ('first', Sid)]

class Luid(C.Structure):
    _fields_ = [('low', T.DWORD), ('high', T.LONG)]

class Privilege(C.Structure):
    _fields_ = [('luid', Luid), ('attributes', T.DWORD)]

class Privileges(C.Structure):
    _fields_ = [('count', T.DWORD), ('first', Privilege)]

class FileIdentity(C.Structure):
    _fields_ = [('volume', C.c_ulonglong), ('identity', C.c_ubyte*16)]

def string_sid(value):
    text = T.LPWSTR(); require(a.ConvertSidToStringSidW(value, C.byref(text)))
    try: return text.value
    finally: k.LocalFree(C.cast(text, P))

def identity():
    token, size = T.HANDLE(), T.DWORD()
    require(a.OpenProcessToken(k.GetCurrentProcess(), 8, C.byref(token)))
    try:
        result = dict(pid=os.getpid(), restricted=bool(a.IsTokenRestricted(token)), administrator=bool(C.windll.shell32.IsUserAnAdmin()))
        for kind, key in ((20, 'elevated'), (29, 'appcontainer')):
            v = T.DWORD(); require(a.GetTokenInformation(token, kind, C.byref(v), 4, C.byref(size))); result[key] = v.value
        for kind, key in ((1, 'user_sid'), (11, 'restricting_sid')):
            a.GetTokenInformation(token, kind, None, 0, C.byref(size))
            assert 0 < size.value <= 4096
            data = C.create_string_buffer(size.value)
            require(a.GetTokenInformation(token, kind, data, size, C.byref(size)))
            if kind == 1: sid = C.cast(data, C.POINTER(Sid)).contents.sid
            else:
                groups = C.cast(data, C.POINTER(Groups)).contents
                assert groups.count == 1; sid = groups.first.sid
            result[key] = string_sid(sid)
        a.GetTokenInformation(token,3,None,0,C.byref(size));assert 0 < size.value <= 16384
        data=C.create_string_buffer(size.value)
        require(a.GetTokenInformation(token,3,data,size,C.byref(size)))
        count=C.cast(data,C.POINTER(Privileges)).contents.count;assert count<=128
        result['privileges']=[]
        for index in range(count):
            value=Privilege.from_buffer(data,Privileges.first.offset+index*C.sizeof(Privilege))
            text,length=C.create_unicode_buffer(256),T.DWORD(256)
            require(a.LookupPrivilegeNameW(None,C.byref(value.luid),text,C.byref(length)))
            result['privileges'].append(dict(name=text.value,attributes=value.attributes))
        assert all(p['name']=='SeChangeNotifyPrivilege' for p in result['privileges'] if p['attributes']&2)
        return result
    finally: require(k.CloseHandle(token))

def denied(path, new=False):
    h = k.CreateFileW(str(path), 0x40000000, 3, None, 1 if new else 3, 0x80, None)
    error = C.get_last_error()
    if h != C.c_void_p(-1).value: require(k.CloseHandle(h))
    return dict(path=str(path), denied=h == C.c_void_p(-1).value, winerror=error)

def main():
    plan = json.loads(Path(sys.argv[1]).read_bytes())
    mode = sys.argv[2] if len(sys.argv)>2 else 'normal'
    result = identity()
    assert result['restricted'] and not any(result[k] for k in ('administrator','elevated','appcontainer'))
    assert result['user_sid'] == result['restricting_sid'] == plan['user_sid']
    if mode == 'launch':
        result['stdio']=[]
        for which in (0xfffffff6,0xfffffff5,0xfffffff4):
            handle=k.GetStdHandle(which);C.set_last_error(0)
            kind=k.GetFileType(handle)
            result['stdio'].append(dict(selector=which,kind=kind,winerror=C.get_last_error()))
        info=FileIdentity()
        ok=k.GetFileInformationByHandleEx(plan['canary_handle'],18,C.byref(info),C.sizeof(info))
        result['canary_inherited']=bool(ok and info.volume==plan['canary_volume'] and bytes(info.identity).hex()==plan['canary_identity'])
        result['variant']=plan['variant']
        Path('launch-'+plan['variant']+'.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
        return
    if mode == 'descendant':
        result['outside'] = denied(Path(plan['outside'])/'descendant-forbidden', True)
        assert result['outside']['denied'] and result['outside']['winerror'] == 5
        print(json.dumps(result)); return
    if mode == 'sleep':
        with Path('descendant-held.bin').open('xb') as stream:
            stream.write(b'owned'); stream.flush()
            Path('descendant.json').write_text(json.dumps(result))
            time.sleep(30)
        return
    if mode == 'hold':
        child = subprocess.Popen([sys.executable,'-B',__file__,sys.argv[1],'sleep'])
        h = k.CreateFileW(str(Path.cwd()/'held.bin'), 0x40000000, 0, None, 1, 0x80, None)
        if h == C.c_void_p(-1).value: raise C.WinError(C.get_last_error())
        try:
            result['descendant_pid'] = child.pid
            Path('hold.json').write_text(json.dumps(result))
            time.sleep(30)
        finally: require(k.CloseHandle(h))
        return
    assert mode == 'normal'
    root = Path.cwd().resolve()
    native = C.create_unicode_buffer(32768); length = k.GetTempPathW(len(native),native)
    assert 0 < length < len(native)
    result['native_temp'], result['python_temp'] = native.value, tempfile.gettempdir()
    for value in [native.value, tempfile.gettempdir(), *[os.environ[k] for k in ('TEMP','TMP','TMPDIR')]]:
        assert Path(value).resolve().is_relative_to(root)
    result['outside'] = [denied(Path(plan['outside'])/'forbidden', True), denied(plan['source']), denied(plan['backing'])]
    assert all(r['denied'] and r['winerror'] == 5 for r in result['outside'])
    child = subprocess.run([sys.executable,'-B',__file__,sys.argv[1],'descendant'],capture_output=True,timeout=10)
    assert child.returncode == 0
    result['descendant'] = json.loads(child.stdout)
    descriptor = P()
    expected = 'D:P(A;;FA;;;SY)(A;;FA;;;' + result['user_sid'] + ')'
    require(a.ConvertStringSecurityDescriptorToSecurityDescriptorW(expected,1,C.byref(descriptor),None))
    class SA(C.Structure):
        _fields_ = [('size',T.DWORD),('descriptor',P),('inherit',T.BOOL)]
    attributes = SA(C.sizeof(SA),descriptor,False)
    record = root/'user-only.bin'
    h = k.CreateFileW(str(record),0xc0000000,3,C.byref(attributes),1,0x80,None)
    k.LocalFree(descriptor)
    if h == C.c_void_p(-1).value: raise C.WinError(C.get_last_error())
    try:
        count = T.DWORD(); require(k.WriteFile(h,C.create_string_buffer(b'one'),3,C.byref(count),None)); assert count.value == 3
    finally: require(k.CloseHandle(h))
    assert record.read_bytes() == b'one'
    with record.open('r+b') as stream: stream.write(b'TWO'); stream.flush(); os.fsync(stream.fileno())
    assert record.read_bytes() == b'TWO'
    actual, text = P(), T.LPWSTR()
    error = a.GetNamedSecurityInfoW(str(record),1,4,None,None,None,None,C.byref(actual))
    if error: raise C.WinError(error)
    try:
        require(a.ConvertSecurityDescriptorToStringSecurityDescriptorW(actual,1,4,C.byref(text),None))
        result['record_sddl'] = text.value
        assert text.value == expected
    finally:
        if text: k.LocalFree(C.cast(text,P))
        if actual: k.LocalFree(actual)
    result['record_sha256'] = hashlib.sha256(record.read_bytes()).hexdigest()
    result['space_before'] = shutil.disk_usage(root)._asdict()
    assert result['space_before']['total'] <= 32*1024*1024
    payload = root/'capacity.bin'; allocated, full_error = 0, None
    h = k.CreateFileW(str(payload),0x40000000,3,None,1,0x80000080,None)
    if h == C.c_void_p(-1).value: raise C.WinError(C.get_last_error())
    try:
        block = C.create_string_buffer(b'\xa5'*65536)
        for _ in range(1024):
            count = T.DWORD()
            if not k.WriteFile(h,block,65536,C.byref(count),None):
                full_error=C.get_last_error();result['failed_write_bytes']=count.value;break
            assert count.value == 65536; allocated += count.value
        result.update(bytes_written=allocated,allocation_error=full_error,space_full=shutil.disk_usage(root)._asdict())
        assert full_error in (39,112) and 0 < allocated < 32*1024*1024
    finally:
        require(k.CloseHandle(h)); payload.unlink()
    result['space_after_removal'] = shutil.disk_usage(root)._asdict()
    assert result['space_after_removal']['free'] > result['space_full']['free']
    result['status'] = 'pass'
    Path('payload-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print('ordinary-worker-proof-output',flush=True)

if __name__ == '__main__': main()
