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

def worker(work, private):
    return O.Worker(W,work,Path(os.environ['DISKED_WORK_ROOT']),
                    private['DISKED_TEST_ACTOR_NAME'],private['DISKED_TEST_ACTOR_PASS'],
                    private['DISKED_TEST_ACTOR_SID'])

def plan(work, data):
    path=work/'launch.json'
    state=json.loads((ROOT/'scratch/state.json').read_bytes())
    path.write_text(json.dumps(dict(user_sid=data['sid'],source=str(ROOT/'ordinary-worker.py'),
        outside=str(ROOT/'scratch/outside'),backing=state['image'])))
    return path

def controller():
    data=actor(); private={k:v for k,v in os.environ.items() if k.startswith('DISKED_TEST_ACTOR_')}
    work=Path(sys.argv[2]);assert work==Path(json.loads((ROOT/'scratch/state.json').read_bytes())['work'])/'abrupt'
    instance,job,child=None,None,None
    try:
        instance=worker(work,private); request=plan(work,data);job=S.WindowsJob()
        child=instance.launch([sys.executable,'-B',str(ROOT/'target.py'),str(request),'hold'],os.environ,job)
        (work/'controller.json').write_text(json.dumps(dict(controller_pid=os.getpid(),worker_pid=child.pid)))
        child.wait(timeout=35)
        raise RuntimeError('Outer coordinator failed to interrupt the owned controller')
    finally:
        if job:job.close()
        if child:child.close()
        if instance:instance.close()

def main():
    if ROOT!=Path('C:/ProgramData/DiskEd/qualification') or not __debug__:
        raise RuntimeError('Fixed guest source and active assertions required')
    result=dict(status='running',scope='Ordinary-token primitive proof only; no DiskEd/compiler qualification',
                all_owned_processes_retired=False)
    instance,job,child,coordinator=None,None,None,None
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
        normal=fresh(work_root/'normal'); instance=worker(normal,private)
        result['coordinator_sid']=instance.coordinator_sid
        instance.apply_acl(outside,'D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;'+instance.coordinator_sid+')(A;OICI;0x1301bf;;;BU)')
        W.bind(instance.a,'ImpersonateLoggedOnUser',T.BOOL,T.HANDLE)
        W.bind(instance.a,'RevertToSelf',T.BOOL)
        W.require(instance.a.ImpersonateLoggedOnUser(instance.original))
        try:(outside/'baseline').write_bytes(b'1')
        finally:W.require(instance.a.RevertToSelf())
        assert (outside/'baseline').read_bytes()==b'1'
        (outside/'baseline').unlink();result['ordinary_group_write_control']=True
        source_before=hashlib.sha256((ROOT/'ordinary-worker.py').read_bytes()).hexdigest()
        request=plan(normal,data);job=S.WindowsJob()
        child=instance.launch([sys.executable,'-B',str(ROOT/'target.py'),str(request)],os.environ,job)
        code=child.wait(timeout=25)
        result['normal_exit_code']=code
        log=(normal/'worker.log').read_bytes();assert len(log)<=65536
        result['normal_log']=log.decode(errors='replace')
        assert code==0
        result['payload']=json.loads((normal/'payload-result.json').read_bytes())
        assert result['payload']['status']=='pass'
        assert 'ordinary-worker-proof-output' in result['normal_log']
        assert hashlib.sha256((ROOT/'ordinary-worker.py').read_bytes()).hexdigest()==source_before
        assert (outside/'sentinel').read_bytes()==b'preserve-owned-sentinel'
        assert set(p.name for p in outside.iterdir())=={'sentinel'}
        job.close();job=None;child.close();child=None;instance.close();instance=None
        abrupt=fresh(work_root/'abrupt')
        controller_log=Path(os.environ['DISKED_WORK_ROOT'])/'controller.log'
        with controller_log.open('wb') as output:
            coordinator=subprocess.Popen([sys.executable,'-B',__file__,'--controller',str(abrupt)],
                env=dict(os.environ,**private),stdout=output,stderr=subprocess.STDOUT)
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
                assert record['user_sid']==record['restricting_sid']==data['sid'] and record['restricted']
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
        if instance:instance.close()
        if observed:
            for handle,record in observed:
                W.require(k.WaitForSingleObject(handle,10000)==0);W.require(k.CloseHandle(handle))
        result['all_owned_processes_retired']=True
        result['guest_c_free_bytes']=shutil.disk_usage('C:/').free
        result['python_sha256']=hashlib.sha256(Path(sys.executable).read_bytes()).hexdigest()
        if 'normal' in locals() and (normal/'worker.log').exists():
            data=(normal/'worker.log').read_bytes();assert len(data)<=65536
            result['normal_log']=data.decode(errors='replace')
        (ROOT/'proof-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')

if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--controller':controller()
    else:main()
