"""Guest-only disposable profile proof, before admitting any MMC process.

This is trusted administrative fixture setup. The probe remains the existing
ordinary restricted worker; it does not qualify an administrative UI reference.
"""
import contextlib
import ctypes as C
from ctypes import wintypes as T
import json
import os
from pathlib import Path
import shutil
import traceback
import uuid
import winreg

FILES=()
DEFAULT=Path('C:/Users/Default')

class ProfileInfo(C.Structure):
    _fields_=[('size',T.DWORD),('flags',T.DWORD),('username',T.LPWSTR),
              ('profile_path',T.LPWSTR),('default_path',T.LPWSTR),
              ('server',T.LPWSTR),('policy',T.LPWSTR),('profile',T.HANDLE)]

class Luid(C.Structure):
    _fields_=[('low',T.DWORD),('high',T.LONG)]

class Privileges(C.Structure):
    _fields_=[('count',T.DWORD),('luid',Luid),('attributes',T.DWORD)]

@contextlib.contextmanager
def privilege(worker,name):
    a,k,bind=worker.a,worker.k,worker.bind
    bind(a,'OpenProcessToken',T.BOOL,T.HANDLE,T.DWORD,C.POINTER(T.HANDLE))
    bind(a,'LookupPrivilegeValueW',T.BOOL,T.LPCWSTR,T.LPCWSTR,C.POINTER(Luid))
    bind(a,'AdjustTokenPrivileges',T.BOOL,T.HANDLE,T.BOOL,C.POINTER(Privileges),T.DWORD,C.POINTER(Privileges),C.POINTER(T.DWORD))
    bind(k,'GetCurrentProcess',T.HANDLE)
    token=T.HANDLE();previous=Privileges();changed=False
    worker.require(a.OpenProcessToken(k.GetCurrentProcess(),0x28,C.byref(token)))
    try:
        wanted=Privileges();wanted.count=1;wanted.attributes=2
        worker.require(a.LookupPrivilegeValueW(None,name,C.byref(wanted.luid)))
        size=T.DWORD();C.set_last_error(0)
        worker.require(a.AdjustTokenPrivileges(token,False,C.byref(wanted),C.sizeof(previous),C.byref(previous),C.byref(size)))
        if C.get_last_error()==1300:raise RuntimeError('Required existing guest privilege unavailable: '+name)
        changed=True;yield
    finally:
        if changed:worker.require(a.AdjustTokenPrivileges(token,False,C.byref(previous),0,None,None))
        k.CloseHandle(token)

def key_exists(root,path):
    try:
        with winreg.OpenKey(root,path):return True
    except FileNotFoundError:return False

def copy_default(target):
    """Copy regular default-profile content once; never follow compatibility links."""
    pending=[(DEFAULT,target)]
    count=total=skipped=0
    while pending:
        parent,destination=pending.pop()
        with os.scandir(parent) as entries:
            for entry in entries:
                count+=1
                if count>512:raise ValueError('Default-profile entry bound')
                # Windows DirEntry's cached stat omits the link count. Query
                # the path itself rather than weakening the single-link check.
                path=Path(entry.path);info=path.lstat();out=destination/entry.name
                if info.st_file_attributes&0x400:skipped+=1;continue
                if entry.is_dir(follow_symlinks=False):out.mkdir();pending.append((path,out))
                elif entry.is_file(follow_symlinks=False) and info.st_nlink==1:
                    total+=info.st_size
                    if total>8388608:raise ValueError('Default-profile byte bound')
                    shutil.copyfile(path,out)
                else:raise ValueError('Unexpected default-profile entry')
    return dict(entries=count,bytes=total,skipped_links=skipped)

def exercise(g,work,environment,executor,result):
    worker=executor.worker;expected=json.loads((g.ROOT/'expected.json').read_bytes())['windows_reference']
    assert expected['mode']=='--windows-ui-profile' and work.drive.upper()=='R:'
    assert os.environ['COMPUTERNAME']=='BLACKGLASS-HYPE' and worker.username.startswith('DiskEdTest-')
    profile=worker.work/'profile';g.W.plain_directory(profile)
    assert not list(profile.iterdir())
    sid=worker.user_sid;key_path=r'SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList'+'\\'+sid
    assert not key_exists(winreg.HKEY_LOCAL_MACHINE,key_path) and not key_exists(winreg.HKEY_USERS,sid)
    report=dict(status='running',actor_sid=sid,path=str(profile),profile_key=key_path,
                desktop=worker.desktop_name,mmc_started=False,ui_reference_qualified=False,
                loaded=False,unloaded=False,profile_removed=False,key_removed=False)
    result['ui_profile']=report;result['all_owned_profiles_retired']=False
    journal=g.ROOT/'scratch/ordinary-actor.json'
    def phase(value):
        state=json.loads(journal.read_bytes())
        assert state['sid']==sid and state['name']==worker.username
        state['ui_profile']=dict(phase=value,path=str(profile),key=key_path,sid=sid)
        journal.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8',newline='\n')
    phase('preparing')
    u=C.WinDLL('userenv',use_last_error=True)
    g.W.bind(u,'LoadUserProfileW',T.BOOL,T.HANDLE,C.POINTER(ProfileInfo))
    g.W.bind(u,'UnloadUserProfile',T.BOOL,T.HANDLE,T.HANDLE)
    g.W.bind(u,'GetUserProfileDirectoryW',T.BOOL,T.HANDLE,T.LPWSTR,C.POINTER(T.DWORD))
    g.W.bind(u,'DeleteProfileW',T.BOOL,T.LPCWSTR,T.LPCWSTR,T.LPCWSTR)
    info=ProfileInfo();info.size=C.sizeof(info);info.flags=1;info.username=worker.username
    created=False
    try:
        report['default_copy']=copy_default(profile)
        with winreg.CreateKeyEx(winreg.HKEY_LOCAL_MACHINE,key_path,0,winreg.KEY_ALL_ACCESS) as key:
            created=True
            winreg.SetValueEx(key,'ProfileImagePath',0,winreg.REG_EXPAND_SZ,str(profile))
            for name in ('Flags','State','RefCount'):winreg.SetValueEx(key,name,0,winreg.REG_DWORD,0)
        with privilege(worker,'SeBackupPrivilege'),privilege(worker,'SeRestorePrivilege'):
            worker.require(u.LoadUserProfileW(worker.original,C.byref(info)))
        report['loaded']=True
        phase('loaded')
        path=C.create_unicode_buffer(32768);size=T.DWORD(len(path))
        worker.require(u.GetUserProfileDirectoryW(worker.original,path,C.byref(size)))
        report['resolved_profile']=path.value
        assert Path(path.value)==profile and key_exists(winreg.HKEY_USERS,sid)
        nonce=uuid.uuid4().hex
        command=[os.sys.executable,'-B',str(g.ROOT/'ui-profile-probe.py'),str(profile),sid,nonce]
        value=executor(argv=command,cwd=work,payload=b'',timeout=15,output_limit=65536)
        report['call']={k:v for k,v in value.items() if k not in ('stdout','stderr')}
        report['stdout']=value['stdout'].decode(errors='replace');report['stderr']=value['stderr'].decode(errors='replace')
        assert value['outcome']=='exited' and value['exit_code']==0 and not value['stderr']
        observed=json.loads(value['stdout']);report['probe']=observed
        assert observed['nonce']==nonce and observed['profile']==str(profile)
        assert all(Path(path).is_relative_to(profile) for path in observed['known_folders'].values())
        assert Path(observed['temp']).is_relative_to(work)
        with winreg.OpenKey(winreg.HKEY_USERS,sid+r'\Software\DiskEdProfileProof') as key:
            assert winreg.QueryValueEx(key,'nonce')[0]==nonce
        report['owned_hive_write_verified']=True
        assert executor.calls==9
        report['status']='pass'
    except BaseException:
        report.update(status='fail',error=traceback.format_exc()[-16384:]);raise
    finally:
        if executor.active_job is not None or executor.poisoned:
            raise RuntimeError('Preserve profile until owned worker retirement is proven')
        if report['loaded']:
            with privilege(worker,'SeBackupPrivilege'),privilege(worker,'SeRestorePrivilege'):
                worker.require(u.UnloadUserProfile(worker.original,info.profile))
            report['unloaded']=True
            phase('unloaded')
        if key_exists(winreg.HKEY_USERS,sid):raise RuntimeError('Owned profile hive still loaded')
        if created:
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,key_path) as key:
                assert Path(winreg.QueryValueEx(key,'ProfileImagePath')[0])==profile
            g.W.plain_directory(profile)
            worker.require(u.DeleteProfileW(sid,str(profile),None))
            report['profile_removed']=not profile.exists()
            report['key_removed']=not key_exists(winreg.HKEY_LOCAL_MACHINE,key_path)
            if not report['profile_removed'] or not report['key_removed']:raise RuntimeError('Owned profile cleanup incomplete')
        result['all_owned_profiles_retired']=True
        phase('retired')

def coordinate(g):
    port=g.load('ui_profile_port',g.ROOT/'native-port.py')
    try:port.coordinate(g,extension=lambda *args:exercise(g,*args))
    finally:
        path=g.ROOT/'proof-result.json'
        if path.exists():
            value=json.loads(path.read_bytes())
            value.update(scope=__doc__,all_owned_media_retired=True,reference_tools_run=False,ui_observations=0,campaign_complete=False)
            path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
