"""Read Windows fixture DACLs directly, without a managed-runtime dependency."""
import ctypes as C
from ctypes import wintypes as T
from pathlib import Path
import struct
import json


def user_only_dacls(paths):
    k=C.WinDLL('kernel32',use_last_error=True);a=C.WinDLL('advapi32',use_last_error=True)
    k.GetCurrentProcess.restype=T.HANDLE;k.CloseHandle.argtypes=[T.HANDLE];k.LocalFree.argtypes=[C.c_void_p];k.LocalFree.restype=C.c_void_p
    a.OpenProcessToken.argtypes=[T.HANDLE,T.DWORD,C.POINTER(T.HANDLE)]
    a.GetTokenInformation.argtypes=[T.HANDLE,C.c_int,C.c_void_p,T.DWORD,C.POINTER(T.DWORD)]
    a.GetFileSecurityW.argtypes=[T.LPCWSTR,T.DWORD,C.c_void_p,T.DWORD,C.POINTER(T.DWORD)]
    a.GetSecurityDescriptorControl.argtypes=[C.c_void_p,C.POINTER(T.WORD),C.POINTER(T.DWORD)]
    a.GetSecurityDescriptorDacl.argtypes=[C.c_void_p,C.POINTER(T.BOOL),C.POINTER(C.c_void_p),C.POINTER(T.BOOL)]
    a.ConvertSidToStringSidW.argtypes=[C.c_void_p,C.POINTER(T.LPWSTR)]
    a.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes=[C.c_void_p,T.DWORD,T.DWORD,C.POINTER(T.LPWSTR),C.POINTER(T.DWORD)]
    a.IsValidSid.argtypes=[C.c_void_p]
    def require(ok):
        if not ok:raise C.WinError(C.get_last_error())
    def sid_text(pointer):
        require(a.IsValidSid(pointer));text=T.LPWSTR();require(a.ConvertSidToStringSidW(pointer,C.byref(text)))
        try:return text.value
        finally:k.LocalFree(C.cast(text,C.c_void_p))
    token=T.HANDLE();require(a.OpenProcessToken(k.GetCurrentProcess(),8,C.byref(token)))
    try:
        size=T.DWORD();a.GetTokenInformation(token,1,None,0,C.byref(size))
        if not 0<size.value<=65536:raise ValueError('Token information bound')
        data=C.create_string_buffer(size.value);require(a.GetTokenInformation(token,1,data,size,C.byref(size)))
        current=sid_text(C.cast(data,C.POINTER(C.c_void_p))[0])
        size=T.DWORD();a.GetTokenInformation(token,25,None,0,C.byref(size))
        if not 0<size.value<=65536:raise ValueError('Token integrity bound')
        data=C.create_string_buffer(size.value);require(a.GetTokenInformation(token,25,data,size,C.byref(size)))
        integrity=sid_text(C.cast(data,C.POINTER(C.c_void_p))[0])
    finally:k.CloseHandle(token)
    files=[]
    for path in map(Path,paths):
        size=T.DWORD();a.GetFileSecurityW(str(path),4,None,0,C.byref(size))
        if not 0<size.value<=65536:raise ValueError('File security descriptor bound')
        data=C.create_string_buffer(size.value);require(a.GetFileSecurityW(str(path),4,data,size,C.byref(size)))
        control=T.WORD();revision=T.DWORD();require(a.GetSecurityDescriptorControl(data,C.byref(control),C.byref(revision)))
        present=T.BOOL();defaulted=T.BOOL();acl=C.c_void_p()
        require(a.GetSecurityDescriptorDacl(data,C.byref(present),C.byref(acl),C.byref(defaulted)))
        if not present.value or not acl.value:raise ValueError('Missing or null fixture DACL')
        start=C.addressof(data);offset=acl.value-start
        if not 0<=offset<=len(data)-8:raise ValueError('DACL pointer bound')
        header=C.string_at(acl,8);_,_,length,count,_=struct.unpack('<BBHHH',header)
        if not 8<=length<=len(data)-offset or count>64:raise ValueError('DACL size bound')
        rows=[];at=8
        for _ in range(count):
            if at+8>length:raise ValueError('ACE header bound')
            kind,flags,n,mask=struct.unpack('<BBHI',C.string_at(acl.value+at,8))
            if kind not in (0,1) or n<20 or at+n>length:raise ValueError('ACE form or size')
            sid_header=C.string_at(acl.value+at+8,8)
            if sid_header[0]!=1 or 8+sid_header[1]*4!=n-8:raise ValueError('ACE SID bound')
            rows.append(dict(sid=sid_text(acl.value+at+8),type='Allow' if kind==0 else 'Deny',
                             rights=mask,inherited=bool(flags&0x10)))
            at+=n
        label_size=T.DWORD();a.GetFileSecurityW(str(path),0x10,None,0,C.byref(label_size))
        if not 0<label_size.value<=65536:raise ValueError('File label bound')
        label_data=C.create_string_buffer(label_size.value)
        require(a.GetFileSecurityW(str(path),0x10,label_data,label_size,C.byref(label_size)))
        label=T.LPWSTR();require(a.ConvertSecurityDescriptorToStringSecurityDescriptorW(label_data,1,0x10,C.byref(label),None))
        try:label_text=label.value
        finally:k.LocalFree(C.cast(label,C.c_void_p))
        files.append(dict(name=path.name,protected=bool(control.value&0x1000),aces=rows,label=label_text))
    return dict(current_sid=current,integrity_sid=integrity,files=files)


class DaclFixture:
    """Create one new scratch object and retain its permission-restoration handle.

    Only generated fixtures receive the actor/restricted-code creation grants.
    Denial removes those grants while keeping SYSTEM/admin recovery possible.
    Product records, existing objects and directories outside managed temp are
    never changed. The handle restores the original descriptor even when new
    path-based security opens are denied by the deliberately narrowed DACL.
    """
    def __init__(self,path,*,directory=False):
        from support.tempdir import fixture_parent
        self.path=Path(path).absolute();self.directory=directory;self.handle=None
        parent=self.path.parent.resolve(strict=True)
        if not parent.is_relative_to(fixture_parent().resolve()) or self.path.exists():
            raise ValueError('DACL fixture must be a new object in managed temp')
        self.sid=user_only_dacls([])['current_sid']
        self.k=C.WinDLL('kernel32',use_last_error=True);self.a=C.WinDLL('advapi32',use_last_error=True)
        self.k.CreateFileW.argtypes=[T.LPCWSTR,T.DWORD,T.DWORD,C.c_void_p,T.DWORD,T.DWORD,T.HANDLE]
        self.k.CreateFileW.restype=T.HANDLE
        self.k.CreateDirectoryW.argtypes=[T.LPCWSTR,C.c_void_p]
        self.k.GetFileInformationByHandleEx.argtypes=[T.HANDLE,C.c_int,C.c_void_p,T.DWORD]
        self.k.CloseHandle.argtypes=[T.HANDLE]
        self.k.LocalFree.argtypes=[C.c_void_p];self.k.LocalFree.restype=C.c_void_p
        self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[T.LPCWSTR,T.DWORD,C.POINTER(C.c_void_p),C.POINTER(T.DWORD)]
        self.a.GetSecurityDescriptorDacl.argtypes=[C.c_void_p,C.POINTER(T.BOOL),C.POINTER(C.c_void_p),C.POINTER(T.BOOL)]
        self.a.SetSecurityInfo.argtypes=[T.HANDLE,C.c_int,T.DWORD,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p]
        self.a.SetSecurityInfo.restype=T.DWORD
        self.original=self._descriptor('FA')

    @staticmethod
    def _require(ok):
        if not ok:raise C.WinError(C.get_last_error())

    def _descriptor(self,rights):
        flags='OICI' if self.directory else ''
        text='D:P(A;'+flags+';FA;;;SY)(A;'+flags+';FA;;;BA)'
        if rights:
            text+='(A;'+flags+';'+rights+';;;'+self.sid+')(A;'+flags+';'+rights+';;;RC)'
        value=C.c_void_p()
        self._require(self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(text,1,C.byref(value),None))
        return value

    def __enter__(self):
        class Attributes(C.Structure):
            _fields_=[('length',T.DWORD),('descriptor',C.c_void_p),('inherit',T.BOOL)]
        attributes=Attributes(C.sizeof(Attributes),self.original,False)
        phase='create_directory' if self.directory else 'create_data'
        try:
            identity=None
            if self.directory:self._require(self.k.CreateDirectoryW(str(self.path),C.byref(attributes)))
            else:
                # Create data first, then request security access against the
                # installed descriptor. Bind the two handles to the same file.
                created=self.k.CreateFileW(str(self.path),0x40000000,7,C.byref(attributes),1,0x80,None)
                self._require(created not in (None,C.c_void_p(-1).value))
                try:identity=self._identity(created)
                finally:self.k.CloseHandle(created)
            phase='reopen_security'
            self.handle=self.k.CreateFileW(str(self.path),0x60000,7,None,3,0x02200000,None)
            self._require(self.handle not in (None,C.c_void_p(-1).value))
            if identity is not None and self._identity(self.handle)!=identity:
                raise ValueError('DACL fixture file identity changed')
            return self
        except BaseException as error:
            if self.handle not in (None,C.c_void_p(-1).value):self.k.CloseHandle(self.handle)
            self.handle=None
            self.k.LocalFree(self.original);self.original=None
            diagnostic=dict(phase=phase,sid=self.sid,path_exists=self.path.exists())
            try:diagnostic['actual_dacl']=user_only_dacls([self.path if self.path.exists() else self.path.parent])
            except OSError as observation_error:diagnostic['observation_error']=str(observation_error)
            if self.path.exists():
                # Read-only observations of alternative opens on this single
                # failed fixture; no permission mutation, fallback or pass.
                diagnostic['open_observations']=[]
                for flags in ((0x02200000,) if self.directory else (0,0x00200000,0x02200000)):
                    for access in (0x20000,0x40000,0x60080,0x80040000):
                        handle=self.k.CreateFileW(str(self.path),access,7,None,3,flags,None)
                        opened=handle not in (None,C.c_void_p(-1).value)
                        code=0 if opened else C.get_last_error()
                        if opened:self.k.CloseHandle(handle)
                        diagnostic['open_observations'].append(dict(access=hex(access),flags=hex(flags),opened=opened,code=code))
            raise RuntimeError('Owned DACL fixture setup: '+json.dumps(diagnostic)) from error

    def _identity(self,handle):
        class Identity(C.Structure):
            _fields_=[('volume',C.c_ulonglong),('file',C.c_ubyte*16)]
        value=Identity()
        self._require(self.k.GetFileInformationByHandleEx(handle,18,C.byref(value),C.sizeof(value)))
        return value.volume,bytes(value.file)

    def restrict(self,rights=None):
        if self.handle in (None,C.c_void_p(-1).value):raise ValueError('Fixture is not open')
        descriptor=self._descriptor(rights)
        try:self._apply(descriptor)
        finally:self.k.LocalFree(descriptor)

    def _apply(self,descriptor):
        present=T.BOOL();defaulted=T.BOOL();acl=C.c_void_p()
        self._require(self.a.GetSecurityDescriptorDacl(descriptor,C.byref(present),C.byref(acl),C.byref(defaulted)))
        if not present.value or not acl.value:raise ValueError('Fixture must retain a non-null DACL')
        error=self.a.SetSecurityInfo(self.handle,1,0x80000004,None,None,acl,None)
        if error:raise C.WinError(error)

    def __exit__(self,*_):
        try:self._apply(self.original)
        finally:
            self.k.CloseHandle(self.handle);self.handle=None
            self.k.LocalFree(self.original);self.original=None


if __name__=='__main__':
    import json
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from support.tempdir import managed_directory
    if sys.argv[1:]!=['--fixture-proof']:raise ValueError('Expected bounded fixture proof')
    with managed_directory(prefix='disked-dacl-proof-') as folder:
        root=Path(folder);source=root/'source.bin'
        with DaclFixture(source) as security:
            source.write_bytes(b'fixture')
            before=user_only_dacls([source])
            security.restrict()
            try:source.read_bytes()
            except PermissionError as error:assert error.winerror==5
            else:raise AssertionError('Denied source remained readable')
        assert source.read_bytes()==b'fixture' and user_only_dacls([source])==before
        directory=root/'metadata-only'
        with DaclFixture(directory,directory=True) as security:
            security.restrict('0x1200a0')
            handle=security.k.CreateFileW(str(directory),0x80,7,None,3,0x02200000,None)
            security._require(handle not in (None,C.c_void_p(-1).value));security.k.CloseHandle(handle)
            handle=security.k.CreateFileW(str(directory),1,7,None,3,0x02200000,None)
            assert handle==C.c_void_p(-1).value and C.get_last_error()==5
        assert list(directory.iterdir())==[]
    print(json.dumps(dict(passed=True,source_denied=True,metadata_only_allowed=True,
        list_denied=True,source_dacl_restored=True,owned_cleanup=True)))
