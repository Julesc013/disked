"""Owned 4 MiB guest VHD, nonpermanent read-only attachment and handle transfer.

Administrative setup is separate from the restricted observer. No device path
comes from a fixture or caller; it is resolved from the held virtual-disk object.
"""
import contextlib
import ctypes as C
from ctypes import wintypes as T
import hashlib
import json
import os
from pathlib import Path
import re
import stat
import struct
import uuid

SIZE=4194304

class Guid(C.Structure):
    _fields_=[('a',T.DWORD),('b',T.WORD),('c',T.WORD),('d',T.BYTE*8)]
class Storage(C.Structure):
    _fields_=[('device',T.DWORD),('vendor',Guid)]
class CreateV1(C.Structure):
    _fields_=[('identifier',Guid),('maximum',C.c_uint64),('block',T.DWORD),('sector',T.DWORD),('parent',T.LPCWSTR),('source',T.LPCWSTR)]
class Create(C.Structure):
    _fields_=[('version',T.DWORD),('data',CreateV1)]
class Open(C.Structure):
    _fields_=[('version',T.DWORD),('depth',T.DWORD)]
class Attach(C.Structure):
    _fields_=[('version',T.DWORD),('reserved',T.DWORD)]
class Info(C.Structure):
    _fields_=[('version',T.DWORD),('data',C.c_uint64*16)]
class Luid(C.Structure):
    _fields_=[('low',T.DWORD),('high',T.LONG)]
class Privileges(C.Structure):
    _fields_=[('count',T.DWORD),('luid',Luid),('attributes',T.DWORD)]


def sha(body):return 'sha256:'+hashlib.sha256(body).hexdigest()

class Media:
    def __init__(self,g,work,name,data,expected,abi,report):
        if os.name!='nt' or os.environ.get('COMPUTERNAME')!='BLACKGLASS-HYPE' or g.ROOT!=Path('C:/ProgramData/DiskEd/qualification'):
            raise ValueError('Owned guest only')
        assert name in ('mbr-valid','gpt-valid','gpt-primary-damaged','gpt-conflicting')
        assert type(data) is bytes and len(data)==SIZE and sha(data)==expected
        assert work.drive.upper()=='R:' and work==g.W.plain_directory(work)
        assert abi['pointer_bytes']==8 and abi['create_v1_offset']==Create.data.offset==8
        assert abi['create_v1_bytes']==C.sizeof(CreateV1)==48 and abi['get_info_union_offset']==Info.data.offset==8
        assert abi['attach_flags']==3 and abi['create_flags']==1 and abi['create_access']==0x180000 and abi['open_access']==0xd0000
        self.g,self.work,self.path,self.data,self.expected,self.report=g,work,work/(name+'-api.vhd'),data,expected,report
        self.k=C.WinDLL('kernel32',use_last_error=True);self.a=C.WinDLL('advapi32',use_last_error=True);self.v=C.WinDLL('virtdisk',use_last_error=True)
        bind=g.W.bind;P=C.c_void_p
        bind(self.k,'GetCurrentProcess',T.HANDLE);bind(self.k,'CloseHandle',T.BOOL,T.HANDLE)
        bind(self.k,'CreateFileW',T.HANDLE,T.LPCWSTR,T.DWORD,T.DWORD,P,T.DWORD,T.DWORD,T.HANDLE)
        bind(self.k,'DuplicateHandle',T.BOOL,T.HANDLE,T.HANDLE,T.HANDLE,C.POINTER(T.HANDLE),T.DWORD,T.BOOL,T.DWORD)
        bind(self.a,'OpenProcessToken',T.BOOL,T.HANDLE,T.DWORD,C.POINTER(T.HANDLE))
        bind(self.a,'LookupPrivilegeValueW',T.BOOL,T.LPCWSTR,T.LPCWSTR,C.POINTER(Luid))
        bind(self.a,'AdjustTokenPrivileges',T.BOOL,T.HANDLE,T.BOOL,C.POINTER(Privileges),T.DWORD,C.POINTER(Privileges),C.POINTER(T.DWORD))
        bind(self.v,'CreateVirtualDisk',T.DWORD,C.POINTER(Storage),T.LPCWSTR,T.DWORD,P,T.DWORD,T.DWORD,C.POINTER(Create),P,C.POINTER(T.HANDLE))
        bind(self.v,'OpenVirtualDisk',T.DWORD,C.POINTER(Storage),T.LPCWSTR,T.DWORD,T.DWORD,C.POINTER(Open),C.POINTER(T.HANDLE))
        bind(self.v,'GetVirtualDiskInformation',T.DWORD,T.HANDLE,C.POINTER(T.DWORD),C.POINTER(Info),C.POINTER(T.DWORD))
        bind(self.v,'AttachVirtualDisk',T.DWORD,T.HANDLE,P,T.DWORD,T.DWORD,C.POINTER(Attach),P)
        bind(self.v,'DetachVirtualDisk',T.DWORD,T.HANDLE,T.DWORD,T.DWORD)
        bind(self.v,'GetVirtualDiskPhysicalPath',T.DWORD,T.HANDLE,C.POINTER(T.DWORD),T.LPWSTR)
        self.storage=Storage(2,Guid.from_buffer_copy(uuid.UUID('ec984aec-a0f9-47e9-901f-71415a66345b').bytes_le))
        self.identifier=uuid.uuid4();self.nonce=uuid.uuid4().hex
        self.virtual=T.HANDLE();self.device=T.HANDLE();self.attached=False;self.created=False;self.file_id=None;self.quiescent=True
        report.update(path=str(self.path),attachment_uuid=str(self.identifier),nonce=self.nonce,initial_payload_sha256=expected,
                      bytes=SIZE,attachment_flags=3,permanent_lifetime=False,device_acl_changed=False,transfers=[])

    def require(self,result):self.g.W.require(result)
    def status(self,code):
        if code:raise C.WinError(code)

    @contextlib.contextmanager
    def privilege(self):
        token=T.HANDLE();previous=Privileges();changed=False
        self.require(self.a.OpenProcessToken(self.k.GetCurrentProcess(),0x28,C.byref(token)))
        try:
            wanted=Privileges();wanted.count=1;wanted.attributes=2
            self.require(self.a.LookupPrivilegeValueW(None,'SeManageVolumePrivilege',C.byref(wanted.luid)))
            returned=T.DWORD();C.set_last_error(0)
            self.require(self.a.AdjustTokenPrivileges(token,False,C.byref(wanted),C.sizeof(previous),C.byref(previous),C.byref(returned)))
            if C.get_last_error()==1300:raise RuntimeError('Existing guest coordinator privilege unavailable')
            changed=True;yield
        finally:
            if changed:self.require(self.a.AdjustTokenPrivileges(token,False,C.byref(previous),0,None,None))
            self.k.CloseHandle(token)

    def ordinary(self):
        self.g.W.plain_directory(self.path.parent);info=self.path.lstat()
        assert stat.S_ISREG(info.st_mode) and info.st_nlink==1 and not info.st_file_attributes&0x4c00
        assert info.st_size==SIZE+512
        identity=(info.st_dev,info.st_ino)
        assert self.file_id is None or identity==self.file_id
        self.file_id=identity;return info

    def content(self):
        self.ordinary();payload=hashlib.sha256();whole=hashlib.sha256()
        with self.path.open('rb') as stream:
            left=SIZE
            while left:
                body=stream.read(min(left,65536));assert body;left-=len(body);payload.update(body);whole.update(body)
            footer=stream.read(513);assert len(footer)==512 and footer[:8]==b'conectix'
            assert struct.unpack_from('>Q',footer,48)[0]==SIZE and struct.unpack_from('>I',footer,60)[0]==2
            checksum=struct.unpack_from('>I',footer,64)[0];check=bytearray(footer);check[64:68]=b'\0'*4
            assert checksum==((~sum(check))&0xffffffff)
            whole.update(footer)
        self.ordinary()
        return dict(payload_sha256='sha256:'+payload.hexdigest(),file_sha256='sha256:'+whole.hexdigest(),
                    footer_identifier_hex=footer[68:84].hex(),footer_hex=footer.hex(),file_id=[str(v) for v in self.file_id])

    def info(self,kind):
        result=Info();result.version=kind;size=T.DWORD(C.sizeof(result));used=T.DWORD()
        self.status(self.v.GetVirtualDiskInformation(self.virtual,C.byref(size),C.byref(result),C.byref(used)))
        assert used.value<=C.sizeof(result)
        return C.string_at(C.addressof(result)+Info.data.offset,128)

    def identity(self):
        identifier=uuid.UUID(bytes_le=self.info(2)[:16]);size,physical,block,sector=struct.unpack_from('<QQII',self.info(1))
        assert identifier==self.identifier and size==SIZE and sector==512
        return dict(attachment_uuid=str(identifier),virtual_bytes=size,physical_bytes=physical,sector_bytes=sector,block_bytes=block)

    def physical(self):
        buffer=C.create_unicode_buffer(512);size=T.DWORD(C.sizeof(buffer))
        self.status(self.v.GetVirtualDiskPhysicalPath(self.virtual,C.byref(size),buffer))
        assert re.fullmatch(r'\\\\\.\\PhysicalDrive[0-9]{1,5}',buffer.value,re.I)
        return buffer.value

    def start(self):
        assert not self.path.exists()
        options=Create();options.version=1;options.data.identifier=Guid.from_buffer_copy(self.identifier.bytes_le)
        options.data.maximum=SIZE;options.data.sector=512
        created=T.HANDLE()
        with self.privilege():
            code=self.v.CreateVirtualDisk(C.byref(self.storage),str(self.path),0x180000,None,1,0,C.byref(options),None,C.byref(created))
            self.report['create_code']=code;self.status(code);self.created=True
            try:self.require(self.k.CloseHandle(created))
            finally:created=T.HANDLE()
        self.ordinary()
        with self.path.open('r+b') as stream:
            for offset in range(0,SIZE,65536):stream.write(self.data[offset:offset+65536])
            stream.flush();os.fsync(stream.fileno())
        self.report['before']=self.content();assert self.report['before']['payload_sha256']==self.expected
        options=Open();options.version=1;options.depth=1
        self.status(self.v.OpenVirtualDisk(C.byref(self.storage),str(self.path),0xd0000,0,C.byref(options),C.byref(self.virtual)))
        self.report['identity_before_attach']=self.identity()
        options=Attach();options.version=1
        with self.privilege():self.status(self.v.AttachVirtualDisk(self.virtual,None,3,0,C.byref(options),None))
        self.attached=True;self.report['attached']=True
        self.report['identity_after_attach']=self.identity();self.report['physical_path']=self.physical()
        self.device=self.k.CreateFileW(self.report['physical_path'],0x80000000,3,None,3,0,None)
        if self.device in (None,C.c_void_p(-1).value):self.device=T.HANDLE();raise C.WinError(C.get_last_error())
        self.report['parent_access']='GENERIC_READ';return self

    def transfer(self,process,job):
        assert self.attached and self.identity()['attachment_uuid']==str(self.identifier) and self.physical()==self.report['physical_path']
        handle=T.HANDLE()
        self.require(self.k.DuplicateHandle(self.k.GetCurrentProcess(),self.device,process.process,C.byref(handle),0,False,2))
        self.report['transfers'].append(dict(pid=process.pid,handle=str(handle.value),access='GENERIC_READ',inheritable=False,suspended_job_member=True))
        return (json.dumps(dict(handle=str(handle.value),expected_bytes=str(SIZE),attachment_uuid=str(self.identifier),nonce=self.nonce),separators=(',',':'))+'\n').encode()

    def close(self):
        if not self.quiescent:raise RuntimeError('Preserve owned media: reader job quiescence unknown')
        if self.device:self.require(self.k.CloseHandle(self.device));self.device=T.HANDLE()
        if self.attached:
            self.report['identity_before_detach']=self.identity();assert self.physical()==self.report['physical_path']
            with self.privilege():code=self.v.DetachVirtualDisk(self.virtual,0,0)
            self.report['detach_code']=code;self.status(code);self.attached=False
            path=C.create_unicode_buffer(512);size=T.DWORD(C.sizeof(path))
            code=self.v.GetVirtualDiskPhysicalPath(self.virtual,C.byref(size),path)
            self.report['post_detach_path_error']=code;assert code!=0
        if self.virtual:self.require(self.k.CloseHandle(self.virtual));self.virtual=T.HANDLE()
        if self.created:
            self.report['after']=self.content();self.report['payload_unchanged']=self.report['after']['payload_sha256']==self.expected
            self.ordinary();self.path.unlink();self.report['removed']=not self.path.exists();self.created=False
            assert self.report['payload_unchanged'] and self.report['removed']
