"""Guest-only cooperative capture control; no product capture admission."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import io
import json
import lzma
import os
from pathlib import Path
import shutil
import struct
import sys
import tarfile
import threading
import time
import traceback

FILES=('source/platform/windows/ui/window_capture.cpp','source/platform/windows/ui/window_capture.h',
       'tests/frontend/window_capture_probe.cpp','source/portable/hash/sha256.cpp','source/portable/hash/sha256.h',
       'source/runtime/command/json.cpp','source/runtime/command/json.h','tests/support/cooperative_capture.py',
       'tests/frontend/window_capture_import_probe.cpp')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def query_job(g,worker,report):
    # An empty native wrapper supplies the ABI declarations. Replace only its
    # freshly owned empty object, before any process can be assigned to it.
    job=g.S.WindowsJob(memory_bytes=268435456,process_limit=8);job.close()
    descriptor=C.c_void_p()
    sddl='D:P(A;;GA;;;SY)(A;;GA;;;'+worker.coordinator_sid+')(A;;0x4;;;'+worker.user_sid+')'
    g.W.require(worker.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl,1,C.byref(descriptor),None))
    try:
        attributes=g.W.SecurityAttributes(C.sizeof(g.W.SecurityAttributes),descriptor,False)
        C.set_last_error(0);handle=job.api.CreateJobObjectW(C.byref(attributes),None);error=C.get_last_error()
        if not handle:raise C.WinError(error)
        job.handle=handle
    finally:worker.k.LocalFree(descriptor)
    try:
        limits=job.limit_info_type();limits.basic.flags=0x2208;limits.basic.active=8;limits.job_memory=268435456
        g.W.require(job.api.SetInformationJobObject(job.handle,9,C.byref(limits),C.sizeof(limits)))
        observed=job.limit_info_type();query=g.W.bind(job.api,'QueryInformationJobObject',T.BOOL,T.HANDLE,C.c_int,C.c_void_p,T.DWORD,C.c_void_p)
        g.W.require(query(job.handle,9,C.byref(observed),C.sizeof(observed),None))
        assert observed.basic.flags==0x2208 and observed.basic.active==8 and observed.job_memory==268435456
        row=dict(anonymous=True,creation_dacl=sddl,actor_access='JOB_OBJECT_QUERY only',job_commit_bytes=observed.job_memory,process_limit=observed.basic.active)
        report['query_jobs'].append(row);return job,row
    except BaseException:job.close();raise


class GuardedJob:
    def __init__(self,g,named,row):
        self.g,self.named,self.row=g,named,row;self.handle=named.handle
        self.guard=g.S.WindowsJob(memory_bytes=268435456,process_limit=8)
        self.api=self;self.fault_closed=False;self.lock=threading.Lock()
    def __getattr__(self,name):return getattr(self.named.api,name)
    def AssignProcessToJobObject(self,handle,process):
        assert handle==self.handle
        if not self.guard.api.AssignProcessToJobObject(self.guard.handle,process):return False
        return self.named.api.AssignProcessToJobObject(handle,process)
    def lose_controller_handle(self):
        with self.lock:
            assert self.guard.handle and not self.fault_closed
            self.g.W.require(self.guard.api.CloseHandle(self.guard.handle))
            self.guard.handle=None;self.fault_closed=True;self.row['supervisor_handle_closed_without_termination']=True
    def close(self):
        with self.lock:
            if not self.handle:return
            if self.guard.handle:self.row['supervisor_retirement']=self.g.retire_job(self.guard)
            else:assert self.fault_closed
            self.named.close();self.handle=None


def exercise(g,work,environment,executor,result):
    oracle=g.load('cooperative_pixel_oracle',g.ROOT/'pixel-origin.py')
    verifier=g.load('cooperative_frame',g.ROOT/'tests/support/cooperative_capture.py')
    expected=json.loads((g.ROOT/'expected.json').read_bytes())['cooperative_capture']
    assert expected['limits']['scratch_mib']==32 and expected['expected_negative_controls']==list(verifier.NEGATIVES)
    report=dict(status='running',method=verifier.METHOD,modes=[],query_jobs=[],product_capture_admitted=False,display_dc_read=False,desktop_switched=False)
    result['cooperative_capture']=report
    folder=work/'cooperative';folder.mkdir();objects=folder/'obj';objects.mkdir();artifacts=folder/'observations';artifacts.mkdir()
    total=0
    def save(name,body):
        nonlocal total
        assert type(body) is bytes and len(body)<=262144 and total+len(body)<=1048576
        path=artifacts/name;assert path.parent==artifacts and not path.exists();path.write_bytes(body);total+=len(body)
        return dict(path=name,bytes=len(body),sha256=hashlib.sha256(body).hexdigest())
    report['sources']={name:sha(g.ROOT/name) for name in FILES}
    binary=Path(environment['PATH'].split(os.pathsep)[0]);executable=folder/'window-capture-control.exe'
    common=['/nologo','/std:c++14','/W4','/WX','/MT','/O2','/EHsc','/GS','/sdl','/guard:cf','/permissive-','/utf-8','/D_WIN32_WINNT=0x0A00','/I'+str(g.ROOT/'source')]
    sources=[g.ROOT/name for name in FILES if name.endswith('.cpp') and not name.endswith('window_capture_import_probe.cpp')]
    argv=[str(binary/'cl.exe'),*common,'/Fo'+str(objects)+'\\','/Fe'+str(executable),*[str(p) for p in sources],
          'kernel32.lib','advapi32.lib','user32.lib','gdi32.lib','/link','/DYNAMICBASE','/NXCOMPAT','/guard:cf']
    value=executor(argv=argv,cwd=work,payload=b'',timeout=120,output_limit=131072)
    report['compile']=dict(argv=argv,outcome=value['outcome'],exit_code=value['exit_code'],
        raw={key:save('compile.'+key,value[key]) for key in ('stdout','stderr')})
    if value['outcome']!='exited' or value['exit_code']!=0:
        report.update(status='compile_failed',diagnostic_tail=(value['stdout']+value['stderr'])[-16384:].decode(errors='replace'))
        raise RuntimeError('Capture control compilation failed')
    header=folder/'header.cpp';header.write_text('#include "platform/windows/ui/window_capture.h"\n',encoding='utf-8',newline='\n')
    argv=[str(binary/'cl.exe'),*common,'/c','/Fo'+str(objects/'header.obj'),str(header)]
    value=executor(argv=argv,cwd=work,payload=b'',timeout=60,output_limit=65536)
    report['standalone_header']=dict(argv=argv,outcome=value['outcome'],exit_code=value['exit_code'],raw={key:save('header.'+key,value[key]) for key in ('stdout','stderr')})
    assert value['outcome']=='exited' and value['exit_code']==0
    value=executor(argv=[str(binary/'dumpbin.exe'),'/imports',str(executable)],cwd=work,payload=b'',timeout=30,output_limit=65536)
    report['imports']=dict(outcome=value['outcome'],exit_code=value['exit_code'],raw={key:save('imports.'+key,value[key]) for key in ('stdout','stderr')})
    assert value['outcome']=='exited' and value['exit_code']==0
    report['artifact']=dict(bytes=executable.stat().st_size,sha256=sha(executable))
    if 'tree_requirements' in expected:
        lazy=folder/'capture-lazy-probe.exe'
        argv=[str(binary/'cl.exe'),*common,'/Fo'+str(objects)+'\\','/Fe'+str(lazy),str(g.ROOT/'source/platform/windows/ui/window_capture.cpp'),
              str(g.ROOT/'tests/frontend/window_capture_import_probe.cpp'),'kernel32.lib','/link','/DYNAMICBASE','/NXCOMPAT','/guard:cf']
        rows=[];report['lazy_import_control']=dict(commands=rows)
        for label,args,timeout in [('compile',argv,120),('imports',[str(binary/'dumpbin.exe'),'/imports',str(lazy)],30),('run',[str(lazy)],3)]:
            value=executor(argv=args,cwd=work,payload=b'',timeout=timeout,output_limit=65536)
            rows.append(dict(label=label,call_index=executor.calls,outcome=value['outcome'],exit_code=value['exit_code'],raw={key:save('lazy-'+label+'.'+key,value[key]) for key in ('stdout','stderr')}))
            if value['outcome']!='exited' or value['exit_code']!=0:
                report.update(status='lazy_control_failed',diagnostic_tail=(value['stdout']+value['stderr'])[-16384:].decode(errors='replace'));raise RuntimeError('Lazy import control failed')
            if label=='imports':assert b'user32.dll' not in value['stdout'].lower() and b'gdi32.dll' not in value['stdout'].lower()
            if label=='run':assert value['stdout']==b'capture-lazy-startup-ok\r\n' and not value['stderr']
        report['lazy_import_control'].update(status='pass',artifact_sha256=sha(lazy),user32_gdi32_static_imports=False)
    pin=executor.worker.k.CreateFileW(str(executable),0x80000080,1,None,3,0x80,None)
    if pin==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
    original_factory=executor.new_job;original_builder=executor.payload_builder
    try:
        identity=executor.worker.file_identity(executable);report['image_file_identity']=identity
        challenge=os.urandom(16);rgb_expected=[oracle.expected_rgb(challenge,p) for p in (0,1)]
        nonce=int.from_bytes(os.urandom(8),'little')
        while not(nonce&0xffffffff) or not(nonce>>32):nonce=int.from_bytes(os.urandom(8),'little')
        report.update(challenge=challenge.hex(),nonce=str(nonce),expected_rgb_sha256=[hashlib.sha256(v).hexdigest() for v in rgb_expected])
        modes=[('normal',None),('blank_oracle_rejection','--blank'),('hung_paint_timeout','--hang'),('controller_handle_loss','--hang'),('invalid_mode','--invalid')]
        if 'tree_requirements' in expected:modes.append(('tree','--tree'))
        for label,mode in modes:
            correct,correct_row=query_job(g,executor.worker,report)
            wrong,wrong_row=query_job(g,executor.worker,report)
            guarded=GuardedJob(g,correct,correct_row);observer=None;fault={};stop=threading.Event();before_launch=getattr(executor.worker,'launch_index',0)
            executor.new_job=lambda:guarded
            request=dict(challenge=challenge.hex(),nonce=str(nonce),volume=identity['volume'],file_id=identity['identity'],desktop=executor.worker.desktop_name)
            transferred={}
            def transfer(process,job):
                assert job is guarded
                kernel=executor.worker.k
                current=g.W.bind(kernel,'GetCurrentProcess',T.HANDLE)()
                duplicate=g.W.bind(kernel,'DuplicateHandle',T.BOOL,T.HANDLE,T.HANDLE,T.HANDLE,C.POINTER(T.HANDLE),T.DWORD,T.BOOL,T.DWORD)
                for key,source in (('job_handle',correct),('wrong_job_handle',wrong)):
                    handle=T.HANDLE();g.W.require(duplicate(current,source.handle,process.process,C.byref(handle),4,False,0))
                    request[key]=str(handle.value)
                transferred.update(process_id=process.pid,access=4,inheritable=False,count=2,supervisor_exposed=False)
                return (json.dumps(request,separators=(',',':'))+'\n').encode()
            executor.payload_builder=transfer
            def remove_guard():
                try:
                    until=time.monotonic()+2.5
                    while not stop.is_set() and time.monotonic()<until:
                        if getattr(executor.worker,'launch_index',0)>before_launch and executor.child is not None:
                            path=executor.worker.raw_paths['stdout']
                            try:
                                with path.open('rb') as stream:body=stream.read(4097)
                            except FileNotFoundError:body=b''
                            assert len(body)<=4096
                            if body.endswith(b'\n'):
                                ready=json.loads(body);assert ready==dict(schema='org.disked.cooperative-capture-ready/1',pid=str(executor.child.pid),nonce=str(nonce),holding_job_query=True)
                                fault['ready']=ready;guarded.lose_controller_handle();return
                        time.sleep(.01)
                    fault['error']='Owned ready observation deadline'
                except BaseException:fault['error']=traceback.format_exc()[-4096:]
            try:
                if label=='controller_handle_loss':observer=threading.Thread(target=remove_guard);observer.start()
                argv=[str(executable)]+([] if mode is None else [mode])
                value=executor(argv=argv,cwd=work,payload=b'',timeout=3,output_limit=262144)
                payload=(json.dumps(request,separators=(',',':'))+'\n').encode()
                if observer:stop.set();observer.join(timeout=1);assert not observer.is_alive()
                row=dict(mode=label,outcome=value['outcome'],exit_code=value['exit_code'],call_index=executor.calls,
                    elapsed_seconds=value['elapsed_seconds'],stdout_sha256=hashlib.sha256(value['stdout']).hexdigest(),stdout_bytes=len(value['stdout']),
                    stderr=save(label+'.stderr',value['stderr']),request=save(label+'.request',payload),transfer=transferred,pixels_retained=False)
                report['modes'].append(row)
                assert value['terminal'] and executor.observations[-1]['temporary_files_removed']
                assert transferred['process_id']==executor.observations[-1]['process_id'] and executor.observations[-1]['launch']['pre_resume_hook_completed']
                if label in ('normal','blank_oracle_rejection','tree'):
                    assert value['outcome']=='exited' and value['exit_code']==0 and not value['stderr']
                    frame,pixels=verifier.parse_frame(value['stdout'],process_id=executor.observations[-1]['process_id'],nonce=nonce,actor_sid=executor.worker.user_sid,tree=label=='tree')
                    row['frame']=frame
                    known=all(oracle.rgb_pixels(v) in (*rgb_expected,bytes(69120)) for v in pixels)
                    if known:row['stdout']=save(label+'.stdout',value['stdout']);row['pixels_retained']=True
                    if label in ('normal','tree'):
                        observed=verifier.verify_pixels(pixels,rgb_expected)
                        row['rgb_sha256']=[hashlib.sha256(v).hexdigest() for v in observed]
                        for i,rgb in enumerate(observed):save(('tree-' if label=='tree' else '')+'phase-'+str(i)+'.png',oracle.png(rgb))
                        try:verifier.verify_pixels([pixels[0],pixels[0]],rgb_expected)
                        except ValueError as error:assert str(error)=='pixel_origin';row['stale_phase_rejected']=True
                        else:raise ValueError('Stale pixels accepted')
                    else:
                        assert all(v==bytes(92160) for v in pixels)
                        try:verifier.verify_pixels(pixels,rgb_expected)
                        except ValueError as error:assert str(error)=='pixel_origin';row['blank_surface_rejected']=True
                        else:raise ValueError('Blank pixels accepted')
                elif label in ('hung_paint_timeout','controller_handle_loss'):
                    ready=json.loads(value['stdout']);assert ready==dict(schema='org.disked.cooperative-capture-ready/1',pid=str(executor.observations[-1]['process_id']),nonce=str(nonce),holding_job_query=True)
                    row['ready']=ready;assert not value['stderr']
                    if label=='hung_paint_timeout':assert value['outcome']=='timeout'
                    else:assert value['outcome']=='exited' and guarded.fault_closed and 'error' not in fault;row['controller_handle_loss']=fault
                else:assert value['outcome']=='exited' and value['exit_code']==2 and not value['stdout'] and value['stderr']==b'invalid_control_mode\r\n'
                assert sha(executable)==report['artifact']['sha256'] and executor.worker.file_identity(executable)==identity
            finally:
                stop.set()
                if observer:observer.join(timeout=1)
                executor.new_job=original_factory
                executor.payload_builder=original_builder
                if executor.active_job is not guarded and guarded.handle:guarded.close()
                wrong_row['retirement']=g.retire_job(wrong)
            assert executor.active_job is None and not guarded.handle and not correct.handle and not wrong.handle
            row['owned_job_handles_closed']=True
        assert [v['mode'] for v in report['modes']]==expected['control_modes']
        report['status']='pass';report['source_unchanged']=all(sha(g.ROOT/name)==value for name,value in report['sources'].items())
        assert report['source_unchanged']
    except BaseException:report.update(status='fail',error=traceback.format_exc()[-16384:]);raise
    finally:
        executor.new_job=original_factory
        executor.payload_builder=original_builder
        try:executor.close()
        except BaseException:
            report['image_pin_held_after_unknown_retirement']=True;raise
        else:executor.worker.k.CloseHandle(pin)
        report['port_observations']=executor.observations
        if all(row['terminal'] and row['temporary_files_removed'] for row in executor.observations):
            save('control.json',(json.dumps(report,indent=2)+'\n').encode())
            inventory=[]
            archive=work/'retained.tar.xz'
            with archive.open('xb') as raw:
                with lzma.LZMAFile(raw,'w',filters=[dict(id=lzma.FILTER_LZMA2,dict_size=1048576,preset=6)]) as compressed:
                    with tarfile.open(fileobj=compressed,mode='w|') as stream:
                        for path in sorted(artifacts.iterdir()):
                            assert path.is_file() and not path.is_symlink() and path.stat().st_nlink==1
                            inventory.append(dict(path=path.name,bytes=path.stat().st_size,sha256=sha(path)));stream.add(path,arcname=path.name,recursive=False)
            assert archive.stat().st_size<=1048576
            with tarfile.open(archive,'r:xz') as stream:
                members=stream.getmembers();assert [v.name for v in members]==[v['path'] for v in inventory]
                for member,row in zip(members,inventory):assert member.isfile() and hashlib.sha256(stream.extractfile(member).read(262145)).hexdigest()==row['sha256']
            shutil.copyfile(archive,g.ROOT/'retained.tar.xz');result['archive_sha256']=sha(archive)
            report['archive']=dict(bytes=archive.stat().st_size,sha256=sha(archive),entries=inventory)


def coordinate(g):
    port=g.load('cooperative_native_port',g.ROOT/'native-port.py')
    port.coordinate(g,extension=lambda work,environment,executor,result:exercise(g,work,environment,executor,result))
