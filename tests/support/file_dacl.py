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
    """Create a marked fixture; the private coordinator holds/restores its DACL.

    The restricted test process receives no WRITE_DAC handle or credential.
    Only new managed-temp objects with a fixed marker descriptor are eligible.
    """
    def __init__(self,path,*,directory=False):
        from support.tempdir import fixture_parent
        import os
        import uuid
        self.path=Path(path).absolute();self.directory=directory;self.held=False
        parent=self.path.parent.resolve(strict=True)
        if not parent.is_relative_to(fixture_parent().resolve()) or self.path.exists():
            raise ValueError('DACL fixture must be a new object in managed temp')
        self.control=Path(os.environ['DISKED_DACL_FIXTURE_CONTROL']).resolve(strict=True)
        if not self.control.is_relative_to(Path(os.environ['DISKED_WORK_ROOT']).resolve()):
            raise ValueError('Fixture coordinator outside owned workspace')
        self.nonce=os.environ['DISKED_DACL_FIXTURE_NONCE'];self.ident=uuid.uuid4().hex
        self.sid=user_only_dacls([])['current_sid']
        self.k=C.WinDLL('kernel32',use_last_error=True);self.a=C.WinDLL('advapi32',use_last_error=True)
        self.k.CreateFileW.argtypes=[T.LPCWSTR,T.DWORD,T.DWORD,C.c_void_p,T.DWORD,T.DWORD,T.HANDLE];self.k.CreateFileW.restype=T.HANDLE
        self.k.CreateDirectoryW.argtypes=[T.LPCWSTR,C.c_void_p]
        self.k.GetFileInformationByHandleEx.argtypes=[T.HANDLE,C.c_int,C.c_void_p,T.DWORD]
        self.k.CloseHandle.argtypes=[T.HANDLE];self.k.LocalFree.argtypes=[C.c_void_p];self.k.LocalFree.restype=C.c_void_p
        self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[T.LPCWSTR,T.DWORD,C.POINTER(C.c_void_p),C.POINTER(T.DWORD)]
        flags='OICI' if directory else ''
        text='D:P(A;'+flags+';FA;;;SY)(A;'+flags+';FA;;;BA)(A;'+flags+';FA;;;'+self.sid+')(A;'+flags+';FA;;;RC)'
        self.descriptor=C.c_void_p()
        self._require(self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(text,1,C.byref(self.descriptor),None))

    @staticmethod
    def _require(ok):
        if not ok:raise C.WinError(C.get_last_error())

    def _identity(self,handle):
        class Identity(C.Structure):
            _fields_=[('volume',C.c_ulonglong),('file',C.c_ubyte*16)]
        value=Identity();self._require(self.k.GetFileInformationByHandleEx(handle,18,C.byref(value),C.sizeof(value)))
        return str(value.volume),bytes(value.file).hex()

    def _call(self,action,**fields):
        import os
        import time
        import uuid
        request_id=uuid.uuid4().hex
        value=dict(nonce=self.nonce,request_id=request_id,fixture_id=self.ident,action=action,**fields)
        body=json.dumps(value,separators=(',',':')).encode('utf-8')
        if len(body)>4096:raise ValueError('Fixture packet bound')
        pending=self.control/('request-'+request_id+'.pending')
        request=pending.with_suffix('.json');response=self.control/('response-'+request_id+'.json')
        with pending.open('xb') as stream:stream.write(body)
        os.replace(pending,request);deadline=time.monotonic()+8
        while not response.exists():
            if time.monotonic()>=deadline:raise TimeoutError('Owned fixture coordinator response')
            time.sleep(.02)
        if response.stat().st_size>4096:raise ValueError('Fixture response bound')
        result=json.loads(response.read_bytes());response.unlink()
        if result!=dict(nonce=self.nonce,request_id=request_id,ok=True):raise ValueError('Fixture acknowledgement identity')

    def __enter__(self):
        class Attributes(C.Structure):
            _fields_=[('length',T.DWORD),('descriptor',C.c_void_p),('inherit',T.BOOL)]
        attributes=Attributes(C.sizeof(Attributes),self.descriptor,False);handle=None
        try:
            if self.directory:
                self._require(self.k.CreateDirectoryW(str(self.path),C.byref(attributes)))
                handle=self.k.CreateFileW(str(self.path),0x80,7,None,3,0x02200000,None)
            else:handle=self.k.CreateFileW(str(self.path),0x40000000,7,C.byref(attributes),1,0x80,None)
            self._require(handle not in (None,C.c_void_p(-1).value))
            volume,file_id=self._identity(handle)
            self.k.CloseHandle(handle);handle=None
            self._call('hold',path=str(self.path),volume=volume,file_id=file_id,directory=self.directory)
            self.held=True
            return self
        except BaseException:
            if handle not in (None,C.c_void_p(-1).value):self.k.CloseHandle(handle)
            self.k.LocalFree(self.descriptor);self.descriptor=None
            raise

    def restrict(self,rights=None):
        if not self.held:raise ValueError('Fixture is not held')
        if rights not in (None,'0x1200a0') or (rights is not None)!=self.directory:
            raise ValueError('Only declared file denial or directory metadata access is supported')
        self._call('narrow',mode='metadata_only' if self.directory else 'denied')

    def __exit__(self,*_):
        try:self._call('restore')
        finally:self.held=False;self.k.LocalFree(self.descriptor);self.descriptor=None


if __name__=='__main__':
    import json
    import sys
    sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
    from support.tempdir import managed_directory
    if sys.argv[1:] not in (['--fixture-proof'],['--fixture-interrupt-proof']):raise ValueError('Expected bounded fixture proof')
    with managed_directory(prefix='disked-dacl-proof-') as folder:
        root=Path(folder);source=root/'source.bin'
        with DaclFixture(source) as security:
            source.write_bytes(b'fixture')
            before=user_only_dacls([source])
            security.restrict()
            try:source.read_bytes()
            except PermissionError as error:assert error.winerror==5
            else:raise AssertionError('Denied source remained readable')
            if sys.argv[1]=='--fixture-interrupt-proof':
                import os
                os._exit(19)
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
