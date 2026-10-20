"""Private coordinator for narrowing/restoring new capped-volume test fixtures.

No worker credential, arbitrary descriptor, existing product-record grant or
path outside the owned native temp filesystem is accepted.
"""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import uuid

HEX=re.compile(r'[0-9a-f]{32}\Z')


def fixture_path(value,temp):
    path=Path(value)
    if (not path.is_absolute() or path.drive.casefold()!=temp.drive.casefold()
            or path==temp or not path.is_relative_to(temp)
            or any(part in ('.','..') or ':' in part or part.endswith((' ','.')) for part in path.parts[1:])):
        raise ValueError('Fixture outside owned temp')
    return path


def validate_request(value,nonce):
    if not isinstance(value,dict):raise ValueError('Fixture request object required')
    base={'nonce','request_id','fixture_id','action'}
    action=value.get('action')
    extra={'path','volume','file_id','directory'} if action=='hold' else {'mode'} if action=='narrow' else set()
    if action not in ('hold','narrow','restore') or set(value)!=base|extra:
        raise ValueError('Fixture request fields')
    if value['nonce']!=nonce or not all(isinstance(value[k],str) and HEX.fullmatch(value[k]) for k in ('request_id','fixture_id')):
        raise ValueError('Fixture request identity')
    if action=='hold':
        if (not isinstance(value['path'],str) or len(value['path'])>1024 or '\0' in value['path']
                or type(value['directory']) is not bool or not isinstance(value['volume'],str)
                or not value['volume'].isascii() or not value['volume'].isdecimal()
                or len(value['volume'])>20 or int(value['volume'])>2**64-1
                or str(int(value['volume']))!=value['volume']
                or not isinstance(value['file_id'],str) or not HEX.fullmatch(value['file_id'])):
            raise ValueError('Fixture object identity')
    if action=='narrow' and value['mode'] not in ('denied','metadata_only'):
        raise ValueError('Fixture narrowing mode')
    return action


class Broker:
    def __init__(self,work,temp,actor_sid):
        self.root=Path(work)/'fixture-dacl-control';self.root.mkdir()
        self.temp=Path(temp).resolve(strict=True);self.actor=actor_sid
        if not 0<shutil.disk_usage(self.temp).total<=512*1024*1024:raise ValueError('Capped fixture filesystem required')
        self.held={};self.audit=[];self.seen=set();self.nonce=None
        self.k=C.WinDLL('kernel32',use_last_error=True);self.a=C.WinDLL('advapi32',use_last_error=True)
        self.k.CreateFileW.argtypes=[T.LPCWSTR,T.DWORD,T.DWORD,C.c_void_p,T.DWORD,T.DWORD,T.HANDLE];self.k.CreateFileW.restype=T.HANDLE
        self.k.CloseHandle.argtypes=[T.HANDLE];self.k.LocalFree.argtypes=[C.c_void_p];self.k.LocalFree.restype=C.c_void_p
        self.k.GetFileInformationByHandleEx.argtypes=[T.HANDLE,C.c_int,C.c_void_p,T.DWORD]
        self.k.GetFinalPathNameByHandleW.argtypes=[T.HANDLE,T.LPWSTR,T.DWORD,T.DWORD];self.k.GetFinalPathNameByHandleW.restype=T.DWORD
        self.a.GetSecurityInfo.argtypes=[T.HANDLE,C.c_int,T.DWORD,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,C.POINTER(C.c_void_p)];self.a.GetSecurityInfo.restype=T.DWORD
        self.a.GetSecurityDescriptorDacl.argtypes=[C.c_void_p,C.POINTER(T.BOOL),C.POINTER(C.c_void_p),C.POINTER(T.BOOL)]
        self.a.GetSecurityDescriptorControl.argtypes=[C.c_void_p,C.POINTER(T.WORD),C.POINTER(T.DWORD)]
        self.a.ConvertSidToStringSidW.argtypes=[C.c_void_p,C.POINTER(T.LPWSTR)]
        self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW.argtypes=[T.LPCWSTR,T.DWORD,C.POINTER(C.c_void_p),C.POINTER(T.DWORD)]
        self.a.SetSecurityInfo.argtypes=[T.HANDLE,C.c_int,T.DWORD,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p];self.a.SetSecurityInfo.restype=T.DWORD
        handle=self._open(self.temp,0x80)
        try:self.volume=self._identity(handle)[0]
        finally:self.k.CloseHandle(handle)
        # Pin the endpoint and its owned work root against replacement. Child
        # file creation remains allowed; write-data/delete directory opens do not.
        self.pins=[self._open(Path(work).parent,0x81,share=1)]
        try:
            self.pins.append(self._open(Path(work),0x81,share=1))
            self.pins.append(self._open(self.root,0x81,share=1))
        except BaseException:
            for pinned in self.pins:self.k.CloseHandle(pinned)
            self.pins=[];raise

    @staticmethod
    def _require(ok):
        if not ok:raise C.WinError(C.get_last_error())

    def _open(self,path,access,*,share=3):
        handle=self.k.CreateFileW(str(path),access,share,None,3,0x02200000,None)
        self._require(handle not in (None,C.c_void_p(-1).value))
        return handle

    def _identity(self,handle):
        class Identity(C.Structure):
            _fields_=[('volume',C.c_ulonglong),('file',C.c_ubyte*16)]
        value=Identity();self._require(self.k.GetFileInformationByHandleEx(handle,18,C.byref(value),C.sizeof(value)))
        return str(value.volume),bytes(value.file).hex()

    def _form(self,handle):
        class Standard(C.Structure):
            _fields_=[('allocated',C.c_longlong),('size',C.c_longlong),('links',T.DWORD),('deleting',T.BYTE),('directory',T.BYTE)]
        class Tag(C.Structure):
            _fields_=[('attributes',T.DWORD),('tag',T.DWORD)]
        standard=Standard();tag=Tag()
        self._require(self.k.GetFileInformationByHandleEx(handle,1,C.byref(standard),C.sizeof(standard)))
        self._require(self.k.GetFileInformationByHandleEx(handle,9,C.byref(tag),C.sizeof(tag)))
        return standard,tag

    def _final(self,handle):
        value=C.create_unicode_buffer(2048);n=self.k.GetFinalPathNameByHandleW(handle,value,len(value),0)
        if not 0<n<len(value):raise ValueError('Fixture canonical path bound')
        path=value.value
        if path.startswith('\\\\?\\'):path=path[4:]
        return Path(path)

    def _acl(self,descriptor):
        present=T.BOOL();defaulted=T.BOOL();acl=C.c_void_p()
        self._require(self.a.GetSecurityDescriptorDacl(descriptor,C.byref(present),C.byref(acl),C.byref(defaulted)))
        if not present.value or not acl.value:raise ValueError('Fixture non-null DACL required')
        return acl

    def _descriptor(self,entry,mode):
        flags='OICI' if entry['directory'] else ''
        text='D:P(A;'+flags+';FA;;;SY)(A;'+flags+';FA;;;BA)'
        if mode!='denied':
            rights='FA' if mode=='original' else '0x1200a0'
            text+='(A;'+flags+';'+rights+';;;'+self.actor+')(A;'+flags+';'+rights+';;;RC)'
        value=C.c_void_p();self._require(self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(text,1,C.byref(value),None))
        return value

    def _set(self,entry,descriptor):
        if self._identity(entry['handle'])!=entry['identity']:raise ValueError('Held fixture identity changed')
        error=self.a.SetSecurityInfo(entry['handle'],1,0x80000004,None,None,self._acl(descriptor),None)
        if error:raise C.WinError(error)
        actual=C.c_void_p()
        error=self.a.GetSecurityInfo(entry['handle'],1,4,None,None,None,None,C.byref(actual))
        if error:raise C.WinError(error)
        try:
            control=T.WORD();revision=T.DWORD()
            self._require(self.a.GetSecurityDescriptorControl(actual,C.byref(control),C.byref(revision)))
            if not control.value&0x1000 or self._acl_bytes(actual)!=self._acl_bytes(descriptor):
                raise ValueError('Fixture DACL verification failed')
        finally:self.k.LocalFree(actual)

    def _acl_bytes(self,descriptor):
        acl=self._acl(descriptor);size=int.from_bytes(C.string_at(acl.value+2,2),'little')
        if not 8<=size<=4096:raise ValueError('Fixture ACL bound')
        return C.string_at(acl,size)

    def start_job(self,env):
        if self.held or list(self.root.iterdir()):raise ValueError('Fixture control not retired')
        self.nonce=uuid.uuid4().hex;self.audit=[];self.seen=set()
        env.update(DISKED_DACL_FIXTURE_CONTROL=str(self.root),DISKED_DACL_FIXTURE_NONCE=self.nonce)

    def prove_refusals(self,forbidden):
        """Coordinator controls before any test child; all writes stay in temp."""
        if self.held:raise ValueError('Fixture controls require an idle coordinator')
        source=self.temp/('coordinator-scope-'+uuid.uuid4().hex+'.bin')
        source.write_bytes(b'bounded fixture scope')
        link=source.with_suffix('.link');descriptor=C.c_void_p();observed=[]
        handle=self._open(source,0x20080)
        try:
            identity=self._identity(handle)
            error=self.a.GetSecurityInfo(handle,1,4,None,None,None,None,C.byref(descriptor))
            if error:raise C.WinError(error)
            before=self._acl_bytes(descriptor)
        finally:
            self.k.CloseHandle(handle)
            if descriptor:self.k.LocalFree(descriptor)
        base=dict(fixture_id='0'*32,path=str(source),volume=identity[0],file_id=identity[1],directory=False)
        cases=[('outside',dict(base,path=str(forbidden)),'outside owned temp'),
               ('wrong_identity',dict(base,file_id='f'*32),'identity mismatch'),
               ('unmarked',base,'marked fixture DACL')]
        try:
            for name,value,reason in cases:
                try:self._hold(value)
                except ValueError as error:
                    if reason not in str(error):raise
                    observed.append(name)
                else:raise AssertionError('Fixture control was not refused: '+name)
            os.link(source,link)
            try:
                try:self._hold(base)
                except ValueError as error:
                    if 'object form' not in str(error):raise
                    observed.append('hardlink')
                else:raise AssertionError('Aliased fixture was not refused')
            finally:link.unlink()
            handle=self._open(source,0x20080);descriptor=C.c_void_p()
            try:
                error=self.a.GetSecurityInfo(handle,1,4,None,None,None,None,C.byref(descriptor))
                if error:raise C.WinError(error)
                if before!=self._acl_bytes(descriptor) or source.read_bytes()!=b'bounded fixture scope':
                    raise AssertionError('Refused fixture changed')
            finally:
                self.k.CloseHandle(handle)
                if descriptor:self.k.LocalFree(descriptor)
            return dict(passed=True,refused=observed,fixture_bytes_and_dacl_unchanged=True)
        finally:source.unlink()

    def _hold(self,value):
        if len(self.held)>=8 or value['fixture_id'] in self.held:raise ValueError('Fixture hold bound or duplicate')
        path=fixture_path(value['path'],self.temp)
        pins=[];handle=None;descriptor=C.c_void_p()
        try:
            # Walk local names without following reparse points. Each pinned
            # directory prevents replacement/reparse mutation before the next.
            current=self.temp
            parents=[current]
            for part in path.relative_to(self.temp).parts[:-1]:
                current=current/part;parents.append(current)
            for parent in parents:
                pinned=self._open(parent,0x81,share=1);pins.append(pinned)
                standard,tag=self._form(pinned)
                if not standard.directory or tag.attributes&0x400 or self._identity(pinned)[0]!=self.volume:
                    raise ValueError('Linked or foreign fixture parent')
            handle=self._open(path,0x60080)
            identity=self._identity(handle)
            if identity!=(value['volume'],value['file_id']) or identity[0]!=self.volume or not self._final(handle).is_relative_to(self.temp):
                raise ValueError('Fixture filesystem/handle identity mismatch')
            standard,tag=self._form(handle)
            if tag.attributes&0x400 or bool(standard.directory)!=value['directory'] or (not value['directory'] and standard.links!=1):
                raise ValueError('Fixture object form')
            error=self.a.GetSecurityInfo(handle,1,4,None,None,None,None,C.byref(descriptor))
            if error:raise C.WinError(error)
            entry=dict(handle=handle,pins=pins,identity=identity,directory=value['directory'],original=descriptor,path=str(path))
            expected=self._descriptor(entry,'original')
            try:
                actual=self._acl_bytes(descriptor);control=T.WORD();revision=T.DWORD()
                self._require(self.a.GetSecurityDescriptorControl(descriptor,C.byref(control),C.byref(revision)))
                if not control.value&0x1000 or actual!=self._acl_bytes(expected):raise ValueError('Not an original marked fixture DACL')
                entry['original_dacl_sha256']=hashlib.sha256(actual).hexdigest()
            finally:self.k.LocalFree(expected)
            self.held[value['fixture_id']]=entry;handle=None;descriptor=None;pins=[]
        finally:
            if descriptor:self.k.LocalFree(descriptor)
            if handle:self.k.CloseHandle(handle)
            for pinned in reversed(pins):self.k.CloseHandle(pinned)

    def _restore(self,fixture_id,*,abandoned=False):
        entry=self.held[fixture_id];self._set(entry,entry['original'])
        self.audit.append(dict(action='restore',fixture_id=fixture_id,identity=entry['identity'],
            original_dacl_sha256=entry['original_dacl_sha256'],abandoned=abandoned))
        self.k.CloseHandle(entry['handle']);self.k.LocalFree(entry['original']);del self.held[fixture_id]
        for pinned in reversed(entry['pins']):self.k.CloseHandle(pinned)

    def poll(self):
        pending=list(self.root.glob('request-*.ready'))
        if len(pending)>8:raise ValueError('Fixture request queue bound')
        for marker in pending:
            marker_info=marker.lstat()
            if (not stat.S_ISREG(marker_info.st_mode) or marker_info.st_nlink!=1
                    or getattr(marker_info,'st_file_attributes',0)&0x400 or marker_info.st_size!=0):
                raise ValueError('Fixture ready marker form')
            if not HEX.fullmatch(marker.name[len('request-'):-len('.ready')]):raise ValueError('Fixture marker identity')
            path=marker.with_suffix('.json')
            info=path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or getattr(info,'st_file_attributes',0)&0x400 or info.st_size>4096:
                raise ValueError('Fixture request file form')
            import msvcrt
            handle=self._open(path,0x80000080,share=1)
            try:
                class Standard(C.Structure):
                    _fields_=[('allocated',C.c_longlong),('size',C.c_longlong),('links',T.DWORD),('deleting',T.BYTE),('directory',T.BYTE)]
                class Tag(C.Structure):
                    _fields_=[('attributes',T.DWORD),('tag',T.DWORD)]
                standard=Standard();tag=Tag()
                self._require(self.k.GetFileInformationByHandleEx(handle,1,C.byref(standard),C.sizeof(standard)))
                self._require(self.k.GetFileInformationByHandleEx(handle,9,C.byref(tag),C.sizeof(tag)))
                if (standard.directory or standard.links!=1 or not 0<=standard.size<=4096
                        or tag.attributes&0x400 or self._identity(handle)[0]!=self.volume
                        or not self._final(handle).is_relative_to(self.root)):
                    raise ValueError('Fixture packet handle form')
                fd=msvcrt.open_osfhandle(handle,os.O_RDONLY|os.O_BINARY);handle=None
                with os.fdopen(fd,'rb') as stream:body=stream.read(4097)
                if len(body)>4096:raise ValueError('Fixture packet bound')
                value=json.loads(body)
            finally:
                if handle:self.k.CloseHandle(handle)
            action=validate_request(value,self.nonce)
            ident=value['request_id']
            if path.name!='request-'+ident+'.json' or ident in self.seen or len(self.seen)>=128:raise ValueError('Fixture replay/request bound')
            self.seen.add(ident)
            if action=='hold':self._hold(value)
            elif action=='restore':self._restore(value['fixture_id'])
            else:
                entry=self.held[value['fixture_id']]
                if (value['mode']=='metadata_only')!=entry['directory']:raise ValueError('Fixture mode/object mismatch')
                descriptor=self._descriptor(entry,value['mode'])
                try:self._set(entry,descriptor)
                finally:self.k.LocalFree(descriptor)
            if action!='restore':self.audit.append(dict(action=action,fixture_id=value['fixture_id'],mode=value.get('mode')))
            response=self.root/('response-'+ident+'.json')
            with response.open('x',encoding='utf-8',newline='\n') as stream:
                stream.write(json.dumps(dict(nonce=self.nonce,request_id=ident,ok=True)))
            path.unlink();marker.unlink()
            response.with_suffix('.ready').open('xb').close()

    def finish_job(self,*,quiescent):
        if not quiescent:raise ValueError('Fixture restore requires owned job retirement')
        for fixture_id in list(self.held):self._restore(fixture_id,abandoned=True)
        for path in self.root.iterdir():
            info=path.lstat()
            if not stat.S_ISREG(info.st_mode) or info.st_nlink!=1 or getattr(info,'st_file_attributes',0)&0x400 or info.st_size>4096:
                raise ValueError('Fixture endpoint cleanup form')
            path.unlink()
        return dict(requests=len(self.seen),all_held_fixtures_restored=True,audit=self.audit)

    def close(self,*,quiescent):
        if not quiescent:raise ValueError('Fixture close requires owned job retirement')
        try:self.finish_job(quiescent=True)
        finally:
            for entry in self.held.values():
                self.k.CloseHandle(entry['handle']);self.k.LocalFree(entry['original'])
                for pinned in reversed(entry['pins']):self.k.CloseHandle(pinned)
            self.held.clear()
            for handle in reversed(self.pins):self.k.CloseHandle(handle)
            self.pins=[]
        self.root.rmdir()
