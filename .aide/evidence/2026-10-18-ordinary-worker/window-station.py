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
BASE_MASK=0x2012b  # read-control, enumeration, attributes, atoms, own desktop creation
# Run70 isolates EXITWINDOWS as necessary for User32 initialization on WinSta0.
# Opening this right is tested; invoking exit/logoff is outside the test grant.
MASK=BASE_MASK|0x40
DIAGNOSTIC_MASKS=(BASE_MASK,BASE_MASK|0x200,BASE_MASK|4,BASE_MASK|0x10,MASK,0x2037f)
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

def owned_ace(sid,mask=MASK):
    if not 12<=len(sid)<=68 or sid[0]!=1 or len(sid)!=8+4*sid[1]:raise ValueError('Owned station SID')
    if mask not in DIAGNOSTIC_MASKS:raise ValueError('Undeclared station diagnostic mask')
    return struct.pack('<BBHI',0,0,8+len(sid),mask)+sid

def add_subject(raw,sid,mask=MASK):
    rows=aces(raw)
    if any(row[8:]==sid for row in rows):raise ValueError('Actor already has station ACE')
    return support.packed_acl(raw,rows+[owned_ace(sid,mask)])

def remove_subject(raw,sid,mask=MASK):
    rows=aces(raw);matches=[row for row in rows if row[8:]==sid]
    if matches and matches!=[owned_ace(sid,mask)]:raise ValueError('Station actor ACE changed')
    return support.packed_acl(raw,[row for row in rows if row[8:]!=sid]),len(matches)

class Grant:
    read=support.Grant.read
    def __init__(self,mask=MASK):
        if os.name!='nt' or Path(__file__).resolve().parent!=ROOT or C.sizeof(P)!=8 or not C.windll.shell32.IsUserAnAdmin():raise ValueError('Fixed guest coordinator required')
        if mask!=MASK and not json.loads((ROOT/'expected.json').read_bytes()).get('station_bootstrap_matrix_only'):
            raise ValueError('Additional UI rights limited to trusted startup diagnostic')
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
        self.mask=mask
        self.report=dict(station='WinSta0',session_id=3,subject=self.sid_text,mask=mask,retired=False)
        require(bind(self.a,'ConvertStringSidToSidW',T.BOOL,T.LPCWSTR,C.POINTER(P))(self.sid_text,C.byref(self.sid)))
        length=bind(self.a,'GetLengthSid',T.DWORD,P)(self.sid)
        self.sid_bytes=C.string_at(self.sid,length)
        self.owned=owned_ace(self.sid_bytes,mask)
        assert mask&0xd0000==0  # never delete, change DACL or take ownership
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
        before=self.snapshot();candidate=add_subject(before['raw'],self.sid_bytes,self.mask)
        state=dict(phase='prepared',station='WinSta0',session_id=3,subject=self.sid_text,mask=self.mask,workers_started=False,
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
        if (state['station'],state['session_id'],state['subject'],state['mask'],state['owned_ace'])!=('WinSta0',3,self.sid_text,self.mask,base64.b64encode(self.owned).decode()):raise ValueError('Station grant ownership changed')
        before=self.snapshot();candidate,count=remove_subject(before['raw'],self.sid_bytes,self.mask)
        after=self.update(before,candidate) if count else before
        if any(row[8:]==self.sid_bytes for row in aces(after['raw'])):raise ValueError('Station actor ACE remains')
        state.update(phase='retired',after_sddl=after['sddl']);self.record(state)
        self.report.update(retired=True,removed_aces=count,retired_sddl=after['sddl'])
    def close(self):
        if self.sid:bind(self.k,'LocalFree',P,P)(self.sid);self.sid=None
        if self.station:require(bind(self.u,'CloseWindowStation',T.BOOL,T.HANDLE)(self.station));self.station=None

def bootstrap_matrix(g):
    data=g.actor();private={key:value for key,value in os.environ.items() if key.startswith('DISKED_TEST_ACTOR_')}
    work=Path(json.loads((ROOT/'scratch/state.json').read_bytes())['work']);rows=[]
    for mask in DIAGNOSTIC_MASKS:
        grant=Grant(mask);instance=job=child=None;row=dict(mask=mask)
        try:
            grant.apply();grant.started()
            folder=g.fresh(work/('bootstrap-'+hex(mask)[2:]));instance=g.worker(folder,private,namespace_compat=True)
            request=folder/'startup-request.json';variant='mask-'+hex(mask)[2:]
            request.write_text(json.dumps(dict(variant=variant,user_sid=data['sid'],desktop=instance.desktop_name)))
            job=g.S.WindowsJob()
            child=instance.launch([sys.executable,'-B',str(ROOT/'target.py'),str(request),'startup'],os.environ,job,diagnostic_original=True)
            row.update(exit_code=child.wait(timeout=15),parameters=instance.last_launch,
                       log=instance.log_path.read_bytes()[-8192:].decode(errors='replace'))
            observation=folder/('startup-'+variant+'.json')
            row['observation']=json.loads(observation.read_bytes()) if observation.exists() else None
        finally:
            if job:row['job_retirement']=g.retire_job(job)
            if child:child.wait(timeout=10);child.close()
            if instance:instance.close()
            grant.retire(quiescent=True);row['station_retirement']=grant.report;grant.close()
            rows.append(row)
    return rows

def coordinate(g,body):
    instances={};body_started=False;recoveries={};namespace=None
    try:
        interrupted=subprocess.run([sys.executable,'-B',str(ROOT/'window-station.py'),'--apply-and-exit'],capture_output=True,timeout=15)
        if interrupted.returncode!=19:raise RuntimeError('Station setup fault did not reach boundary: '+interrupted.stderr[-4096:].decode(errors='replace'))
        station=Grant();instances['window_station']=station
        assert station.read()['window_station']['workers_started'] is False
        station.retire(quiescent=True);recoveries['window_station_recovery']=dict(station.report)
        station.close();instances.pop('window_station')
        if json.loads((ROOT/'expected.json').read_bytes()).get('station_bootstrap_matrix_only'):
            rows=bootstrap_matrix(g)
            proof=dict(status='pass',scope='Six fixed trusted standard-user bootstrap observations only;no restricted worker or product qualification',
                       all_owned_processes_retired=True,station_bootstrap_matrix=rows,**recoveries)
            assert len(rows)==len(DIAGNOSTIC_MASKS) and all(row['station_retirement']['retired'] for row in rows)
            (ROOT/'proof-result.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
            return
        namespace=g.load('interactive_object_namespace',ROOT/'object-namespace.py')
        interrupted=subprocess.run([sys.executable,'-B',str(ROOT/'object-namespace.py'),'--apply-and-exit'],capture_output=True,timeout=15,creationflags=0x08000000)
        if interrupted.returncode!=19:raise RuntimeError('Namespace setup fault did not reach boundary: '+interrupted.stderr[-4096:].decode(errors='replace'))
        entry=namespace.Grant(recovery=True);instances['object_namespace']=entry
        assert entry.read()['crypto_device']['workers_started'] is False
        entry.retire(quiescent=True);recoveries['object_namespace_recovery']=dict(entry.report)
        entry.close();instances.pop('object_namespace')
        station=Grant();instances['window_station']=station;station.apply()
        entry=namespace.Grant();instances['object_namespace']=entry;entry.apply()
        station.started();entry.started();body_started=True;body()
    except BaseException as error:
        if not body_started:
            journal=json.loads((ROOT/'scratch/ordinary-actor.json').read_bytes())
            quiescent=all(journal.get(key,{}).get('workers_started') is not True for key in ('window_station','object_namespace'))
            proof=dict(status='fail',scope='Interactive setup failed before restricted worker launch',
                       all_owned_processes_retired=quiescent,error=repr(error),**recoveries)
            (ROOT/'proof-result.json').write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
        raise
    finally:
        errors=[];path=ROOT/'proof-result.json';proof=json.loads(path.read_bytes()) if path.exists() else {}
        for key in ('object_namespace','window_station'):
            instance=instances.get(key)
            try:
                journal=json.loads((ROOT/'scratch/ordinary-actor.json').read_bytes());state=journal.get(key,{})
                if not instance and state:
                    if key=='object_namespace':
                        if namespace is None:namespace=g.load('interactive_object_namespace_recovery',ROOT/'object-namespace.py')
                        instance=namespace.Grant(recovery=True)
                    else:instance=Grant(state.get('mask',MASK))
                if instance:
                    quiescent=bool(proof.get('all_owned_processes_retired')) or state.get('workers_started') is False
                    instance.retire(quiescent=quiescent);proof[key]=instance.report
                    if key=='object_namespace':proof['object_namespace_retired']=instance.report['retired']
            except BaseException as error:
                errors.append(repr(error));proof.update(status='fail');proof[key+'_cleanup_error']=repr(error)
            finally:
                if instance:
                    try:instance.close()
                    except BaseException as error:errors.append(repr(error));proof.update(status='fail');proof[key+'_close_error']=repr(error)
        if proof:
            proof.update(recoveries);path.write_text(json.dumps(proof,indent=2)+'\n',encoding='utf-8',newline='\n')
        if errors:raise RuntimeError('Interactive grant retirement needs review: '+';'.join(errors))

if __name__=='__main__':
    if sys.argv[1:]!=['--apply-and-exit']:raise ValueError('Only owned setup fault supported')
    grant=Grant()
    try:grant.apply()
    except BaseException:
        grant.retire(quiescent=True);grant.close();raise
    os._exit(19)
