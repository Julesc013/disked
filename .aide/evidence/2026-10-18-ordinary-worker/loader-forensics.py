"""Finite Win10/x64 loader tracing of owned children, never a worker admission."""
import base64
import ctypes as C
from ctypes import wintypes as T
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback
import winreg

ROOT=Path('C:/ProgramData/DiskEd/qualification')
P=C.c_void_p

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

class ExceptionRecord(C.Structure):
    _fields_=[('code',T.DWORD),('flags',T.DWORD),('previous',P),('address',P),('count',T.DWORD),('parameters',C.c_size_t*15)]
class ExceptionInfo(C.Structure):
    _fields_=[('record',ExceptionRecord),('first',T.DWORD)]
class CreateInfo(C.Structure):
    _fields_=[('file',T.HANDLE),('process',T.HANDLE),('thread',T.HANDLE),('base',P),('offset',T.DWORD),('size',T.DWORD),('tls',P),('entry',P),('name',P),('unicode',T.WORD)]
class LoadInfo(C.Structure):
    _fields_=[('file',T.HANDLE),('base',P),('offset',T.DWORD),('size',T.DWORD),('name',P),('unicode',T.WORD)]
class StringInfo(C.Structure):
    _fields_=[('address',P),('unicode',T.WORD),('length',T.WORD)]
class EventData(C.Union):
    _fields_=[('exception',ExceptionInfo),('created',CreateInfo),('loaded',LoadInfo),('string',StringInfo),('exit_code',T.DWORD)]
class Event(C.Structure):
    _fields_=[('code',T.DWORD),('pid',T.DWORD),('tid',T.DWORD),('data',EventData)]

def namespace_actor(plan):
    """Open/query existing object directories; never create or change one."""
    t=load('namespace_identity',ROOT/'target.py');b=load('namespace_base',ROOT/'tools/windows-worker.py')
    k,a=t.k,t.a;bind,require=t.bind,t.require;n=C.WinDLL('ntdll',use_last_error=True)
    observed=t.identity();assert observed['user_sid']==plan['user_sid'] and not any(observed[x] for x in ('restricted','administrator','elevated','appcontainer'))
    assert Path.cwd()==Path(plan['work']) and C.sizeof(P)==8
    class Unicode(C.Structure):_fields_=[('length',T.WORD),('maximum',T.WORD),('buffer',P)]
    class Attributes(C.Structure):_fields_=[('length',T.DWORD),('root',T.HANDLE),('name',C.POINTER(Unicode)),('attributes',T.DWORD),('security',P),('qos',P)]
    assert C.sizeof(Attributes)==48
    bind(k,'GetCurrentThread',T.HANDLE);bind(k,'ProcessIdToSessionId',T.BOOL,T.DWORD,C.POINTER(T.DWORD))
    bind(a,'OpenThreadToken',T.BOOL,T.HANDLE,T.DWORD,T.BOOL,C.POINTER(T.HANDLE))
    bind(a,'ImpersonateLoggedOnUser',T.BOOL,T.HANDLE);bind(a,'RevertToSelf',T.BOOL)
    bind(a,'ConvertStringSidToSidW',T.BOOL,T.LPCWSTR,C.POINTER(P))
    bind(a,'CreateRestrictedToken',T.BOOL,T.HANDLE,T.DWORD,T.DWORD,P,T.DWORD,P,T.DWORD,P,C.POINTER(T.HANDLE))
    bind(n,'NtOpenDirectoryObject',T.LONG,C.POINTER(T.HANDLE),T.DWORD,C.POINTER(Attributes))
    bind(n,'NtQuerySecurityObject',T.LONG,T.HANDLE,T.DWORD,P,T.DWORD,C.POINTER(T.DWORD))
    session=T.DWORD();require(k.ProcessIdToSessionId(os.getpid(),C.byref(session)))
    prefix='\\Sessions\\'+str(session.value)
    names=['\\BaseNamedObjects','\\BaseNamedObjects\\Restricted',prefix+'\\BaseNamedObjects',prefix+'\\BaseNamedObjects\\Restricted',prefix+'\\Windows',prefix+'\\Windows\\WindowStations']
    original,sid=T.HANDLE(),P();report=dict(status='running',bootstrap=observed,session=session.value,observations=[])
    require(a.OpenProcessToken(k.GetCurrentProcess(),0x8b,C.byref(original)))
    try:
        require(a.ConvertStringSidToSidW(plan['user_sid'],C.byref(sid)))
        for name,restricted in (('baseline',False),('restricted',True)):
            token=T.HANDLE();entry=b.SidAttributes(sid,0)
            require(a.CreateRestrictedToken(original,9 if restricted else 1,0,None,0,None,int(restricted),C.byref(entry) if restricted else None,C.byref(token)))
            try:
                require(a.ImpersonateLoggedOnUser(token))
                try:
                    actual=T.HANDLE();require(a.OpenThreadToken(k.GetCurrentThread(),8,True,C.byref(actual)))
                    try:assert bool(a.IsTokenRestricted(actual))==restricted
                    finally:k.CloseHandle(actual)
                    for path in names:
                        text=C.create_unicode_buffer(path);value=Unicode(len(path)*2,(len(path)+1)*2,C.cast(text,P))
                        attrs=Attributes(C.sizeof(Attributes),None,C.pointer(value),0x40,None,None)
                        for mask in (3,7,15,0x20003,0x2000f):
                            handle=T.HANDLE();status=n.NtOpenDirectoryObject(C.byref(handle),mask,C.byref(attrs))
                            row=dict(token=name,path=path,access=hex(mask),status=hex(status&0xffffffff))
                            try:
                                if status==0 and mask&0x20000:
                                    length=T.DWORD();n.NtQuerySecurityObject(handle,4,None,0,C.byref(length));assert 0<length.value<=32768
                                    sd=C.create_string_buffer(length.value);security_status=n.NtQuerySecurityObject(handle,4,sd,length,C.byref(length));row['security_status']=hex(security_status&0xffffffff)
                                    if security_status==0:
                                        output=T.LPWSTR();require(a.ConvertSecurityDescriptorToStringSecurityDescriptorW(sd,1,4,C.byref(output),None))
                                        try:row['dacl']=output.value
                                        finally:k.LocalFree(C.cast(output,P))
                            finally:
                                if handle:k.CloseHandle(handle)
                            report['observations'].append(row)
                finally:require(a.RevertToSelf())
            finally:k.CloseHandle(token)
        assert len(report['observations'])==60
        report['status']='pass'
    finally:
        if sid:k.LocalFree(sid)
        if original:k.CloseHandle(original)
        Path('namespace-report.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')

def coordinate_namespace(g):
    result=dict(status='running',scope='Read-only existing object-namespace access diagnostic; no profile admission',full_profile_qualified=False,all_owned_processes_retired=False)
    instance,job,child=None,None,None
    try:
        data=g.actor();private={k:os.environ.pop(k) for k in list(os.environ) if k.startswith('DISKED_TEST_ACTOR_')}
        state=json.loads((ROOT/'scratch/state.json').read_bytes());assert state['size_mib']==32
        selected=g.fresh(g.W.plain_directory(state['work'])/'namespace');instance=g.worker(selected,private)
        request=selected/'debug-plan.json';request.write_text(json.dumps(dict(work=str(selected),user_sid=data['sid'])))
        job=g.S.WindowsJob();child=instance.launch([sys.executable,'-B',str(ROOT/'loader-forensics.py'),'--namespace',str(request)],os.environ,job,diagnostic_original=True)
        code=child.wait(timeout=15);result['actor_exit_code']=code
        if (selected/'namespace-report.json').exists():result['namespace']=json.loads((selected/'namespace-report.json').read_bytes())
        result['actor_output']=instance.log_path.read_text(errors='replace')[:65536]
        assert code==0 and result['namespace']['status']=='pass'
        result['status']='pass'
    except BaseException:
        result.update(status='fail',error=traceback.format_exc()[-8192:]);raise
    finally:
        if job:job.close()
        if child:child.wait(timeout=10);child.close()
        if instance:instance.close()
        result['all_owned_processes_retired']=True
        (ROOT/'proof-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')

def actor(plan):
    b=load('debug_base',ROOT/'tools/windows-worker.py')
    target=load('debug_identity',ROOT/'target.py')
    k,a=target.k,target.a;bind,require=target.bind,target.require
    identity=target.identity()
    assert identity['user_sid']==plan['user_sid'] and not any(identity[x] for x in ('restricted','administrator','elevated','appcontainer'))
    assert C.sizeof(P)==8 and C.sizeof(Event)==176 and Event.data.offset==16
    assert Path.cwd()==Path(plan['work']) and Path(plan['image']).parent==Path(sys.executable).parent
    assert hashlib.sha256(Path(plan['image']).read_bytes()).hexdigest()==plan['image_sha256']
    bind(k,'IsProcessInJob',T.BOOL,T.HANDLE,T.HANDLE,C.POINTER(T.BOOL))
    inside=T.BOOL();require(k.IsProcessInJob(k.GetCurrentProcess(),None,C.byref(inside)));assert inside.value
    bind(k,'WaitForDebugEventEx',T.BOOL,C.POINTER(Event),T.DWORD)
    bind(k,'ContinueDebugEvent',T.BOOL,T.DWORD,T.DWORD,T.DWORD)
    bind(k,'ReadProcessMemory',T.BOOL,T.HANDLE,P,P,C.c_size_t,C.POINTER(C.c_size_t))
    bind(k,'GetFinalPathNameByHandleW',T.DWORD,T.HANDLE,T.LPWSTR,T.DWORD,T.DWORD)
    bind(k,'ResumeThread',T.DWORD,T.HANDLE)
    bind(k,'WaitForSingleObject',T.DWORD,T.HANDLE,T.DWORD)
    bind(k,'TerminateProcess',T.BOOL,T.HANDLE,T.UINT)
    bind(k,'InitializeProcThreadAttributeList',T.BOOL,P,T.DWORD,T.DWORD,C.POINTER(C.c_size_t))
    bind(k,'UpdateProcThreadAttribute',T.BOOL,P,T.DWORD,C.c_size_t,P,C.c_size_t,P,P)
    bind(k,'DeleteProcThreadAttributeList',None,P)
    bind(k,'CreateFileW',T.HANDLE,T.LPCWSTR,T.DWORD,T.DWORD,C.POINTER(b.SecurityAttributes),T.DWORD,T.DWORD,T.HANDLE)
    bind(a,'ConvertStringSidToSidW',T.BOOL,T.LPCWSTR,C.POINTER(P))
    bind(a,'CreateRestrictedToken',T.BOOL,T.HANDLE,T.DWORD,T.DWORD,P,T.DWORD,P,T.DWORD,P,C.POINTER(T.HANDLE))
    bind(a,'CreateProcessAsUserW',T.BOOL,T.HANDLE,T.LPCWSTR,T.LPWSTR,P,P,T.BOOL,T.DWORD,P,T.LPCWSTR,P,C.POINTER(b.ProcessInfo))
    bind(a,'IsTokenRestricted',T.BOOL,T.HANDLE)
    result=dict(status='running',bootstrap_identity=identity,variants=[])
    original,sid,compatibility=T.HANDLE(),P(),P()
    require(a.OpenProcessToken(k.GetCurrentProcess(),0x8b,C.byref(original)))
    try:
        require(a.ConvertStringSidToSidW(plan['user_sid'],C.byref(sid)))
        require(a.ConvertStringSidToSidW('S-1-5-12',C.byref(compatibility)))
        for name,restricted_case in (('baseline',False),('restricted_compat',True)):
            token,process=T.HANDLE(),b.ProcessInfo();handles=[];attributes=None;initialized=False;exited=False
            row=dict(name=name,phase='derive_token',modules=[],exceptions=[],events=0)
            trace_path=Path(name+'-loader.txt');trace=None;initial_breakpoint_seen=False
            try:
                entries=(b.SidAttributes*2)(b.SidAttributes(sid,0),b.SidAttributes(compatibility,0))
                require(a.CreateRestrictedToken(original,9 if restricted_case else 1,0,None,0,None,2 if restricted_case else 0,entries if restricted_case else None,C.byref(token)))
                row['token_restricted']=bool(a.IsTokenRestricted(token));assert row['token_restricted']==restricted_case
                class Groups(C.Structure):_fields_=[('count',T.DWORD),('first',b.SidAttributes)]
                needed=T.DWORD();a.GetTokenInformation(token,11,None,0,C.byref(needed));assert 0<needed.value<=4096
                info=C.create_string_buffer(needed.value);require(a.GetTokenInformation(token,11,info,needed,C.byref(needed)))
                count=C.cast(info,C.POINTER(Groups)).contents.count;assert count==(2 if restricted_case else 0)
                row['restricting_sids']=[target.string_sid(b.SidAttributes.from_buffer(info,Groups.first.offset+i*C.sizeof(b.SidAttributes)).sid) for i in range(count)]
                assert set(row['restricting_sids'])==({plan['user_sid'],'S-1-5-12'} if restricted_case else set())
                for kind,key in ((20,'elevated'),(29,'appcontainer')):
                    value,size=T.DWORD(),T.DWORD();require(a.GetTokenInformation(token,kind,C.byref(value),4,C.byref(size)));row[key]=value.value;assert not value.value
                sa=b.SecurityAttributes(C.sizeof(b.SecurityAttributes),None,True)
                row['phase']='open_capped_stdio'
                for path,access,disposition in ((name+'-stdio.log',0x40000000,1),('NUL',0x80000000,3)):
                    h=k.CreateFileW(path,access,3,C.byref(sa),disposition,0x80,None)
                    if h==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
                    handles.append(h)
                size=C.c_size_t();k.InitializeProcThreadAttributeList(None,1,0,C.byref(size))
                attributes=C.create_string_buffer(size.value);require(k.InitializeProcThreadAttributeList(attributes,1,0,C.byref(size)));initialized=True
                inherited=(T.HANDLE*2)(*handles);require(k.UpdateProcThreadAttribute(attributes,0,0x20002,inherited,C.sizeof(inherited),None,None))
                startup=b.StartupInfoEx();startup.startup.cb=C.sizeof(startup);startup.startup.desktop=plan['desktop'];startup.startup.flags=0x100
                startup.startup.stdin=handles[1];startup.startup.stdout=startup.startup.stderr=handles[0];startup.attributes=C.addressof(attributes)
                filename='loader-standard.log' if name=='baseline' else 'loader-restricted.log'
                line=subprocess.list2cmdline([plan['image'],'-B',str(ROOT/'loader-observer.py'),filename])
                row['phase']='CreateProcessAsUserW_DEBUG_ONLY_THIS_PROCESS'
                require(a.CreateProcessAsUserW(token,plan['image'],C.create_unicode_buffer(line),None,None,True,0x08080406,None,str(Path.cwd()),C.byref(startup),C.byref(process)))
                row['pid']=process.pid;inside=T.BOOL();require(k.IsProcessInJob(process.process,None,C.byref(inside)));assert inside.value
                row['job_inherited']=True;row['phase']='resume_and_collect';assert k.ResumeThread(process.thread)!=0xffffffff
                trace=trace_path.open('xb');total=0;deadline=time.monotonic()+15
                while not exited:
                    if time.monotonic()>deadline:raise TimeoutError('Owned debuggee exceeded15seconds')
                    event=Event()
                    if not k.WaitForDebugEventEx(C.byref(event),100):
                        if C.get_last_error()==121:continue
                        raise C.WinError(C.get_last_error())
                    assert event.pid==process.pid
                    row['events']+=1;assert row['events']<=4096
                    continuation=0x10002;file_handle=None
                    try:
                        if event.code in (3,6):
                            info=event.data.created if event.code==3 else event.data.loaded;file_handle=info.file
                            path=C.create_unicode_buffer(2048)
                            length=k.GetFinalPathNameByHandleW(file_handle,path,len(path),0) if file_handle else 0
                            row['modules'].append(dict(event=event.code,path=path.value if 0<length<len(path) else None))
                        elif event.code==8:
                            info=event.data.string;n=info.length*(2 if info.unicode else 1);assert n<=131070
                            if n:
                                data=C.create_string_buffer(n);got=C.c_size_t()
                                require(k.ReadProcessMemory(process.process,info.address,data,n,C.byref(got)));assert got.value==n
                                message=data.raw.decode('utf-16le' if info.unicode else 'mbcs',errors='replace').rstrip('\0').encode('utf-8')
                                total+=len(message);assert total<=2097152
                                trace.write(message)
                        elif event.code==1:
                            code=event.data.exception.record.code
                            row['exceptions'].append(dict(code=hex(code),first_chance=event.data.exception.first))
                            if code==0x80000003 and not initial_breakpoint_seen:initial_breakpoint_seen=True
                            else:continuation=0x80010001
                        elif event.code==5:row['exit_code']=event.data.exit_code;exited=True
                    finally:
                        if file_handle:require(k.CloseHandle(file_handle))
                        require(k.ContinueDebugEvent(event.pid,event.tid,continuation))
                trace.close();trace=None
                assert k.WaitForSingleObject(process.process,5000)==0
                raw=trace_path.read_bytes();compressed=lzma.compress(raw,filters=[dict(id=lzma.FILTER_LZMA2,preset=9|lzma.PRESET_EXTREME,dict_size=2097152)])
                assert len(compressed)<=131072 and lzma.decompress(compressed)==raw
                row['trace']=dict(encoding='normalized UTF-8 debugger strings; xz/base64',dictionary_bytes=2097152,bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),xz_sha256=hashlib.sha256(compressed).hexdigest(),xz_base64=base64.b64encode(compressed).decode('ascii'))
                observation=Path(filename);row['breadcrumb']=observation.read_text(encoding='utf-8') if observation.exists() else None
                row['phase']='collected'
            except BaseException:
                row['error']=traceback.format_exc()[-8192:];raise
            finally:
                if trace:trace.close()
                if process.process:
                    if not exited:k.TerminateProcess(process.process,78)
                    # Drain debug events after termination so no debug-stop keeps
                    # an owned process alive while parent cleanup proceeds.
                    until=time.monotonic()+5
                    while k.WaitForSingleObject(process.process,0)!=0 and time.monotonic()<until:
                        event=Event()
                        if k.WaitForDebugEventEx(C.byref(event),100):
                            if event.code in (3,6):
                                h=event.data.created.file if event.code==3 else event.data.loaded.file
                                if h:k.CloseHandle(h)
                            require(k.ContinueDebugEvent(event.pid,event.tid,0x10002))
                    assert k.WaitForSingleObject(process.process,1000)==0
                    k.CloseHandle(process.process)
                if process.thread:k.CloseHandle(process.thread)
                if initialized:k.DeleteProcThreadAttributeList(attributes)
                for h in handles:k.CloseHandle(h)
                if token:k.CloseHandle(token)
                result['variants'].append(row)
        assert result['variants'][0]['exit_code']==0 and result['variants'][0]['breadcrumb'].endswith('complete\n')
        assert all(r['trace']['bytes']>0 for r in result['variants'])
        result['status']='pass'
    except BaseException:
        result.update(status='fail',error=traceback.format_exc()[-8192:]);raise
    finally:
        if compatibility:k.LocalFree(compatibility)
        if sid:k.LocalFree(sid)
        if original:k.CloseHandle(original)
        Path('debug-report.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')

def coordinate(context):
    g=context;W,S=g.W,g.S
    result=dict(status='running',scope='Per-image loader diagnostic only; no ordinary-worker qualification',full_profile_qualified=False,all_owned_processes_retired=False)
    instance,job,child=None,None,None;image=None;image_identity=None;registry=None;key_created=False;source_sha=None
    journal=ROOT/'scratch/ordinary-actor.json'
    try:
        data=g.actor();private={k:os.environ.pop(k) for k in list(os.environ) if k.startswith('DISKED_TEST_ACTOR_')}
        state=json.loads((ROOT/'scratch/state.json').read_bytes());assert state['size_mib']==32
        selected=g.fresh(W.plain_directory(state['work'])/'forensic');instance=g.worker(selected,private)
        source=Path(sys.executable);assert source==Path('C:/ProgramData/DiskEd/python314/python.exe')
        W.plain_directory(source.parent);payload=source.read_bytes();assert len(payload)<=262144
        source_sha=hashlib.sha256(payload).hexdigest();assert source_sha=='4942b86a6597e5aee0128daa00050ed79bc21f6e709a78eb19cbfeb0c2f39ac9'
        image=source.with_name('DiskEdLoader-'+data['nonce']+'.exe')
        registry=r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\Image File Execution Options'+'\\'+image.name
        try:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,registry,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY):raise ValueError('Diagnostic key already exists')
        except FileNotFoundError:pass
        data['loader']=dict(phase='creating',image=str(image),image_sha256=source_sha,registry=registry)
        journal.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')
        with image.open('xb') as stream:stream.write(payload);stream.flush();os.fsync(stream.fileno())
        stat=image.lstat();image_identity=(stat.st_dev,stat.st_ino)
        a=instance.a;handle=P();disposition=T.DWORD()
        W.bind(a,'RegCreateKeyExW',T.LONG,P,T.LPCWSTR,T.DWORD,T.LPWSTR,T.DWORD,T.DWORD,P,C.POINTER(P),C.POINTER(T.DWORD))
        W.bind(a,'RegCloseKey',T.LONG,P)
        error=a.RegCreateKeyExW(int(winreg.HKEY_LOCAL_MACHINE),registry,0,None,0,winreg.KEY_READ|winreg.KEY_WRITE|winreg.KEY_WOW64_64KEY,None,C.byref(handle),C.byref(disposition))
        if error:raise C.WinError(error)
        try:
            if disposition.value!=1:raise ValueError('Diagnostic key was not newly created')
            key_created=True
            winreg.SetValueEx(handle.value,'DiskEdOwnerNonce',0,winreg.REG_SZ,data['nonce'])
            winreg.SetValueEx(handle.value,'GlobalFlag',0,winreg.REG_SZ,'0x00000002')
        finally:a.RegCloseKey(handle)
        data['loader']['phase']='created';journal.write_text(json.dumps(data,indent=2)+'\n',encoding='utf-8',newline='\n')
        request=selected/'debug-plan.json';request.write_text(json.dumps(dict(work=str(selected),user_sid=data['sid'],desktop=instance.desktop_name,image=str(image),image_sha256=source_sha)))
        job=S.WindowsJob();child=instance.launch([sys.executable,'-B',str(ROOT/'loader-forensics.py'),'--actor',str(request)],os.environ,job,diagnostic_original=True)
        code=child.wait(timeout=40);result['actor_exit_code']=code
        path=selected/'debug-report.json'
        if path.exists():
            raw=path.read_bytes();assert len(raw)<=524288;result['debug']=json.loads(raw)
        assert code==0 and result['debug']['status']=='pass'
        result.update(status='pass',image_sha256=source_sha,registry_scope=registry)
    except BaseException:
        result.update(status='fail',error=traceback.format_exc()[-8192:]);raise
    finally:
        try:
            if job:
                class Accounting(C.Structure):
                    _fields_=[('times',C.c_longlong*4),('faults',T.DWORD),('total',T.DWORD),('active',T.DWORD),('terminated',T.DWORD)]
                query=W.bind(job.api,'QueryInformationJobObject',T.BOOL,T.HANDLE,C.c_int,P,T.DWORD,P)
                W.require(job.api.TerminateJobObject(job.handle,78))
                until=time.monotonic()+10
                while True:
                    info=Accounting();W.require(query(job.handle,1,C.byref(info),C.sizeof(info),None))
                    if info.active==0:break
                    if time.monotonic()>until:raise TimeoutError('Owned debugger job is not quiescent')
                    time.sleep(.05)
                result['job_active_processes_at_retirement']=info.active
                job.close()
            if child:child.wait(timeout=10);child.close()
            result['all_owned_processes_retired']=True
            if instance:instance.close()
            if key_created:
                with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,registry,0,winreg.KEY_READ|winreg.KEY_WOW64_64KEY) as key:
                    assert winreg.QueryInfoKey(key)[:2]==(0,2)
                    assert winreg.QueryValueEx(key,'DiskEdOwnerNonce')==(data['nonce'],winreg.REG_SZ)
                    assert winreg.QueryValueEx(key,'GlobalFlag')==('0x00000002',winreg.REG_SZ)
                winreg.DeleteKeyEx(winreg.HKEY_LOCAL_MACHINE,registry,winreg.KEY_WOW64_64KEY,0)
                result['image_registry_removed']=True
            if image_identity:
                stat=image.lstat();assert (stat.st_dev,stat.st_ino)==image_identity and not image.is_symlink() and not stat.st_file_attributes&0x400
                assert hashlib.sha256(image.read_bytes()).hexdigest()==source_sha
                image.unlink();result['diagnostic_image_removed']=True
            if source_sha:
                assert hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()==source_sha
                result['original_runtime_preserved']=True
        except BaseException:
            result.update(status='fail',cleanup_error=traceback.format_exc()[-8192:]);raise
        finally:
            (ROOT/'proof-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':
    if Path(__file__).resolve().parent!=ROOT or len(sys.argv)!=3 or sys.argv[1] not in ('--actor','--namespace'):raise ValueError('Fixed guest actor invocation only')
    (namespace_actor if sys.argv[1]=='--namespace' else actor)(json.loads(Path(sys.argv[2]).read_bytes()))
