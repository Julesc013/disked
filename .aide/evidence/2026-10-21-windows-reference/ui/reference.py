"""Trusted guest reference role, distinct from the restricted product worker.

Only the fresh owned actor gets temporary administrator membership. This role
can administer the guest; it is not claimed write-confined by its token. Owned
profile/media/output paths remain on the cap, and all processes enter jobs.
"""
import ctypes as C
from ctypes import wintypes as T
import json
import os
from pathlib import Path
import re
import subprocess

P=C.c_void_p
class Member(C.Structure):_fields_=[('sid',P)]

class Reference:
    def __init__(self,g,worker,observer,report):
        assert os.name=='nt' and os.environ['COMPUTERNAME']=='BLACKGLASS-HYPE'
        assert g.ROOT==Path('C:/ProgramData/DiskEd/qualification')
        assert re.fullmatch('DiskEdTest-[a-f0-9]{8}',worker.username)
        assert worker.user_sid!=worker.coordinator_sid and worker.work.drive.upper()=='R:'
        self.g,self.w,self.observer,self.report=g,worker,observer,report
        self.a,self.k=worker.a,worker.k;self.n=C.WinDLL('netapi32',use_last_error=True)
        self.token=T.HANDLE();self.actor=P();self.admin=P();self.added=False;self.quiescent=True;self.labels=set()
        self.journal=g.ROOT/'scratch/ordinary-actor.json';self.launches=[]
        b=g.W.bind
        b(self.n,'NetLocalGroupAddMembers',T.DWORD,T.LPCWSTR,T.LPCWSTR,T.DWORD,P,T.DWORD)
        b(self.n,'NetLocalGroupDelMembers',T.DWORD,T.LPCWSTR,T.LPCWSTR,T.DWORD,P,T.DWORD)
        b(self.n,'NetLocalGroupGetMembers',T.DWORD,T.LPCWSTR,T.LPCWSTR,T.DWORD,C.POINTER(P),T.DWORD,C.POINTER(T.DWORD),C.POINTER(T.DWORD),C.POINTER(C.c_size_t))
        b(self.n,'NetApiBufferFree',T.DWORD,P)
        b(self.a,'LookupAccountSidW',T.BOOL,T.LPCWSTR,P,T.LPWSTR,C.POINTER(T.DWORD),T.LPWSTR,C.POINTER(T.DWORD),C.POINTER(T.DWORD))
        b(self.a,'EqualSid',T.BOOL,P,P)
        b(self.a,'DuplicateToken',T.BOOL,T.HANDLE,C.c_int,C.POINTER(T.HANDLE))
        b(self.a,'CheckTokenMembership',T.BOOL,T.HANDLE,P,C.POINTER(T.BOOL))
        b(self.a,'IsTokenRestricted',T.BOOL,T.HANDLE)
        b(self.a,'CreateProcessWithTokenW',T.BOOL,T.HANDLE,T.DWORD,T.LPCWSTR,T.LPWSTR,T.DWORD,P,T.LPCWSTR,P,C.POINTER(g.W.ProcessInfo))
        b(self.k,'CreateFileW',T.HANDLE,T.LPCWSTR,T.DWORD,T.DWORD,C.POINTER(g.W.SecurityAttributes),T.DWORD,T.DWORD,T.HANDLE)
        b(self.k,'ResumeThread',T.DWORD,T.HANDLE);b(self.k,'TerminateProcess',T.BOOL,T.HANDLE,T.UINT)
        b(self.k,'WaitForSingleObject',T.DWORD,T.HANDLE,T.DWORD)
        b(self.k,'IsProcessInJob',T.BOOL,T.HANDLE,T.HANDLE,C.POINTER(T.BOOL))
        b(self.k,'GetExitCodeProcess',T.BOOL,T.HANDLE,C.POINTER(T.DWORD))
        b(self.k,'ProcessIdToSessionId',T.BOOL,T.DWORD,C.POINTER(T.DWORD))
        worker.require(self.a.ConvertStringSidToSidW(worker.user_sid,C.byref(self.actor)))
        worker.require(self.a.ConvertStringSidToSidW('S-1-5-32-544',C.byref(self.admin)))
        name=C.create_unicode_buffer(256);domain=C.create_unicode_buffer(256);size=T.DWORD(256);other=T.DWORD(256);kind=T.DWORD()
        worker.require(self.a.LookupAccountSidW(None,self.admin,name,C.byref(size),domain,C.byref(other),C.byref(kind)))
        self.group=name.value
        report.update(role='trusted administrative Windows UI reference',actor_sid=worker.user_sid,
            coordinator_sid=worker.coordinator_sid,token_write_confined=False,launches=self.launches,retired=False)

    def phase(self,phase):
        state=json.loads(self.journal.read_bytes())
        assert state['sid']==self.w.user_sid and state['name']==self.w.username
        state['administrative_reference']=dict(phase=phase,actor_sid=self.w.user_sid,group_sid='S-1-5-32-544')
        self.journal.write_text(json.dumps(state,indent=2)+'\n',encoding='utf-8',newline='\n')

    def member(self):
        buffer=P();read=T.DWORD();total=T.DWORD();resume=C.c_size_t()
        code=self.n.NetLocalGroupGetMembers(None,self.group,0,C.byref(buffer),32768,C.byref(read),C.byref(total),C.byref(resume))
        try:
            if code:raise C.WinError(code)
            if read.value!=total.value or read.value>256:raise ValueError('Bounded complete reference-group observation required')
            if not read.value:return False
            return any(self.a.EqualSid(row.sid,self.actor) for row in C.cast(buffer,C.POINTER(Member*read.value)).contents)
        finally:
            if buffer:self.n.NetApiBufferFree(buffer)

    def administrator(self,token):
        duplicate=T.HANDLE();self.w.require(self.a.DuplicateToken(token,1,C.byref(duplicate)))
        try:
            present=T.BOOL();self.w.require(self.a.CheckTokenMembership(duplicate,self.admin,C.byref(present)));return bool(present.value)
        finally:self.k.CloseHandle(duplicate)

    def identity(self,token):
        result=dict(sid=self.w.identity(token),administrator=self.administrator(token),restricted=bool(self.a.IsTokenRestricted(token)))
        for name,kind in [('elevated',20),('appcontainer',29),('session',12)]:
            value=T.DWORD();size=T.DWORD();self.w.require(self.a.GetTokenInformation(token,kind,C.byref(value),C.sizeof(value),C.byref(size)))
            result[name]=value.value
        return result

    def start(self,secret):
        if self.member() or self.administrator(self.w.original):raise ValueError('Fresh ordinary actor required; no membership adoption')
        self.phase('preparing');member=Member(self.actor)
        code=self.n.NetLocalGroupAddMembers(None,self.group,0,C.byref(member),1)
        if code:raise C.WinError(code)
        self.added=True;self.phase('active');assert self.member()
        self.w.require(self.a.LogonUserW(self.w.username,'.',secret,2,0,C.byref(self.token)))
        actual=self.identity(self.token);self.report['token']=actual
        assert actual['sid']==self.w.user_sid and actual['administrator'] and not actual['restricted'] and not actual['appcontainer']
        return self

    def launch(self,argv,environment,job,label):
        assert self.token and self.added and label not in self.labels
        assert re.fullmatch(r'(role-uia|(?:mbr-valid|gpt-valid|gpt-primary-damaged|gpt-conflicting)-(?:mmc|uia))',label)
        mmc=Path(os.environ['WINDIR'])/'System32/mmc.exe';msc=mmc.with_name('diskmgmt.msc')
        assert argv==[str(mmc),str(msc)] or Path(argv[0])==self.observer and len(argv) in (2,4)
        self.labels.add(label);w=self.w;handles=[];process=self.g.W.ProcessInfo()
        paths={key:w.work/(label+'.'+key) for key in ('stdin','stdout','stderr')}
        row=dict(label=label,argv=argv,role='trusted administrative reference',desktop=w.desktop_name,paths={k:str(v) for k,v in paths.items()})
        self.launches.append(row)
        try:
            paths['stdin'].write_bytes(b'');sa=self.g.W.SecurityAttributes(C.sizeof(self.g.W.SecurityAttributes),None,True)
            for stream in paths:
                handle=self.k.CreateFileW(str(paths[stream]),0x80000080 if stream=='stdin' else 0x40000080,3,C.byref(sa),3 if stream=='stdin' else 1,0x80,None)
                if handle in (None,C.c_void_p(-1).value):raise C.WinError(C.get_last_error())
                handles.append(handle)
            startup=self.g.W.StartupInfo();startup.cb=C.sizeof(startup);startup.desktop=w.desktop_name;startup.flags=0x100
            startup.stdin,startup.stdout,startup.stderr=handles
            env={key:str(value) for key,value in environment.items() if not key.startswith('DISKED_TEST_ACTOR_')}
            env.update(USERNAME=w.username,USERPROFILE=str(w.work/'profile'),HOME=str(w.work/'profile'),
                LOCALAPPDATA=str(w.work/'profile/AppData/Local'),APPDATA=str(w.work/'profile/AppData/Roaming'),
                TEMP=str(w.work/'temp'),TMP=str(w.work/'temp'),TMPDIR=str(w.work/'temp'),
                PROGRAMDATA=str(w.work/'common'),ALLUSERSPROFILE=str(w.work/'common'),PUBLIC=str(w.work/'public'),
                HOMEDRIVE=w.work.drive,HOMEPATH=str(w.work/'profile')[len(w.work.drive):])
            block=C.create_unicode_buffer('\0'.join(key+'='+value for key,value in sorted(env.items(),key=lambda pair:pair[0].upper()))+'\0\0')
            line=subprocess.list2cmdline(argv);assert len(line)<1024 and '\0' not in line
            w.require(self.a.CreateProcessWithTokenW(self.token,0,argv[0],C.create_unicode_buffer(line),0x08000404,block,str(w.work),C.byref(startup),C.byref(process)))
            row['created_pid']=process.pid
            def job_state():
                any_job,specific,exit_code=T.BOOL(),T.BOOL(),T.DWORD()
                w.require(self.k.IsProcessInJob(process.process,None,C.byref(any_job)))
                w.require(self.k.IsProcessInJob(process.process,job.handle,C.byref(specific)))
                w.require(self.k.GetExitCodeProcess(process.process,C.byref(exit_code)))
                query=self.g.W.bind(job.api,'QueryInformationJobObject',T.BOOL,T.HANDLE,C.c_int,P,T.DWORD,P)
                limits=job.limit_info_type();w.require(query(job.handle,9,C.byref(limits),C.sizeof(limits),None))
                ui=T.DWORD();w.require(query(job.handle,4,C.byref(ui),C.sizeof(ui),None))
                return dict(in_any_job=bool(any_job.value),in_owned_job=bool(specific.value),exit_code=exit_code.value,
                    flags=hex(limits.basic.flags),process_limit=limits.basic.active,memory_limit=limits.job_memory,
                    peak_job_memory=limits.peak_job,ui_limits=ui.value)
            row['job_before_assignment']=job_state()
            if not row['job_before_assignment']['in_owned_job']:
                if not job.api.AssignProcessToJobObject(job.handle,process.process):
                    error=C.get_last_error();row['assignment_error']=error;row['job_after_assignment_error']=job_state();raise C.WinError(error)
            row['job_after_assignment']=job_state()
            assert row['job_after_assignment']['in_owned_job']
            self.quiescent=False
            token=T.HANDLE();w.require(self.a.OpenProcessToken(process.process,0xe,C.byref(token)))
            try:actual=self.identity(token)
            finally:self.k.CloseHandle(token)
            session=T.DWORD();w.require(self.k.ProcessIdToSessionId(process.pid,C.byref(session)))
            assert actual['sid']==w.user_sid and actual['administrator'] and not actual['restricted'] and not actual['appcontainer'] and session.value==3
            row.update(pid=process.pid,token=actual,actual_session=session.value,job_assigned_before_resume=True)
            if self.k.ResumeThread(process.thread)==0xffffffff:raise C.WinError(C.get_last_error())
            child=self.g.W.Child(self.k,process.process,process.pid);process.process=None;return child,row
        finally:
            if process.process:
                self.k.TerminateProcess(process.process,78);self.k.WaitForSingleObject(process.process,10000);self.k.CloseHandle(process.process)
            if process.thread:self.k.CloseHandle(process.thread)
            for handle in handles:self.k.CloseHandle(handle)

    def close(self):
        if not self.quiescent:raise RuntimeError('Preserve reference role until its owned jobs retire')
        if self.token:self.k.CloseHandle(self.token);self.token=T.HANDLE()
        try:
            if self.added:
                code=self.n.NetLocalGroupDelMembers(None,self.group,0,C.byref(Member(self.actor)),1)
                if code:raise C.WinError(code)
                assert not self.member();self.added=False
            self.phase('retired');self.report['retired']=True
        finally:
            for name in ('actor','admin'):
                if getattr(self,name):self.k.LocalFree(getattr(self,name));setattr(self,name,P())
