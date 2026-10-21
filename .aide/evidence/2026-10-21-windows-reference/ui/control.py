"""Four actual read-only Disk Management observations on owned guest media."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import json
import lzma
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess
import tarfile
import time
import traceback
import winreg

FILES=('source/runtime/command/json.cpp','source/runtime/command/json.h',
       'tests/differential/windows_ui_probe.cpp','tests/corpus/windows_partitions.py')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def service(g,name):
    a=C.WinDLL('advapi32',use_last_error=True);bind=g.W.bind
    bind(a,'OpenSCManagerW',T.HANDLE,T.LPCWSTR,T.LPCWSTR,T.DWORD)
    bind(a,'OpenServiceW',T.HANDLE,T.HANDLE,T.LPCWSTR,T.DWORD)
    bind(a,'QueryServiceStatusEx',T.BOOL,T.HANDLE,C.c_int,C.c_void_p,T.DWORD,C.POINTER(T.DWORD))
    bind(a,'CloseServiceHandle',T.BOOL,T.HANDLE)
    manager=a.OpenSCManagerW(None,None,1);g.W.require(manager)
    handle=None
    try:
        handle=a.OpenServiceW(manager,name,4)
        if not handle:return dict(name=name,winerror=C.get_last_error(),status=None)
        values=(T.DWORD*9)();size=T.DWORD();g.W.require(a.QueryServiceStatusEx(handle,0,values,C.sizeof(values),C.byref(size)))
        return dict(name=name,winerror=0,type=values[0],state=values[1],controls=values[2],service_exit=values[3],pid=values[7])
    finally:
        if handle:a.CloseServiceHandle(handle)
        a.CloseServiceHandle(manager)

def collect(g,work,environment,executor,result,profile,private):
    report=result['windows_ui'];expected=json.loads((g.ROOT/'expected.json').read_bytes())['windows_reference']
    result['all_owned_reference_jobs_retired']=True;result['all_owned_media_retired']=True
    directory=work/'ui-observations';directory.mkdir()
    def artifact(name,body):
        path=directory/name;assert path.is_relative_to(directory) and '..' not in Path(name).parts and len(body)<=2097152
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as stream:stream.write(body)
        return dict(path=name,bytes=len(body),sha256=sha(path))
    report['output_root']=str(directory)
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion') as key:
        report['windows_registry']={name:winreg.QueryValueEx(key,name)[0] for name in ('CurrentBuildNumber','UBR','EditionID','BuildLabEx')}
    report['environment']=dict(platform=platform.version(),architecture=platform.machine(),python=platform.python_version(),
        station=executor.worker.ui_host,desktop=executor.worker.desktop_name,reference_profile=str(work/'profile'))
    assert report['windows_registry']['CurrentBuildNumber']=='19045' and report['windows_registry']['UBR']==7548
    report['components']={}
    for item in expected['components']:
        path=Path(item['path']);assert path.is_file() and path.stat().st_size==item['bytes'] and sha(path)==item['sha256']
        report['components'][item['name']]=dict(item)
    report['service_before']=service(g,'vds')
    binary=Path(environment['PATH'].split(os.pathsep)[0]);observer=work/'windows-ui-probe.exe'
    args=['/nologo','/W4','/WX','/MT','/O2','/GS','/sdl','/guard:cf','/std:c++14','/EHsc','/permissive-',
        '/utf-8','/D_WIN32_WINNT=0x0A00','/I'+str(g.ROOT/'source'),'/Fo'+str(work/'obj')+'\\','/Fe'+str(observer),
        str(g.ROOT/'tests/differential/windows_ui_probe.cpp'),str(g.ROOT/'source/runtime/command/json.cpp'),
        'kernel32.lib','user32.lib','advapi32.lib','ole32.lib','oleaut32.lib','uiautomationcore.lib','uuid.lib','userenv.lib','shell32.lib',
        '/link','/DYNAMICBASE','/NXCOMPAT','/guard:cf']
    response=work/'ui-compile.rsp';response.write_text(subprocess.list2cmdline(args),encoding='utf-8')
    value=executor(argv=[str(binary/'cl.exe'),'@'+str(response)],cwd=work,payload=b'',timeout=60,output_limit=131072)
    report['compilation']=dict(arguments=args,outcome=value['outcome'],exit_code=value['exit_code'],
        stdout=artifact('compile.stdout',value['stdout']),stderr=artifact('compile.stderr',value['stderr']))
    assert value['outcome']=='exited' and value['exit_code']==0
    report['observer']=dict(path=str(observer),bytes=observer.stat().st_size,sha256=sha(observer))
    assert executor.calls==10
    module=g.load('windows_administrative_reference',g.ROOT/'windows-reference-role.py')
    media_module=g.load('windows_ui_media',g.ROOT/'windows-reference-media.py')
    recipes=g.load('windows_ui_recipes',g.ROOT/'tests/corpus/windows_partitions.py')
    assert [recipes.describe(name) for name in recipes.CASES]==expected['fixtures']['cases']
    role=None;job=None;children=[];media=None;job_index=0
    def new_job():
        nonlocal job,job_index
        assert job is None
        job=g.S.WindowsJob(memory_bytes=268435456,process_limit=8);job_index+=1
        result['all_owned_reference_jobs_retired']=False
        return job
    def retire():
        nonlocal job,children
        if job:
            observation=g.retire_job(job);job=None
            assert observation['active_processes']==0
            report['retirements'].append(observation)
        for child in children:child.close()
        children=[];result['all_owned_reference_jobs_retired']=True
        if role:role.quiescent=True
    def wait(child,launch,timeout):
        start=time.monotonic();outcome='exited'
        while child.poll() is None:
            total=0
            for stream in ('stdout','stderr'):
                path=Path(launch['paths'][stream]);info=path.lstat()
                assert info.st_nlink==1 and not info.st_file_attributes&0x400
                total+=info.st_size
            if total>1048576:outcome='output_limit';break
            if time.monotonic()-start>timeout:outcome='timeout';break
            time.sleep(.05)
        launch.update(outcome=outcome,exit_code=child.poll(),seconds=time.monotonic()-start)
        return outcome
    def read(launch,name):
        data={}
        for stream in ('stdout','stderr'):
            path=Path(launch['paths'][stream]);info=path.lstat()
            assert info.st_nlink==1 and not info.st_file_attributes&0x400 and info.st_size<=1048576
            body=path.read_bytes();data[stream]=body;launch[stream]=artifact(name+'.'+stream,body)
        return data
    try:
        role=module.Reference(g,executor.worker,observer,report['reference_role']);role.start(private['DISKED_TEST_ACTOR_PASS'])
        child,launch=role.launch([str(observer),'--identity'],environment,new_job(),'role-uia');children.append(child)
        outcome=wait(child,launch,15);retire();raw=read(launch,'role')
        assert outcome=='exited' and launch['exit_code']==0 and not raw['stderr']
        observed=json.loads(raw['stdout']);report['role_observation']=observed
        identity=observed['identity'];assert observed['uia_hresult']==0
        assert identity['sid']==executor.worker.user_sid and identity['administrator'] and not identity['restricted'] and not identity['appcontainer']
        assert identity['session']==3 and identity['station']=='WinSta0' and identity['desktop']==executor.worker.desktop_name.split('\\',1)[1]
        assert Path(identity['profile'])==work/'profile' and Path(identity['temp']).is_relative_to(work)
        assert all(Path(identity[name]).is_relative_to(work/'profile') for name in ('local','roaming'))
        report['administrative_mmc_role_verified']=True
        media_root=g.fresh(work/'ui-media')
        for fact in expected['fixtures']['cases']:
            name=fact['name'];row=dict(fixture=fact,participant='disk-management-ui',kind='partition-presentation',media={},ui={});report['cases'].append(row)
            media=media_module.Media(g,media_root,name,recipes.generate(name),fact['sha256'],expected['sdk_abi'],row['media'])
            result['all_owned_media_retired']=False
            try:
                media.start();physical=row['media']['physical_path'];disk_number=int(re.search(r'([0-9]+)$',physical)[1])
                row['binding']=dict(attachment_uuid=str(media.identifier),nonce=media.nonce,physical_path=physical,display_locator='Disk '+str(disk_number),authority='Held verified virtual-disk object and immutable fixture bytes;display number is only a current UI locator')
                case_job=new_job()
                mmc=Path(os.environ['WINDIR'])/'System32/mmc.exe'
                child,mmc_launch=role.launch([str(mmc),str(mmc.with_name('diskmgmt.msc'))],environment,case_job,name+'-mmc');children.append(child)
                report['mmc_started']=True;profile['mmc_started']=True
                mmc_launch['leader_exit_before_observer_launch']=child.poll()
                observer_child,ui_launch=role.launch([str(observer),str(child.pid),media.nonce,'Disk '+str(disk_number)],environment,case_job,name+'-uia');children.append(observer_child)
                outcome=wait(observer_child,ui_launch,35);mmc_launch['leader_exit_before_retirement']=child.poll()
                retire();row['ui']['observer_execution']=ui_launch;row['ui']['mmc_execution']=mmc_launch
                raw=read(ui_launch,'cases/'+name+'.uia');read(mmc_launch,'cases/'+name+'.mmc')
                assert outcome=='exited' and ui_launch['exit_code']==0 and not raw['stderr']
                actual=json.loads(raw['stdout'])
                assert actual['identity']=={**identity,'pid':actual['identity']['pid']} and actual['uia_hresult']==0
                view=actual['capture'];assert view['mmc_pid']==mmc_launch['pid'] and view['nonce']==media.nonce
                assert view['target_label']==row['binding']['display_locator']
                # This proves collection/readiness, not agreement with Windows or
                # the fixture's metadata interpretation. Keep that judgement separate.
                assert view['target_label_seen'] and view['stable_snapshots']>=2 and not view['truncated'] and view['nodes']
                row['ui']['capture_summary']=dict(identity=actual['identity'],mmc_pid=view['mmc_pid'],nonce=view['nonce'],
                    target_label=view['target_label'],target_label_seen=True,stable_snapshots=view['stable_snapshots'],
                    truncated=False,nodes=len(view['nodes']),frames=view['frames'])
                row['ui']['status']='captured_pending_semantic_review'
                report['actual_observation_tuples'].append(dict(name=name,participant='disk-management-ui',kind='partition-presentation'))
            finally:
                if job:retire()
                media.quiescent=result['all_owned_reference_jobs_retired'];media.close();media=None
                result['all_owned_media_retired']=True
        assert len(report['actual_observation_tuples'])==4 and job_index==5
        report.update(status='captured_pending_semantic_review',ui_observations=4,reference_jobs=job_index)
    finally:
        if job:retire()
        if media:
            media.quiescent=result['all_owned_reference_jobs_retired'];media.close();result['all_owned_media_retired']=True
        if role:role.close()
        report['service_after']=service(g,'vds')
        report['observer_unchanged']=observer.is_file() and sha(observer)==report['observer']['sha256']
        assert report['observer_unchanged']
        for item in expected['components']:assert sha(Path(item['path']))==item['sha256']

def retain(g,work,result):
    report=result['windows_ui'];directory=work/'ui-observations'
    if not directory.exists():return
    (directory/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    entries=[]
    for path in sorted(directory.rglob('*')):
        if path.is_file():
            assert path.stat().st_nlink==1 and not path.is_symlink() and path.stat().st_size<=2097152
            entries.append(dict(path=path.relative_to(directory).as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
    assert len(entries)<=128 and sum(row['bytes'] for row in entries)<=8388608
    archive=work/'retained.tar.xz'
    with archive.open('xb') as stream:
        with lzma.LZMAFile(stream,'w',filters=[dict(id=lzma.FILTER_LZMA2,dict_size=1048576,preset=6)]) as compressed:
            with tarfile.open(fileobj=compressed,mode='w|') as output:
                for row in entries:output.add(directory/row['path'],arcname=row['path'],recursive=False)
    assert archive.stat().st_size<=1048576
    with tarfile.open(archive,'r:xz') as stream:
        members=stream.getmembers();assert [v.name for v in members]==[v['path'] for v in entries]
        for member,row in zip(members,entries):
            assert member.isfile() and member.size==row['bytes'] and hashlib.sha256(stream.extractfile(member).read()).hexdigest()==row['sha256']
    shutil.copyfile(archive,g.ROOT/'retained.tar.xz');result['archive_sha256']=sha(archive)
    report['archive']=dict(bytes=archive.stat().st_size,sha256=result['archive_sha256'],entries=entries)

def coordinate(g):
    private={key:value for key,value in os.environ.items() if key.startswith('DISKED_TEST_ACTOR_')}
    port=g.load('windows_ui_port',g.ROOT/'native-port.py');profile=g.load('windows_ui_profile',g.ROOT/'ui-profile.py')
    def extension(work,environment,executor,result):
        result.update(all_owned_reference_jobs_retired=True,all_owned_media_retired=True)
        result['windows_ui']=dict(status='running',cases=[],retirements=[],reference_role={},actual_observation_tuples=[],ui_observations=0,mmc_started=False,campaign_complete=False)
        try:profile.exercise(g,work,environment,executor,result,reference=lambda *args:collect(*args,private))
        except BaseException:
            result['windows_ui'].update(status='fail',error=traceback.format_exc()[-16384:]);raise
        finally:retain(g,work,result)
    try:port.coordinate(g,extension=extension)
    finally:
        private.clear();path=g.ROOT/'proof-result.json'
        if path.exists():
            value=json.loads(path.read_bytes());report=value.get('windows_ui',{})
            value.update(scope=__doc__,all_owned_processes_retired=bool(value.get('all_owned_processes_retired')) and bool(value.get('all_owned_reference_jobs_retired',True)),
                         reference_tools_run=bool(report.get('mmc_started')),ui_observations=len(report.get('actual_observation_tuples',[])),campaign_complete=False)
            path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
