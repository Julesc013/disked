"""Private guest setup: one disposable subject, one crypto device, one ACE.

No filesystem ACL, owner, label, broad SID or policy-privilege change. This is
not a general device-access tool or a production dependency. ACL updates use
observed-current deltas; concurrent security-descriptor maintenance is excluded.
"""
import base64
import ctypes as C
from ctypes import wintypes as T
import hashlib
import json
import os
from pathlib import Path
import re
import struct
import sys

ROOT=Path('C:/ProgramData/DiskEd/qualification')
DEVICE='\\Device\\KsecDD'
MASK=0x100003
P=C.c_void_p

def aces(acl):
    if not 8<=len(acl)<=32768:raise ValueError('ACL size')
    revision,reserved,size,count,reserved2=struct.unpack_from('<BBHHH',acl)
    if revision not in (2,4) or reserved or reserved2 or size!=len(acl) or count>64:raise ValueError('ACL header')
    result=[];position=8
    for _ in range(count):
        if position+4>size:raise ValueError('Truncated ACE')
        kind,flags,length=struct.unpack_from('<BBH',acl,position)
        if kind not in (0,1) or flags or length<16 or length%4 or position+length>size:raise ValueError('Unsupported ACE')
        item=acl[position:position+length];sid=item[8:]
        if sid[0]!=1 or len(sid)!=8+4*sid[1]:raise ValueError('ACE SID length')
        result.append(item);position+=length
    if any(acl[position:]):raise ValueError('Nonzero ACL padding')
    return result

def packed_acl(original,items):
    raw=b''.join(items);size=8+len(raw)
    if len(items)>64 or size>32768:raise ValueError('ACL bound')
    return struct.pack('<BBHHH',original[0],0,size,len(items),0)+raw

def owned_ace(sid):
    if not 12<=len(sid)<=68 or sid[0]!=1 or len(sid)!=8+4*sid[1]:raise ValueError('Owned SID')
    return struct.pack('<BBHI',0,0,8+len(sid),MASK)+sid

def add_subject(acl,sid):
    items=aces(acl)
    if any(item[8:]==sid for item in items):raise ValueError('Subject already has an ACE')
    return packed_acl(acl,items+[owned_ace(sid)])

def remove_subject(acl,sid):
    items=aces(acl);matches=[item for item in items if item[8:]==sid]
    if matches and matches!=[owned_ace(sid)]:raise ValueError('Owned ACE changed or duplicated')
    return packed_acl(acl,[item for item in items if item[8:]!=sid]),len(matches)

class Unicode(C.Structure):_fields_=[('length',T.WORD),('maximum',T.WORD),('buffer',P)]
class Attributes(C.Structure):_fields_=[('length',T.DWORD),('root',T.HANDLE),('name',C.POINTER(Unicode)),('attributes',T.DWORD),('security',P),('qos',P)]
class IoStatus(C.Structure):_fields_=[('status_or_pointer',P),('information',C.c_size_t)]

def bind(dll,name,result,*arguments):
    value=getattr(dll,name);value.restype=result;value.argtypes=list(arguments);return value

def require(value):
    if not value:raise C.WinError(C.get_last_error())
    return value

class Grant:
    def __init__(self,*,recovery=False):
        if os.name!='nt' or Path(__file__).resolve().parent!=ROOT or C.sizeof(P)!=8:raise ValueError('Fixed x64 guest setup only')
        self.k=C.WinDLL('kernel32',use_last_error=True);self.a=C.WinDLL('advapi32',use_last_error=True);self.n=C.WinDLL('ntdll',use_last_error=True)
        bind(self.k,'CloseHandle',T.BOOL,T.HANDLE);bind(self.k,'LocalFree',P,P)
        bind(self.k,'GetComputerNameW',T.BOOL,T.LPWSTR,C.POINTER(T.DWORD))
        computer=C.create_unicode_buffer(128);computer_length=T.DWORD(len(computer));require(self.k.GetComputerNameW(computer,C.byref(computer_length)))
        if computer.value.casefold() not in ('blackglass-hype','blackglass-hyperv'):raise ValueError('Wrong guest computer')
        bind(self.a,'GetUserNameW',T.BOOL,T.LPWSTR,C.POINTER(T.DWORD))
        name=C.create_unicode_buffer(256);length=T.DWORD(len(name));require(self.a.GetUserNameW(name,C.byref(length)))
        if name.value.casefold()!='agents' or not C.windll.shell32.IsUserAnAdmin():raise ValueError('Guest Agents administrator required')
        self.journal=ROOT/'scratch/ordinary-actor.json';self.data=self.read()
        self.sid_text=self.data['sid'];self.device=T.HANDLE();self.sid=P()
        self.report=dict(device=DEVICE,subject=self.sid_text,access=hex(MASK),events=[],retired=False)
        if not recovery and self.data.get('crypto_device',{}).get('phase') not in (None,'retired'):raise ValueError('Prior crypto setup needs retirement')
        bind(self.n,'NtOpenFile',T.LONG,C.POINTER(T.HANDLE),T.DWORD,C.POINTER(Attributes),C.POINTER(IoStatus),T.DWORD,T.DWORD)
        bind(self.n,'NtQuerySecurityObject',T.LONG,T.HANDLE,T.DWORD,P,T.DWORD,C.POINTER(T.DWORD))
        bind(self.n,'NtSetSecurityObject',T.LONG,T.HANDLE,T.DWORD,P)
        bind(self.a,'ConvertStringSidToSidW',T.BOOL,T.LPCWSTR,C.POINTER(P));bind(self.a,'GetLengthSid',T.DWORD,P)
        bind(self.a,'GetSecurityDescriptorDacl',T.BOOL,P,C.POINTER(T.BOOL),C.POINTER(P),C.POINTER(T.BOOL))
        bind(self.a,'InitializeSecurityDescriptor',T.BOOL,P,T.DWORD);bind(self.a,'SetSecurityDescriptorDacl',T.BOOL,P,T.BOOL,P,T.BOOL)
        bind(self.a,'ConvertSecurityDescriptorToStringSecurityDescriptorW',T.BOOL,P,T.DWORD,T.DWORD,C.POINTER(T.LPWSTR),P)
        try:
            require(self.a.ConvertStringSidToSidW(self.sid_text,C.byref(self.sid)))
            self.sid_bytes=C.string_at(self.sid,self.a.GetLengthSid(self.sid));owned_ace(self.sid_bytes)
            text=C.create_unicode_buffer(DEVICE);value=Unicode((len(text)-1)*2,len(text)*2,C.cast(text,P))
            attrs=Attributes(C.sizeof(Attributes),None,C.pointer(value),0x40,None,None);iosb=IoStatus()
            status=self.n.NtOpenFile(C.byref(self.device),0x60000,C.byref(attrs),C.byref(iosb),7,0)
            self.report['open_status']=hex(status&0xffffffff)
            if status!=0:raise RuntimeError('Crypto READ_CONTROL/WRITE_DAC open: '+hex(status&0xffffffff))
            self.snapshot()
        except BaseException:self.close();raise

    def read(self):
        for path in (ROOT,ROOT/'scratch',ROOT/'scratch/ordinary-actor.json'):
            st=path.lstat()
            if path.is_symlink() or st.st_file_attributes&0x400:raise ValueError('Linked setup state')
        if self.journal.stat().st_size>65536:raise ValueError('Journal bound')
        data=json.loads(self.journal.read_bytes());nonce=data['nonce']
        if not re.fullmatch('[0-9a-f]{32}',nonce) or data['name']!='DiskEdTest-'+nonce[:8] or data['description']!='DiskEd test '+nonce or data['phase']!='created':raise ValueError('Actor ownership')
        if not re.fullmatch(r'S-1-5-21-385394198-2603589104-1765785984-[1-9][0-9]*',data['sid']):raise ValueError('Unexpected actor SID')
        owner=json.loads((ROOT/'scratch/owner.json').read_bytes())
        if owner['nonce']!=nonce:raise ValueError('Campaign ownership')
        return data

    def record(self,value):
        current=self.read()
        if current['sid']!=self.sid_text or current['nonce']!=self.data['nonce']:raise ValueError('Journal owner changed')
        current['crypto_device']=value
        raw=(json.dumps(current,indent=2)+'\n').encode('utf-8')
        if len(raw)>65536:raise ValueError('Journal bound')
        temporary=self.journal.with_name('ordinary-actor.'+current['nonce']+'.tmp')
        with temporary.open('xb') as stream:stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,self.journal)

    def snapshot(self):
        size=T.DWORD();self.n.NtQuerySecurityObject(self.device,7,None,0,C.byref(size))
        if not 0<size.value<=32768:raise ValueError('Security descriptor bound')
        buffer=C.create_string_buffer(size.value);status=self.n.NtQuerySecurityObject(self.device,7,buffer,size,C.byref(size))
        if status!=0:raise RuntimeError('Crypto security query: '+hex(status&0xffffffff))
        present,defaulted=T.BOOL(),T.BOOL();acl=P()
        require(self.a.GetSecurityDescriptorDacl(buffer,C.byref(present),C.byref(acl),C.byref(defaulted)))
        if not present.value or not acl:raise ValueError('Null/absent crypto DACL')
        length=C.c_ushort.from_address(acl.value+2).value
        if not C.addressof(buffer)<=acl.value or acl.value+length>C.addressof(buffer)+size.value:raise ValueError('DACL range')
        raw=C.string_at(acl,length);aces(raw)
        output=T.LPWSTR();require(self.a.ConvertSecurityDescriptorToStringSecurityDescriptorW(buffer,1,7,C.byref(output),None))
        try:text=output.value
        finally:self.k.LocalFree(C.cast(output,P))
        return dict(acl=raw,sddl=text,sha256=hashlib.sha256(raw).hexdigest())

    def update(self,before,raw):
        if self.snapshot()['sddl']!=before['sddl']:raise ValueError('Crypto security changed before update')
        aces(raw);acl=C.create_string_buffer(raw);descriptor=C.create_string_buffer(40)
        require(self.a.InitializeSecurityDescriptor(descriptor,1));require(self.a.SetSecurityDescriptorDacl(descriptor,True,acl,False))
        status=self.n.NtSetSecurityObject(self.device,4,descriptor)
        self.report['events'].append(dict(action='set_dacl',status=hex(status&0xffffffff)))
        if status!=0:raise RuntimeError('Crypto DACL update unsupported/refused: '+hex(status&0xffffffff))
        after=self.snapshot()
        if aces(after['acl'])!=aces(raw) or after['sddl'].split('D:')[0]!=before['sddl'].split('D:')[0]:raise ValueError('Crypto DACL/owner/group readback mismatch')
        return after

    def apply(self):
        before=self.snapshot();candidate=add_subject(before['acl'],self.sid_bytes)
        expected='(A;;0x1201bf;;;WD)(A;;FA;;;SY)(A;;FA;;;BA)(A;;0x1200a9;;;RC)(A;;0x1201bf;;;AC)(A;;0x1201bf;;;S-1-15-2-2)'
        if before['sddl'].split('D:',1)[1]!=expected:raise ValueError('Unexpected baseline crypto DACL')
        self.record(dict(phase='prepared',device=DEVICE,subject=self.sid_text,mask=MASK,workers_started=False,before_sddl=before['sddl'],before_sha256=before['sha256'],owned_ace_base64=base64.b64encode(owned_ace(self.sid_bytes)).decode('ascii')))
        after=self.update(before,candidate)
        state=self.read()['crypto_device'];state['phase']='applied';self.record(state)
        self.report['events'].append(dict(action='applied',before_sddl=before['sddl'],after_sddl=after['sddl']))

    def started(self):
        state=self.read()['crypto_device']
        if state['phase']!='applied':raise ValueError('Crypto exception not applied')
        state['workers_started']=True;self.record(state)

    def retire(self,*,quiescent):
        state=self.read().get('crypto_device')
        if state is None:self.report['retired']=True;return
        if not quiescent:raise ValueError('Owned workers must retire before device exception')
        if state['phase'] not in ('prepared','applied','retired'):raise ValueError('Unknown crypto setup phase')
        if state['device']!=DEVICE or state['subject']!=self.sid_text or state['mask']!=MASK or state['owned_ace_base64']!=base64.b64encode(owned_ace(self.sid_bytes)).decode('ascii'):raise ValueError('Crypto retirement ownership')
        before=self.snapshot();raw,count=remove_subject(before['acl'],self.sid_bytes)
        after=self.update(before,raw) if count else before
        if any(item[8:]==self.sid_bytes for item in aces(after['acl'])):raise ValueError('Actor crypto ACE remains')
        state['phase']='retired';state['after_sddl']=after['sddl'];self.record(state)
        self.report.update(retired=True,removed_owned_aces=count,retired_sddl=after['sddl'])

    def close(self):
        if getattr(self,'device',None):require(self.k.CloseHandle(self.device));self.device=None
        if getattr(self,'sid',None):self.k.LocalFree(self.sid);self.sid=None

def coordinate(g):
    """Finite setup/recovery/startup/revocation probe; no full-worker admission."""
    import subprocess
    import time
    import traceback
    result=dict(status='running',scope='Scoped guest crypto-device exception startup probe; not full worker qualification',full_worker_qualified=False,all_owned_processes_retired=False,crypto_device_retired=False)
    grant,instance,job,child=None,None,None,None;quiescent=True
    def stop_job():
        nonlocal job,child,quiescent
        if job:
            class Accounting(C.Structure):_fields_=[('times',C.c_longlong*4),('faults',T.DWORD),('total',T.DWORD),('active',T.DWORD),('terminated',T.DWORD)]
            query=bind(job.api,'QueryInformationJobObject',T.BOOL,T.HANDLE,C.c_int,P,T.DWORD,P)
            require(job.api.TerminateJobObject(job.handle,78));until=time.monotonic()+10
            while True:
                observed=Accounting();require(query(job.handle,1,C.byref(observed),C.sizeof(observed),None))
                if observed.active==0:break
                if time.monotonic()>until:raise TimeoutError('Crypto probe job did not retire')
                time.sleep(.05)
            result.setdefault('job_retirements',[]).append(dict(active_processes=observed.active))
            job.close();job=None
        if child:child.wait(timeout=10);child.close();child=None
        quiescent=True
    try:
        data=g.actor();private={k:os.environ.pop(k) for k in list(os.environ) if k.startswith('DISKED_TEST_ACTOR_')}
        state=json.loads((ROOT/'scratch/state.json').read_bytes());assert state['size_mib']==32
        # A real helper exit leaves only the recorded subject ACE. No restricted
        # worker exists at this prelaunch fault point; wait for that exact helper.
        interrupted=subprocess.run([sys.executable,'-B',str(ROOT/'crypto-device.py'),'--apply-and-exit'],capture_output=True,timeout=15,creationflags=0x08000000)
        assert len(interrupted.stdout)+len(interrupted.stderr)<=65536
        result['interruption']=dict(exit_code=interrupted.returncode,output=interrupted.stderr.decode(errors='replace'))
        if interrupted.returncode!=19:raise RuntimeError('Crypto setup interruption probe did not reach its declared boundary')
        grant=Grant(recovery=True)
        assert grant.read()['crypto_device']['workers_started'] is False
        assert any(item==owned_ace(grant.sid_bytes) for item in aces(grant.snapshot()['acl']))
        grant.retire(quiescent=True);result['interruption_recovery']=json.loads(json.dumps(grant.report));grant.close();grant=None
        grant=Grant();grant.apply()
        selected=g.fresh(g.W.plain_directory(state['work'])/'crypto');instance=g.worker(selected,private,namespace_compat=True)
        request=g.plan(selected,data);payload=json.loads(request.read_bytes());payload['variant']='basic-stdio';request.write_text(json.dumps(payload))
        job=g.S.WindowsJob();grant.started();quiescent=False
        child=instance.launch([sys.executable,'-B',str(ROOT/'target.py'),str(request),'launch'],os.environ,job,variant='basic-stdio')
        code=child.wait(timeout=15);result['identity_exit_code']=code;result['identity_launch']=instance.last_launch
        if (selected/'launch-basic-stdio.json').exists():result['identity']=json.loads((selected/'launch-basic-stdio.json').read_bytes())
        assert code==0
        observed=result['identity'];assert observed['user_sid']==data['sid'] and observed['restricted'] and not any(observed[key] for key in ('elevated','administrator','appcontainer'))
        assert set(observed['restricting_sids'])=={data['sid'],'S-1-5-12'} and len(observed['restricting_sids'])==2 and observed['integrity_sid']=='S-1-16-8192'
        assert observed['stdio'][0]['kind']==2 and all(row['kind']==1 and row['file_identity']==instance.last_launch['stdout_identity'] for row in observed['stdio'][1:])
        child.close();child=None
        child=instance.launch([sys.executable,'-B',str(ROOT/'loader-observer.py'),'loader-compatible.log'],os.environ,job,variant='basic-stdio')
        code=child.wait(timeout=15);result['imports_exit_code']=code
        if (selected/'loader-compatible.log').exists():result['imports']=(selected/'loader-compatible.log').read_text(encoding='utf-8')
        assert code==0 and result['imports'].endswith('complete\n')
        stop_job();grant.retire(quiescent=quiescent);result['applied_and_retired']=json.loads(json.dumps(grant.report))
        # Independent new process, after revocation and retirement of every old
        # worker. It receives only its declared stdio handles, not a crypto one.
        assert not (selected/'loader-restricted.log').exists()
        job=g.S.WindowsJob();quiescent=False
        child=instance.launch([sys.executable,'-B',str(ROOT/'loader-observer.py'),'loader-restricted.log'],os.environ,job,variant='basic-stdio')
        code=child.wait(timeout=15);result['after_revocation']=dict(exit_code=code,breadcrumb_exists=(selected/'loader-restricted.log').exists())
        assert code==0xc0000142 and not result['after_revocation']['breadcrumb_exists']
        stop_job();result['status']='pass'
    except BaseException:
        if instance:result['last_launch']=getattr(instance,'last_launch',None)
        result.update(status='fail',error=traceback.format_exc()[-8192:]);raise
    finally:
        try:
            stop_job()
            if instance:instance.close()
            if grant is None and json.loads((ROOT/'scratch/ordinary-actor.json').read_bytes()).get('crypto_device'):
                grant=Grant(recovery=True)
            if grant:
                grant.retire(quiescent=quiescent)
                result['crypto_cleanup']=grant.report
                result['crypto_device_retired']=grant.read()['crypto_device']['phase']=='retired'
                grant.close()
            else:result['crypto_device_retired']=True  # No setup journal/permission was introduced.
            result['all_owned_processes_retired']=True
        except BaseException:
            result.update(status='fail',cleanup_error=traceback.format_exc()[-8192:]);raise
        finally:(ROOT/'proof-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':
    if sys.argv[1:]!=['--apply-and-exit']:raise ValueError('Fixed prelaunch interruption probe only')
    instance=Grant();instance.apply()
    # Intentional abrupt exit before any restricted process is created. The
    # parent must recover the journal and remove only this exact subject ACE.
    os._exit(19)
