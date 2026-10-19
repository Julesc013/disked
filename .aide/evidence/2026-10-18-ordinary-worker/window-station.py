"""One temporary, journaled UI-rights ACE for the owned guest test account."""
import base64
import ctypes as C
from ctypes import wintypes as T
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import struct
import subprocess
import sys

ROOT=Path('C:/ProgramData/DiskEd/qualification')
MASK=0x2012b  # read-control, enumeration, attributes, atoms, own desktop creation
P=C.c_void_p
spec=importlib.util.spec_from_file_location('station_crypto_support',Path(__file__).with_name('crypto-device.py'))
support=importlib.util.module_from_spec(spec);spec.loader.exec_module(support)
bind,require=support.bind,support.require

def aces(raw):
    if not 8<=len(raw)<=32768:raise ValueError('Station ACL size')
    revision,reserved,size,count,reserved2=struct.unpack_from('<BBHHH',raw)
    if revision not in (2,4) or reserved or reserved2 or size!=len(raw) or count>64:raise ValueError('Station ACL header')
    rows=[];at=8
    for _ in range(count):
        if at+4>size:raise ValueError('Station ACE header')
        kind,flags,length=struct.unpack_from('<BBH',raw,at)
        if kind not in (0,1) or flags&~31 or length<16 or length%4 or at+length>size:raise ValueError('Station ACE kind/flags/size')
        row=raw[at:at+length];sid=row[8:]
        if sid[0]!=1 or sid[1]>15 or len(sid)!=8+4*sid[1]:raise ValueError('Station SID size')
        rows.append(row);at+=length
    if any(raw[at:]):raise ValueError('Station ACL padding')
    return rows

def owned_ace(sid):
    if not 12<=len(sid)<=68 or sid[0]!=1 or len(sid)!=8+4*sid[1]:raise ValueError('Owned station SID')
    return struct.pack('<BBHI',0,0,8+len(sid),MASK)+sid

def add_subject(raw,sid):
    rows=aces(raw)
    if any(row[8:]==sid for row in rows):raise ValueError('Actor already has station ACE')
    return support.packed_acl(raw,rows+[owned_ace(sid)])

def remove_subject(raw,sid):
    rows=aces(raw);matches=[row for row in rows if row[8:]==sid]
    if matches and matches!=[owned_ace(sid)]:raise ValueError('Station actor ACE changed')
    return support.packed_acl(raw,[row for row in rows if row[8:]!=sid]),len(matches)

class Grant:
    read=support.Grant.read
    def __init__(self):
        if os.name!='nt' or Path(__file__).resolve().parent!=ROOT or C.sizeof(P)!=8 or not C.windll.shell32.IsUserAnAdmin():raise ValueError('Fixed guest coordinator required')
        self.k,self.a,self.u=[C.WinDLL(name,use_last_error=True) for name in ('kernel32','advapi32','user32')]
        computer=C.create_unicode_buffer(128);length=T.DWORD(128)
        require(bind(self.k,'GetComputerNameW',T.BOOL,T.LPWSTR,C.POINTER(T.DWORD))(computer,C.byref(length)))
        if computer.value.casefold()!='blackglass-hype':raise ValueError('Exact guest required')
        name=C.create_unicode_buffer(256);length=T.DWORD(256)
        require(bind(self.a,'GetUserNameW',T.BOOL,T.LPWSTR,C.POINTER(T.DWORD))(name,C.byref(length)))
        if name.value.casefold()!='agents':raise ValueError('Agents coordinator required')
        session=T.DWORD();require(bind(self.k,'ProcessIdToSessionId',T.BOOL,T.DWORD,C.POINTER(T.DWORD))(os.getpid(),C.byref(session)))
        self.station=bind(self.u,'GetProcessWindowStation',T.HANDLE)()
        name=C.create_unicode_buffer(1024);needed=T.DWORD()
        require(bind(self.u,'GetUserObjectInformationW',T.BOOL,T.HANDLE,C.c_int,P,T.DWORD,C.POINTER(T.DWORD))(self.station,2,name,C.sizeof(name),C.byref(needed)))
        if session.value!=3 or name.value!='WinSta0':raise ValueError('Exact existing session3 WinSta0 required')
        self.station=require(bind(self.u,'OpenWindowStationW',T.HANDLE,T.LPCWSTR,T.BOOL,T.DWORD)('WinSta0',False,0x60002))
        self.journal=ROOT/'scratch/ordinary-actor.json';self.data=self.read();self.sid_text=self.data['sid'];self.sid=P()
        self.report=dict(station='WinSta0',session_id=3,subject=self.sid_text,mask=MASK,retired=False)
        require(bind(self.a,'ConvertStringSidToSidW',T.BOOL,T.LPCWSTR,C.POINTER(P))(self.sid_text,C.byref(self.sid)))
        length=bind(self.a,'GetLengthSid',T.DWORD,P)(self.sid)
        self.sid_bytes=C.string_at(self.sid,length)
        self.owned=owned_ace(self.sid_bytes)
        assert MASK&0xd0254==0  # no delete/DACL/owner, clipboard, exit, screen or global-attribute writes
    def record(self,state):
        data=self.read()
        if data['sid']!=self.sid_text or data['nonce']!=self.data['nonce']:raise ValueError('Station journal identity changed')
        data['window_station']=state;raw=(json.dumps(data,indent=2)+'\n').encode()
        if len(raw)>65536:raise ValueError('Station journal bound')
        temporary=self.journal.with_name('ordinary-actor.'+data['nonce']+'.tmp')
        with temporary.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,self.journal)
    def snapshot(self):
        query=bind(self.u,'GetUserObjectSecurity',T.BOOL,T.HANDLE,C.POINTER(T.DWORD),P,T.DWORD,C.POINTER(T.DWORD))
        kind=T.DWORD(0x17);needed=T.DWORD();query(self.station,C.byref(kind),None,0,C.byref(needed))
        if not 0<needed.value<=32768:raise ValueError('Station descriptor bound')
        data=C.create_string_buffer(needed.value);require(query(self.station,C.byref(kind),data,needed,C.byref(needed)))
        present,defaulted=T.BOOL(),T.BOOL();acl=P()
        require(bind(self.a,'GetSecurityDescriptorDacl',T.BOOL,P,C.POINTER(T.BOOL),C.POINTER(P),C.POINTER(T.BOOL))(data,C.byref(present),C.byref(acl),C.byref(defaulted)))
        if not present.value or not acl:raise ValueError('Station DACL absent/null')
        length=C.c_ushort.from_address(acl.value+2).value
        if not C.addressof(data)<=acl.value or acl.value+length>C.addressof(data)+needed.value:raise ValueError('Station DACL range')
        raw=C.string_at(acl,length);aces(raw)
        text=T.LPWSTR();require(bind(self.a,'ConvertSecurityDescriptorToStringSecurityDescriptorW',T.BOOL,P,T.DWORD,T.DWORD,C.POINTER(T.LPWSTR),P)(data,1,0x17,C.byref(text),None))
        try:sddl=text.value
        finally:bind(self.k,'LocalFree',P,P)(C.cast(text,P))
        prefix,rest=sddl.split('D:',1);suffix=rest.split('S:',1)[1] if 'S:' in rest else ''
        return dict(raw=raw,sddl=sddl,unmodified_parts=prefix+'S:'+suffix)
    def update(self,before,raw):
        if self.snapshot()['sddl']!=before['sddl']:raise ValueError('Concurrent station security update; refuse')
        aces(raw);acl=C.create_string_buffer(raw);sd=C.create_string_buffer(40)
        require(bind(self.a,'InitializeSecurityDescriptor',T.BOOL,P,T.DWORD)(sd,1))
        require(bind(self.a,'SetSecurityDescriptorDacl',T.BOOL,P,T.BOOL,P,T.BOOL)(sd,True,acl,False))
        kind=T.DWORD(4);require(bind(self.u,'SetUserObjectSecurity',T.BOOL,T.HANDLE,C.POINTER(T.DWORD),P)(self.station,C.byref(kind),sd))
        after=self.snapshot()
        if aces(after['raw'])!=aces(raw) or after['unmodified_parts']!=before['unmodified_parts']:raise ValueError('Station delta readback differs')
        return after
    def apply(self):
        if self.read().get('window_station',{}).get('phase') not in (None,'retired'):raise ValueError('Prior station grant needs retirement')
        before=self.snapshot();candidate=add_subject(before['raw'],self.sid_bytes)
        state=dict(phase='prepared',station='WinSta0',session_id=3,subject=self.sid_text,mask=MASK,workers_started=False,
                   owned_ace=base64.b64encode(self.owned).decode(),before_sddl=before['sddl'])
        self.record(state);after=self.update(before,candidate)
        state['phase']='applied';self.record(state);self.report.update(before_sddl=before['sddl'],applied_sddl=after['sddl'])
    def started(self):
        state=self.read()['window_station'];assert state['phase']=='applied';state['workers_started']=True;self.record(state)
    def retire(self,*,quiescent):
        state=self.read().get('window_station')
        if not state:self.report['retired']=True;return
        if not quiescent:raise ValueError('Station workers not quiescent')
        if state.get('phase') not in ('prepared','applied','retired'):raise ValueError('Unknown station grant phase')
        if (state['station'],state['session_id'],state['subject'],state['mask'],state['owned_ace'])!=('WinSta0',3,self.sid_text,MASK,base64.b64encode(self.owned).decode()):raise ValueError('Station grant ownership changed')
        before=self.snapshot();candidate,count=remove_subject(before['raw'],self.sid_bytes)
        after=self.update(before,candidate) if count else before
        if any(row[8:]==self.sid_bytes for row in aces(after['raw'])):raise ValueError('Station actor ACE remains')
        state.update(phase='retired',after_sddl=after['sddl']);self.record(state)
        self.report.update(retired=True,removed_aces=count,retired_sddl=after['sddl'])
    def close(self):
        if self.sid:bind(self.k,'LocalFree',P,P)(self.sid);self.sid=None
        if self.station:require(bind(self.u,'CloseWindowStation',T.BOOL,T.HANDLE)(self.station));self.station=None

def coordinate(g,body):
    grant=None;body_started=False
    try:
        interrupted=subprocess.run([sys.executable,'-B',str(ROOT/'window-station.py'),'--apply-and-exit'],capture_output=True,timeout=15)
        if interrupted.returncode!=19:raise RuntimeError('Station setup fault did not reach boundary: '+interrupted.stderr[-4096:].decode(errors='replace'))
        grant=Grant();assert grant.read()['window_station']['workers_started'] is False
        grant.retire(quiescent=True);recovery=dict(grant.report);grant.close();grant=None
        grant=Grant();grant.apply();grant.started();body_started=True;body()
    except BaseException as error:
        if not body_started:
            if grant is None:grant=Grant()
            state=grant.read().get('window_station',{})
            if state.get('workers_started') is True:raise ValueError('Prior worker retirement uncertain') from error
            grant.retire(quiescent=True)
            proof=dict(status='fail',scope='Station setup failed before restricted worker launch',
                       all_owned_processes_retired=True,window_station=grant.report,error=repr(error))
            (ROOT/'proof-result.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
        raise
    finally:
        if grant:
            path=ROOT/'proof-result.json';proof=json.loads(path.read_bytes()) if path.exists() else {}
            state=grant.read().get('window_station',{})
            quiescent=bool(proof.get('all_owned_processes_retired')) or state.get('workers_started') is False
            try:
                grant.retire(quiescent=quiescent)
                if proof:
                    proof['window_station']=grant.report
                    if 'recovery' in locals():proof['window_station_recovery']=recovery
                    path.write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
            except BaseException as error:
                if proof:
                    proof.update(status='fail',window_station_cleanup_error=repr(error))
                    path.write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
                raise
            finally:grant.close()

if __name__=='__main__':
    if sys.argv[1:]!=['--apply-and-exit']:raise ValueError('Only owned setup fault supported')
    grant=Grant()
    try:grant.apply()
    except BaseException:
        grant.retire(quiescent=True);grant.close();raise
    os._exit(19)
