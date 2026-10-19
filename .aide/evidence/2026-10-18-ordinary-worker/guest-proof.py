"""Guest coordinator for one finite ordinary-token proof, including abrupt exit."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent

class FileIdentity(C.Structure):
    _fields_=[('volume',C.c_ulonglong),('identity',C.c_ubyte*16)]

def load(name, path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

W=load('ordinary_base',ROOT/'tools/windows-worker.py')
S=load('ordinary_storage',ROOT/'tools/workspace.py')
O=load('ordinary_worker',ROOT/'ordinary-worker.py')

def fresh(path):
    path.mkdir()
    (path/'owner.json').write_text(json.dumps(dict(root=str(ROOT))))
    return path

def actor():
    data=json.loads((ROOT/'scratch/ordinary-actor.json').read_bytes())
    assert data['phase']=='created'
    assert os.environ['DISKED_TEST_ACTOR_NAME']==data['name']
    assert os.environ['DISKED_TEST_ACTOR_SID']==data['sid']
    return data

def worker(work, private, *, namespace_compat=False):
    return O.Worker(W,work,Path(os.environ['DISKED_WORK_ROOT']),
                    private['DISKED_TEST_ACTOR_NAME'],private['DISKED_TEST_ACTOR_PASS'],
                    private['DISKED_TEST_ACTOR_SID'],namespace_compat=namespace_compat)

def plan(work, data):
    path=work/'launch.json'
    state=json.loads((ROOT/'scratch/state.json').read_bytes())
    path.write_text(json.dumps(dict(user_sid=data['sid'],source=str(ROOT/'ordinary-worker.py'),
        outside=str(ROOT/'scratch/outside'),backing=state['image'],profile='fresh-user-restricted-code/v1')))
    return path

def controller():
    data=actor(); private={k:v for k,v in os.environ.items() if k.startswith('DISKED_TEST_ACTOR_')}
    work=Path(sys.argv[2]);assert work==Path(json.loads((ROOT/'scratch/state.json').read_bytes())['work'])/'abrupt'
    instance,job,child=None,None,None
    try:
        instance=worker(work,private,namespace_compat=True); request=plan(work,data);job=S.WindowsJob()
        child=instance.launch([sys.executable,'-B',str(ROOT/'target.py'),str(request),'hold'],os.environ,job)
        (work/'controller.json').write_text(json.dumps(dict(controller_pid=os.getpid(),worker_pid=child.pid)))
        child.wait(timeout=35)
        raise RuntimeError('Outer coordinator failed to interrupt the owned controller')
    finally:
        if job:job.close()
        if child:child.close()
        if instance:instance.close()

def diagnose():
    """Finite API-parameter isolation; does not qualify the full worker profile."""
    result=dict(status='running',scope='WithToken startup/handle-attribute diagnostic only',
                full_profile_qualified=False,all_owned_processes_retired=False,variants=[])
    instance,job,child,canary=None,None,None,None
    try:
        data=actor();private={k:os.environ.pop(k) for k in list(os.environ) if k.startswith('DISKED_TEST_ACTOR_')}
        expected=json.loads((ROOT/'expected.json').read_bytes())['launch_diagnostic']
        state=json.loads((ROOT/'scratch/state.json').read_bytes());assert state['size_mib']==32
        root=W.plain_directory(state['work']);selected=fresh(root/'diagnostic');instance=worker(selected,private)
        outside=ROOT/'scratch/outside';outside.mkdir();(outside/'sentinel').write_bytes(b'preserve-owned-sentinel')
        k=instance.k
        W.bind(k,'CreateFileW',T.HANDLE,T.LPCWSTR,T.DWORD,T.DWORD,C.POINTER(W.SecurityAttributes),T.DWORD,T.DWORD,T.HANDLE)
        W.bind(k,'GetFileInformationByHandleEx',T.BOOL,T.HANDLE,C.c_int,C.c_void_p,T.DWORD)
        sa=W.SecurityAttributes(C.sizeof(W.SecurityAttributes),None,True)
        canary=k.CreateFileW(str(outside/'inheritance-canary.bin'),0xc0000000,3,C.byref(sa),1,0x80,None)
        if canary==C.c_void_p(-1).value:canary=None;raise C.WinError(C.get_last_error())
        identity=FileIdentity();W.require(k.GetFileInformationByHandleEx(canary,18,C.byref(identity),C.sizeof(identity)))
        request=selected/'launch.json'
        for variant in expected['variants']:
            request.write_text(json.dumps(dict(user_sid=data['sid'],variant=variant,canary_handle=canary,
                canary_volume=str(identity.volume),canary_identity=bytes(identity.identity).hex())))
            row=dict(variant=variant)
            try:
                job=S.WindowsJob()
                child=instance.launch([sys.executable,'-B',str(ROOT/'target.py'),str(request),'launch'],os.environ,job,variant=variant)
                row.update(api_succeeded=True,pid=child.pid)
                row['exit_code']=child.wait(timeout=15)
                path=selected/('launch-'+variant+'.json')
                row['observation']=json.loads(path.read_bytes()) if path.exists() else None
            except OSError as error:
                if (getattr(instance,'last_launch',None) or {}).get('api_succeeded') or isinstance(error,TimeoutError):raise
                row.update(api_succeeded=False,winerror=error.winerror)
            finally:
                row['launch_parameters']=getattr(instance,'last_launch',None)
                if job:job.close();job=None
                if child:child.wait(timeout=10);child.close();child=None
                result['variants'].append(row)
        candidates=[]
        for row in result['variants']:
            observed=row.get('observation')
            empty=bool(observed and all(item['kind']==0 and item['winerror']==6 for item in observed['stdio']))
            declared=bool(observed and row['variant']=='basic-stdio' and observed['stdio'][0]['kind']==2 and
                all(item.get('file_identity')==row['launch_parameters'].get('stdout_identity') and item['kind']==1
                    for item in observed['stdio'][1:]))
            if (row.get('api_succeeded') and row['exit_code']==0 and observed and
                    not observed['canary_inherited'] and (empty or declared)):
                candidates.append(row['variant'])
        result['candidate_variants']=candidates
        assert [r['variant'] for r in result['variants']]==expected['variants'] and candidates
        result.update(status='pass',actor=dict(name=data['name'],sid=data['sid'],nonce=data['nonce']))
    except BaseException:
        result.update(status='fail',error=traceback.format_exc()[-16384:]);raise
    finally:
        if job:job.close()
        if child:child.wait(timeout=10);child.close()
        if canary:W.require(instance.k.CloseHandle(canary))
        if instance:instance.close()
        result['all_owned_processes_retired']=True
        (ROOT/'proof-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')

def startup_diagnose():
    """Original versus restricted token; no product or confinement admission."""
    result=dict(status='running',scope='Token/console startup diagnostic only',
                full_profile_qualified=False,all_owned_processes_retired=False,variants=[])
    instance,job,child=None,None,None
    try:
        data=actor();private={k:os.environ.pop(k) for k in list(os.environ) if k.startswith('DISKED_TEST_ACTOR_')}
        state=json.loads((ROOT/'scratch/state.json').read_bytes());assert state['size_mib']==32
        selected=fresh(W.plain_directory(state['work'])/'startup');instance=worker(selected,private)
        result['private_ui_security']=instance.ui_security
        for name,variant,original in (('standard-no-window','basic-stdio',True),
                ('restricted-no-window','basic-stdio',False),('restricted-detached','basic-detached',False),
                ('restricted-user-default-dacl','basic-stdio',False),('own-restricted-bootstrap','basic-stdio',True),
                ('restricted-user-logon','basic-stdio',False)):
            if name=='restricted-user-default-dacl':result['token_default_dacl_change']=instance.set_default_dacl()
            if name=='restricted-user-logon':result['fresh_logon_candidate']=instance.use_logon_restriction()
            request=selected/'startup-request.json';request.write_text(json.dumps(dict(variant=name,user_sid=data['sid'],desktop=instance.desktop_name)))
            row=dict(name=name)
            try:
                job=S.WindowsJob()
                mode='bootstrap' if name=='own-restricted-bootstrap' else 'startup'
                child=instance.launch([sys.executable,'-B',str(ROOT/'target.py'),str(request),mode],
                                      os.environ,job,variant=variant,diagnostic_original=original)
                row['exit_code']=child.wait(timeout=15)
                path=selected/('startup-'+name+'.json')
                row['observation']=json.loads(path.read_bytes()) if path.exists() else None
                if mode=='bootstrap':row['bootstrap']=json.loads((selected/'bootstrap-result.json').read_bytes())
            except OSError as error:
                row['error']=str(error)
            finally:
                row['parameters']=instance.last_launch
                if job:job.close();job=None
                if child:child.wait(timeout=10);child.close();child=None
                result['variants'].append(row)
        assert len(result['variants'])==6 and all(r['parameters'] for r in result['variants'])
        result['status']='pass'  # Complete diagnostic, not successful launch/admission.
    except BaseException:
        result.update(status='fail',error=traceback.format_exc()[-16384:]);raise
    finally:
        if job:job.close()
        if child:child.wait(timeout=10);child.close()
        if instance:instance.close()
        result['all_owned_processes_retired']=True
        (ROOT/'proof-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')

def main():
    if ROOT!=Path('C:/ProgramData/DiskEd/qualification') or not __debug__:
        raise RuntimeError('Fixed guest source and active assertions required')
    result=dict(status='running',scope='Ordinary-token primitive proof only; no DiskEd/compiler qualification',
                all_owned_processes_retired=False)
    instance,job,child,coordinator,canary=None,None,None,None,None
    observed=[]
    try:
        data=actor();result['actor']={k:data[k] for k in ('name','sid','nonce')}
        private={k:os.environ.pop(k) for k in list(os.environ) if k.startswith('DISKED_TEST_ACTOR_')}
        state=json.loads((ROOT/'scratch/state.json').read_bytes());assert state['size_mib']==32
        result['image_uuid']=state['image_uuid'];result['capped_volume']=state['volume_unique_id']
        work_root=W.plain_directory(state['work'])
        assert shutil.disk_usage(work_root).total<=32*1024*1024
        outside=ROOT/'scratch/outside';outside.mkdir()
        (outside/'sentinel').write_bytes(b'preserve-owned-sentinel')
        normal=fresh(work_root/'normal'); instance=worker(normal,private,namespace_compat=True)
        result['coordinator_sid']=instance.coordinator_sid
        result['coordinator_integrity_sid']=instance.coordinator_integrity_sid
        result['actor_integrity_sid']=instance.integrity_sid
        result['private_ui_security']=instance.ui_security
        assert all('(ML;;NW;;;ME)' in value for value in instance.ui_security.values())
        instance.apply_acl(outside,'D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;'+instance.coordinator_sid+')(A;OICI;0x1301bf;;;BU)')
        W.bind(instance.a,'ImpersonateLoggedOnUser',T.BOOL,T.HANDLE)
        W.bind(instance.a,'RevertToSelf',T.BOOL)
        W.require(instance.a.ImpersonateLoggedOnUser(instance.original))
        try:(outside/'baseline').write_bytes(b'1')
        finally:W.require(instance.a.RevertToSelf())
        assert (outside/'baseline').read_bytes()==b'1'
        (outside/'baseline').unlink();result['ordinary_group_write_control']=True
        source_before=hashlib.sha256((ROOT/'ordinary-worker.py').read_bytes()).hexdigest()
        request=plan(normal,data)
        W.bind(instance.k,'CreateFileW',T.HANDLE,T.LPCWSTR,T.DWORD,T.DWORD,C.POINTER(W.SecurityAttributes),T.DWORD,T.DWORD,T.HANDLE)
        W.bind(instance.k,'GetFileInformationByHandleEx',T.BOOL,T.HANDLE,C.c_int,C.c_void_p,T.DWORD)
        sa=W.SecurityAttributes(C.sizeof(W.SecurityAttributes),None,True)
        canary=instance.k.CreateFileW(str(outside/'inheritance-canary.bin'),0xc0000000,3,C.byref(sa),1,0x80,None)
        if canary==C.c_void_p(-1).value:canary=None;raise C.WinError(C.get_last_error())
        identity=FileIdentity();W.require(instance.k.GetFileInformationByHandleEx(canary,18,C.byref(identity),C.sizeof(identity)))
        payload=json.loads(request.read_bytes());payload.update(canary_handle=canary,canary_volume=str(identity.volume),canary_identity=bytes(identity.identity).hex())
        request.write_text(json.dumps(payload));job=S.WindowsJob()
        child=instance.launch([sys.executable,'-B',str(ROOT/'target.py'),str(request)],os.environ,job)
        code=child.wait(timeout=25)
        result['normal_exit_code']=code
        result['launch_parameters']=instance.last_launch
        log=instance.log_path.read_bytes();assert len(log)<=65536
        result['normal_log']=log.decode(errors='replace')
        if (normal/'payload-result.json').exists():result['payload']=json.loads((normal/'payload-result.json').read_bytes())
        assert code==0
        assert result['payload']['status']=='pass'
        assert result['payload']['record_sha256']==hashlib.sha256(b'TWO').hexdigest()
        assert result['payload']['record_sddl']=='D:P(A;;FA;;;SY)(A;;FA;;;'+data['sid']+')'
        assert all(row['file_identity']==instance.last_launch['stdout_identity'] for row in result['payload']['stdio'][1:])
        assert 'ordinary-worker-proof-output' in result['normal_log']
        assert hashlib.sha256((ROOT/'ordinary-worker.py').read_bytes()).hexdigest()==source_before
        assert (outside/'sentinel').read_bytes()==b'preserve-owned-sentinel'
        assert set(p.name for p in outside.iterdir())=={'sentinel','inheritance-canary.bin'}
        job.close();job=None;child.close();child=None
        W.require(instance.k.CloseHandle(canary));canary=None
        instance.close();instance=None
        abrupt=fresh(work_root/'abrupt')
        controller_log=Path(os.environ['DISKED_WORK_ROOT'])/'controller.log'
        with controller_log.open('wb') as output:
            coordinator=subprocess.Popen([sys.executable,'-B',__file__,'--controller',str(abrupt)],
                env=dict(os.environ,**private),stdout=output,stderr=subprocess.STDOUT,close_fds=True)
            deadline=time.monotonic()+15
            while not all((abrupt/n).is_file() for n in ('controller.json','hold.json','descendant.json')):
                if coordinator.poll() is not None:raise RuntimeError('Owned abrupt controller exited before readiness')
                if time.monotonic()>=deadline:raise TimeoutError('Owned abrupt controller readiness expired')
                time.sleep(.05)
            identity=json.loads((abrupt/'controller.json').read_bytes())
            held=json.loads((abrupt/'hold.json').read_bytes())
            descendant=json.loads((abrupt/'descendant.json').read_bytes())
            assert identity['controller_pid']==coordinator.pid and identity['worker_pid']==held['pid']
            assert held['descendant_pid']==descendant['pid']
            for record in (held,descendant):
                assert record['user_sid']==data['sid'] and record['restricted']
                assert len(record['restricting_sids'])==2 and set(record['restricting_sids'])=={data['sid'],'S-1-5-12'}
                assert not any(record[k] for k in ('administrator','elevated','appcontainer'))
            k=C.WinDLL('kernel32',use_last_error=True)
            W.bind(k,'OpenProcess',T.HANDLE,T.DWORD,T.BOOL,T.DWORD)
            W.bind(k,'GetProcessTimes',T.BOOL,T.HANDLE,C.POINTER(T.FILETIME),C.POINTER(T.FILETIME),C.POINTER(T.FILETIME),C.POINTER(T.FILETIME))
            W.bind(k,'WaitForSingleObject',T.DWORD,T.HANDLE,T.DWORD)
            W.bind(k,'GetExitCodeProcess',T.BOOL,T.HANDLE,C.POINTER(T.DWORD))
            W.bind(k,'CloseHandle',T.BOOL,T.HANDLE)
            W.bind(k,'CreateFileW',T.HANDLE,T.LPCWSTR,T.DWORD,T.DWORD,C.c_void_p,T.DWORD,T.DWORD,T.HANDLE)
            result['held_before_interruption']=[]
            for name in ('held.bin','descendant-held.bin'):
                handle=k.CreateFileW(str(abrupt/name),0x10000,7,None,3,0x80,None)
                error=C.get_last_error()
                if handle!=C.c_void_p(-1).value:k.CloseHandle(handle)
                result['held_before_interruption'].append(dict(path=name,winerror=error))
                assert handle==C.c_void_p(-1).value and error==32
            for pid in (held['pid'],descendant['pid']):
                handle=W.require(k.OpenProcess(0x101000,False,pid))
                born,exited,kernel,user=T.FILETIME(),T.FILETIME(),T.FILETIME(),T.FILETIME()
                W.require(k.GetProcessTimes(handle,C.byref(born),C.byref(exited),C.byref(kernel),C.byref(user)))
                observed.append((handle,dict(pid=pid,creation_time=str((born.dwHighDateTime<<32)|born.dwLowDateTime))))
            coordinator.kill();coordinator.wait(timeout=10)
            result['abrupt_controller_exit']=coordinator.returncode
            result['retired_processes']=[]
            for handle,record in observed:
                assert k.WaitForSingleObject(handle,10000)==0
                code=T.DWORD();W.require(k.GetExitCodeProcess(handle,C.byref(code)))
                record['exit_code']=code.value;result['retired_processes'].append(record)
            (abrupt/'held.bin').unlink();(abrupt/'descendant-held.bin').unlink()
            result['held_files_released']=True
        assert controller_log.stat().st_size<=65536
        result['controller_log']=controller_log.read_text(errors='replace')
        result.update(status='pass',source_preserved=True,outside_sentinel_preserved=True)
    except BaseException:
        result.update(status='fail',error=traceback.format_exc()[-16384:])
        raise
    finally:
        if coordinator and coordinator.poll() is None:
            coordinator.kill();coordinator.wait(timeout=10)
        if job:job.close()
        if child:
            child.wait(timeout=10);child.close()
        if canary and instance:W.require(instance.k.CloseHandle(canary))
        if instance:instance.close()
        if observed:
            for handle,record in observed:
                W.require(k.WaitForSingleObject(handle,10000)==0);W.require(k.CloseHandle(handle))
        result['all_owned_processes_retired']=True
        result['guest_c_free_bytes']=shutil.disk_usage('C:/').free
        result['python_sha256']=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
        if 'normal' in locals() and (normal/'worker-basic-stdio.log').exists():
            data=(normal/'worker-basic-stdio.log').read_bytes();assert len(data)<=65536
            result['normal_log']=data.decode(errors='replace')
        (ROOT/'proof-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')

def loader_diagnose():
    result=dict(status='running',scope='Pure Python entry/import breadcrumb diagnostic only',
                full_profile_qualified=False,all_owned_processes_retired=False,variants=[])
    instance,job,child=None,None,None
    try:
        data=actor();private={k:os.environ.pop(k) for k in list(os.environ) if k.startswith('DISKED_TEST_ACTOR_')}
        state=json.loads((ROOT/'scratch/state.json').read_bytes());assert state['size_mib']==32
        selected=fresh(W.plain_directory(state['work'])/'loader');instance=worker(selected,private)
        for name,original in (('standard',True),('restricted',False)):
            row=dict(name=name,observer_receipt=None)
            try:
                job=S.WindowsJob();filename='loader-'+name+'.log'
                child=instance.launch([sys.executable,'-B',str(ROOT/'loader-observer.py'),filename],os.environ,job,diagnostic_original=original)
                row['exit_code']=child.wait(timeout=15)
                path=selected/filename
                if path.exists():
                    raw=path.read_bytes();assert len(raw)<=8192
                    row['observer_receipt']=raw.decode('utf-8');row['observer_sha256']=hashlib.sha256(raw).hexdigest()
                log=instance.log_path.read_bytes();assert len(log)<=65536
                row['standard_output']=log.decode(errors='replace')
            finally:
                row['parameters']=instance.last_launch
                if job:job.close();job=None
                if child:child.wait(timeout=10);child.close();child=None
                result['variants'].append(row)
        request=selected/'own-ui-request.json'
        request.write_text(json.dumps(dict(variant='actor-owned-ui',create_ui=True,user_sid=data['sid'],coordinator_sid=instance.coordinator_sid)))
        row=dict(name='actor-owned-ui-bootstrap')
        try:
            job=S.WindowsJob()
            child=instance.launch([sys.executable,'-B',str(ROOT/'target.py'),str(request),'bootstrap'],os.environ,job,diagnostic_original=True)
            row['exit_code']=child.wait(timeout=15)
            row['bootstrap']=json.loads((selected/'bootstrap-result.json').read_bytes())
            path=selected/'startup-actor-owned-ui.json'
            row['observation']=json.loads(path.read_bytes()) if path.exists() else None
        finally:
            row['parameters']=instance.last_launch
            if job:job.close();job=None
            if child:child.wait(timeout=10);child.close();child=None
            result['variants'].append(row)
        assert len(result['variants'])==3 and result['variants'][0]['exit_code']==0
        assert result['variants'][0]['observer_receipt'].endswith('complete\n')
        result['status']='pass'  # Diagnostic collection only.
    except BaseException:
        result.update(status='fail',error=traceback.format_exc()[-16384:]);raise
    finally:
        if job:job.close()
        if child:child.wait(timeout=10);child.close()
        if instance:instance.close()
        result['all_owned_processes_retired']=True
        (ROOT/'proof-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--controller':controller()
    elif len(sys.argv)>1 and sys.argv[1]=='--loader-forensics':load('loader_forensics',ROOT/'loader-forensics.py').coordinate(sys.modules[__name__])
    elif len(sys.argv)>1 and sys.argv[1]=='--namespace-diagnostic':load('namespace_forensics',ROOT/'loader-forensics.py').coordinate_namespace(sys.modules[__name__])
    elif len(sys.argv)>1 and sys.argv[1]=='--loader-diagnostic':loader_diagnose()
    elif len(sys.argv)>1 and sys.argv[1]=='--startup-diagnostic':startup_diagnose()
    elif len(sys.argv)>1 and sys.argv[1]=='--diagnostic':diagnose()
    else:main()
