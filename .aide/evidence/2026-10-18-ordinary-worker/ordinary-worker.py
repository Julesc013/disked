"""Guest-only ordinary-token experiment. Does not create accounts or storage.

The caller owns the disposable principal, capped volume and containing job.
No actor profile is loaded. This prototype is not product runtime code.
"""
import ctypes as C
from ctypes import wintypes as T
import json
import os
from pathlib import Path
import re
import shutil
import socket
import subprocess
import uuid

P = C.c_void_p
ROOT = Path('C:/ProgramData/DiskEd/qualification')


class Worker:
    def __init__(self, base, work, control, username, password, expected_sid, *, namespace_compat=False, interactive_ui=False):
        if (os.name != 'nt' or socket.gethostname().casefold() != 'blackglass-hyperv' or
                Path(__file__).resolve().parent != ROOT or
                not re.fullmatch(r'DiskEdTest-[0-9a-f]{8}', username)):
            raise ValueError('Fixed guest and disposable actor identity required')
        self.base, self.bind, self.require = base, base.bind, base.require
        self.username = username
        self.interactive_ui = interactive_ui
        self.work, self.control = base.plain_directory(work), base.plain_directory(control)
        if set(p.name for p in self.work.iterdir()) != {'owner.json'}:
            raise ValueError('Fresh owned worker directory required')
        for folder in (self.work, self.control):
            marker = folder/'owner.json'
            if (marker.is_symlink() or marker.stat().st_size > 4096 or
                    json.loads(marker.read_bytes()).get('root') != str(ROOT)):
                raise ValueError('Worker/controller ownership mismatch')
        self.k, self.a, self.u = [C.WinDLL(n, use_last_error=True)
                                 for n in ('kernel32', 'advapi32', 'user32')]
        self.token, self.original, self.station, self.desktop = T.HANDLE(), T.HANDLE(), None, None
        self.bind(self.k, 'CloseHandle', T.BOOL, T.HANDLE)
        self.bind(self.k, 'LocalFree', P, P)
        self.bind(self.k, 'GetCurrentProcess', T.HANDLE)
        self.bind(self.a, 'GetUserNameW', T.BOOL, T.LPWSTR, C.POINTER(T.DWORD))
        self.bind(self.a, 'OpenProcessToken', T.BOOL, T.HANDLE, T.DWORD, C.POINTER(T.HANDLE))
        self.bind(self.a, 'GetTokenInformation', T.BOOL, T.HANDLE, C.c_int, P, T.DWORD, C.POINTER(T.DWORD))
        self.bind(self.a, 'ConvertSidToStringSidW', T.BOOL, P, C.POINTER(T.LPWSTR))
        self.bind(self.a, 'ConvertStringSidToSidW', T.BOOL, T.LPCWSTR, C.POINTER(P))
        self.bind(self.a, 'LogonUserW', T.BOOL, T.LPCWSTR, T.LPCWSTR, T.LPCWSTR,
                  T.DWORD, T.DWORD, C.POINTER(T.HANDLE))
        self.bind(self.a, 'CreateRestrictedToken', T.BOOL, T.HANDLE, T.DWORD, T.DWORD,
                  P, T.DWORD, P, T.DWORD, P, C.POINTER(T.HANDLE))
        self.bind(self.a, 'ConvertStringSecurityDescriptorToSecurityDescriptorW', T.BOOL,
                  T.LPCWSTR, T.DWORD, C.POINTER(P), P)
        self.bind(self.a, 'GetSecurityDescriptorDacl', T.BOOL, P, C.POINTER(T.BOOL),
                  C.POINTER(P), C.POINTER(T.BOOL))
        self.bind(self.a, 'SetNamedSecurityInfoW', T.DWORD, T.LPWSTR, C.c_int, T.DWORD, P, P, P, P)
        self.bind(self.u, 'GetProcessWindowStation', T.HANDLE)
        self.bind(self.u, 'CreateWindowStationW', T.HANDLE, T.LPCWSTR, T.DWORD,
                  T.DWORD, C.POINTER(base.SecurityAttributes))
        self.bind(self.u, 'SetProcessWindowStation', T.BOOL, T.HANDLE)
        self.bind(self.u, 'CloseWindowStation', T.BOOL, T.HANDLE)
        self.bind(self.u, 'CreateDesktopW', T.HANDLE, T.LPCWSTR, P, P, T.DWORD,
                  T.DWORD, C.POINTER(base.SecurityAttributes))
        self.bind(self.u, 'CloseDesktop', T.BOOL, T.HANDLE)
        name, length = C.create_unicode_buffer(256), T.DWORD(256)
        self.require(self.a.GetUserNameW(name, C.byref(length)))
        if name.value.casefold() != 'agents' or not C.windll.shell32.IsUserAnAdmin():
            raise PermissionError('Existing Agents guest administrator required')
        coordinator = T.HANDLE()
        try:
            self.require(self.a.OpenProcessToken(self.k.GetCurrentProcess(), 8, C.byref(coordinator)))
            self.coordinator_sid = self.identity(coordinator)
            self.coordinator_integrity_sid = self.identity(coordinator, kind=25)
            self.require(self.a.LogonUserW(username, '.', password, 2, 0, C.byref(self.original)))
            self.user_sid = self.identity(self.original)
            if self.user_sid != expected_sid or self.user_sid == self.coordinator_sid:
                raise ValueError('Actual logon SID differs from owned disposable actor')
            restricting,compatibility = P(),P()
            self.require(self.a.ConvertStringSidToSidW(self.user_sid, C.byref(restricting)))
            try:
                self.restricting_sids=[self.user_sid]
                if namespace_compat:
                    self.require(self.a.ConvertStringSidToSidW('S-1-5-12',C.byref(compatibility)))
                    self.restricting_sids.append('S-1-5-12')
                entries=(base.SidAttributes*len(self.restricting_sids))()
                entries[0]=base.SidAttributes(restricting,0)
                if namespace_compat:entries[1]=base.SidAttributes(compatibility,0)
                # Win10: DISABLE_MAX_PRIVILEGE | WRITE_RESTRICTED. No LUA or
                # SANDBOX_INERT flag. Full candidate v2 explicitly adds only
                # the Windows restricted-code compatibility SID; diagnostics
                # retain the original user-only candidate by default.
                self.require(self.a.CreateRestrictedToken(self.original, 9, 0, None,
                             0, None, len(entries), entries, C.byref(self.token)))
            finally:
                if compatibility:self.k.LocalFree(compatibility)
                self.k.LocalFree(restricting)
            for kind in (20, 29):  # TokenElevation, TokenIsAppContainer
                value, size = T.DWORD(), T.DWORD()
                self.require(self.a.GetTokenInformation(self.token, kind, C.byref(value),
                                                       C.sizeof(value), C.byref(size)))
                if value.value:
                    raise PermissionError('Actor must be nonelevated and non-AppContainer')
            if self.identity(self.token) != expected_sid:
                raise ValueError('Restricted token user identity changed')
            self.integrity_sid=self.identity(self.token,kind=25)
            if self.integrity_sid!='S-1-16-8192':
                raise ValueError('This ordinary worker profile requires medium integrity')
            self.apply_acl(self.work, 'D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;' + self.coordinator_sid +
                           ')(A;OICI;0x1301bf;;;' + self.user_sid + ')')
            for leaf in ('temp', 'profile', 'local', 'roaming', 'common', 'public'):
                (self.work/leaf).mkdir()
            self.native_temp = self.work/'temp'
            self.create_desktop()
        except BaseException:
            self.close()
            raise
        finally:
            if coordinator:
                self.k.CloseHandle(coordinator)

    def identity(self, token, *, kind=1):
        needed = T.DWORD()
        self.a.GetTokenInformation(token, kind, None, 0, C.byref(needed))
        if not 0 < needed.value <= 4096:
            raise ValueError('Invalid token user size')
        info = C.create_string_buffer(needed.value)
        self.require(self.a.GetTokenInformation(token, kind, info, needed, C.byref(needed)))
        sid = C.cast(info, C.POINTER(self.base.SidAttributes)).contents.sid
        text = T.LPWSTR()
        self.require(self.a.ConvertSidToStringSidW(sid, C.byref(text)))
        try:
            return text.value
        finally:
            self.k.LocalFree(C.cast(text, P))

    def descriptor(self, sddl):
        value = P()
        self.require(self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(
                     sddl, 1, C.byref(value), None))
        return value

    def apply_acl(self, path, sddl):
        self.base.plain_directory(path)
        descriptor = self.descriptor(sddl)
        try:
            acl, present, defaulted = P(), T.BOOL(), T.BOOL()
            self.require(self.a.GetSecurityDescriptorDacl(descriptor, C.byref(present),
                                                         C.byref(acl), C.byref(defaulted)))
            error = self.a.SetNamedSecurityInfoW(str(path), 1, 0x80000004, None, None, acl, None)
            if error:
                raise C.WinError(error)
        finally:
            self.k.LocalFree(descriptor)

    def create_desktop(self):
        if self.interactive_ui:
            self.bind(self.u,'GetUserObjectInformationW',T.BOOL,T.HANDLE,C.c_int,P,T.DWORD,C.POINTER(T.DWORD))
            self.bind(self.k,'ProcessIdToSessionId',T.BOOL,T.DWORD,C.POINTER(T.DWORD))
            self.bind(self.k,'GetCurrentProcessId',T.DWORD)
            session=T.DWORD();self.require(self.k.ProcessIdToSessionId(self.k.GetCurrentProcessId(),C.byref(session)))
            current=self.require(self.u.GetProcessWindowStation())
            name=C.create_unicode_buffer(1024);needed=T.DWORD()
            self.require(self.u.GetUserObjectInformationW(current,2,name,C.sizeof(name),C.byref(needed)))
            class Flags(C.Structure):_fields_=[('inherit',T.BOOL),('reserved',T.BOOL),('flags',T.DWORD)]
            flags=Flags();self.require(self.u.GetUserObjectInformationW(current,1,C.byref(flags),C.sizeof(flags),C.byref(needed)))
            if session.value!=3 or name.value!='WinSta0' or not flags.flags&1:
                raise ValueError('Existing visible Agents session3 required; no fallback')
            before=self.user_object_security(current)
            descriptor=self.descriptor('D:P(A;;0xf01ff;;;SY)(A;;0xf01ff;;;'+self.coordinator_sid+
                ')(A;;0xf01ff;;;'+self.user_sid+')S:(ML;;NW;;;ME)')
            desktop_name='Proof-'+uuid.uuid4().hex
            try:
                attributes=self.base.SecurityAttributes(C.sizeof(self.base.SecurityAttributes),descriptor,False)
                self.desktop=self.require(self.u.CreateDesktopW(desktop_name,None,None,0,0xf01ff,C.byref(attributes)))
            finally:self.k.LocalFree(descriptor)
            after=self.user_object_security(current)
            if before!=after:raise ValueError('Existing station security changed; no overwrite')
            # Borrow the station; close only the newly owned hidden desktop.
            self.desktop_name=name.value+'\\'+desktop_name
            self.ui_security={'station':after,'desktop':self.user_object_security(self.desktop)}
            self.ui_host=dict(session_id=session.value,station=name.value,visible=True,
                              station_security_unchanged_during_desktop_creation=True)
            return
        station_descriptor = self.descriptor('D:P(A;;0xf037f;;;SY)(A;;0xf037f;;;' +
            self.coordinator_sid + ')(A;;0xf037f;;;' + self.user_sid + ')S:(ML;;NW;;;ME)')
        desktop_descriptor = self.descriptor('D:P(A;;0xf01ff;;;SY)(A;;0xf01ff;;;' +
            self.coordinator_sid + ')(A;;0xf01ff;;;' + self.user_sid + ')S:(ML;;NW;;;ME)')
        station_name, desktop_name = 'DiskEdTest-' + uuid.uuid4().hex, 'Proof-' + uuid.uuid4().hex
        try:
            station_attributes = self.base.SecurityAttributes(C.sizeof(self.base.SecurityAttributes), station_descriptor, False)
            desktop_attributes = self.base.SecurityAttributes(C.sizeof(self.base.SecurityAttributes), desktop_descriptor, False)
            with self.base._STATION_LOCK:
                previous = self.require(self.u.GetProcessWindowStation())
                try:
                    self.station = self.require(self.u.CreateWindowStationW(station_name, 1, 0xf037f, C.byref(station_attributes)))
                    self.require(self.u.SetProcessWindowStation(self.station))
                    self.desktop = self.require(self.u.CreateDesktopW(desktop_name, None, None, 0,
                                                0xf01ff, C.byref(desktop_attributes)))
                finally:
                    self.require(self.u.SetProcessWindowStation(previous))
            self.desktop_name = station_name + '\\' + desktop_name
            self.ui_security={'station':self.user_object_security(self.station),
                              'desktop':self.user_object_security(self.desktop)}
        finally:
            self.k.LocalFree(desktop_descriptor)
            self.k.LocalFree(station_descriptor)

    def user_object_security(self, handle):
        self.bind(self.u,'GetUserObjectSecurity',T.BOOL,T.HANDLE,C.POINTER(T.DWORD),P,T.DWORD,C.POINTER(T.DWORD))
        self.bind(self.a,'ConvertSecurityDescriptorToStringSecurityDescriptorW',T.BOOL,P,T.DWORD,T.DWORD,C.POINTER(T.LPWSTR),P)
        kind,size=T.DWORD(0x14),T.DWORD()
        self.u.GetUserObjectSecurity(handle,C.byref(kind),None,0,C.byref(size))
        if not 0<size.value<=16384:raise ValueError('Unexpected private UI security size')
        data=C.create_string_buffer(size.value)
        self.require(self.u.GetUserObjectSecurity(handle,C.byref(kind),data,size,C.byref(size)))
        text=T.LPWSTR()
        self.require(self.a.ConvertSecurityDescriptorToStringSecurityDescriptorW(data,1,kind,C.byref(text),None))
        try:return text.value
        finally:self.k.LocalFree(C.cast(text,P))

    def set_default_dacl(self):
        """Only this private token's future object defaults, not existing ACLs."""
        self.bind(self.a,'InitializeSecurityDescriptor',T.BOOL,P,T.DWORD)
        self.bind(self.a,'SetSecurityDescriptorDacl',T.BOOL,P,T.BOOL,P,T.BOOL)
        self.bind(self.a,'SetTokenInformation',T.BOOL,T.HANDLE,C.c_int,P,T.DWORD)
        self.bind(self.a,'ConvertSecurityDescriptorToStringSecurityDescriptorW',T.BOOL,P,T.DWORD,T.DWORD,C.POINTER(T.LPWSTR),P)
        def observed():
            needed=T.DWORD();self.a.GetTokenInformation(self.token,6,None,0,C.byref(needed))
            if not 0<needed.value<=16384:raise ValueError('Unexpected default ACL size')
            data=C.create_string_buffer(needed.value)
            self.require(self.a.GetTokenInformation(self.token,6,data,needed,C.byref(needed)))
            acl=C.cast(data,C.POINTER(P)).contents
            sd=C.create_string_buffer(64);text=T.LPWSTR()
            self.require(self.a.InitializeSecurityDescriptor(sd,1))
            self.require(self.a.SetSecurityDescriptorDacl(sd,True,acl,False))
            self.require(self.a.ConvertSecurityDescriptorToStringSecurityDescriptorW(sd,1,4,C.byref(text),None))
            try:return text.value
            finally:self.k.LocalFree(C.cast(text,P))
        before=observed()
        descriptor=self.descriptor('D:(A;;GA;;;SY)(A;;GA;;;'+self.user_sid+')')
        try:
            acl,present,defaulted=P(),T.BOOL(),T.BOOL()
            self.require(self.a.GetSecurityDescriptorDacl(descriptor,C.byref(present),C.byref(acl),C.byref(defaulted)))
            self.require(self.a.SetTokenInformation(self.token,6,C.byref(acl),C.sizeof(acl)))
        finally:self.k.LocalFree(descriptor)
        return dict(before=before,after=observed())

    def use_logon_restriction(self):
        """Candidate limited to this fresh account and this exact logon session."""
        class Groups(C.Structure):
            _fields_=[('count',T.DWORD),('first',self.base.SidAttributes)]
        size=T.DWORD();self.a.GetTokenInformation(self.original,2,None,0,C.byref(size))
        if not 0<size.value<=16384:raise ValueError('Unexpected logon group size')
        data=C.create_string_buffer(size.value)
        self.require(self.a.GetTokenInformation(self.original,2,data,size,C.byref(size)))
        count=C.cast(data,C.POINTER(Groups)).contents.count
        if count>128:raise ValueError('Too many token groups')
        candidates=[self.base.SidAttributes.from_buffer(data,Groups.first.offset+i*C.sizeof(self.base.SidAttributes)) for i in range(count)]
        logon=[g for g in candidates if g.attributes&0xc0000000==0xc0000000]
        if len(logon)!=1:raise ValueError('Unique actual logon SID required')
        text=T.LPWSTR();self.require(self.a.ConvertSidToStringSidW(logon[0].sid,C.byref(text)))
        try:logon_sid=text.value
        finally:self.k.LocalFree(C.cast(text,P))
        if not re.fullmatch(r'S-1-5-5-[0-9]+-[0-9]+',logon_sid):raise ValueError('Unexpected logon SID')
        user=P();replacement=T.HANDLE()
        self.require(self.a.ConvertStringSidToSidW(self.user_sid,C.byref(user)))
        try:
            entries=(self.base.SidAttributes*2)(self.base.SidAttributes(user,0),self.base.SidAttributes(logon[0].sid,0))
            self.require(self.a.CreateRestrictedToken(self.original,9,0,None,0,None,2,entries,C.byref(replacement)))
            self.k.CloseHandle(self.token);self.token=replacement
        finally:self.k.LocalFree(user)
        return dict(restricting_sids=[self.user_sid,logon_sid],scope='Fresh account and its actual logon session only')

    def launch(self, command, env, job, *, variant='basic-stdio', diagnostic_original=False):
        self.last_launch=None
        if variant not in ('handles','ex-empty','basic-empty','basic-null','basic-default','basic-stdio','basic-detached'):
            raise ValueError('Unknown finite launch experiment variant')
        executable = shutil.which(command[0])
        if not executable:
            raise FileNotFoundError(command[0])
        line = subprocess.list2cmdline([executable, *command[1:]])
        if len(line) >= 1024 or '\0' in line:
            raise ValueError('Prototype WithToken bootstrap command exceeds its documented bound')
        b, k, a = self.base, self.k, self.a
        self.bind(k, 'CreateFileW', T.HANDLE, T.LPCWSTR, T.DWORD, T.DWORD,
                  C.POINTER(b.SecurityAttributes), T.DWORD, T.DWORD, T.HANDLE)
        self.bind(k, 'InitializeProcThreadAttributeList', T.BOOL, P, T.DWORD, T.DWORD, C.POINTER(C.c_size_t))
        self.bind(k, 'UpdateProcThreadAttribute', T.BOOL, P, T.DWORD, C.c_size_t, P, C.c_size_t, P, P)
        self.bind(k, 'DeleteProcThreadAttributeList', None, P)
        self.bind(a, 'CreateProcessWithTokenW', T.BOOL, T.HANDLE, T.DWORD, T.LPCWSTR,
                  T.LPWSTR, T.DWORD, P, T.LPCWSTR, P, C.POINTER(b.ProcessInfo))
        self.bind(k, 'ResumeThread', T.DWORD, T.HANDLE)
        self.bind(k, 'TerminateProcess', T.BOOL, T.HANDLE, T.UINT)
        self.bind(k, 'WaitForSingleObject', T.DWORD, T.HANDLE, T.DWORD)
        self.bind(k, 'GetExitCodeProcess', T.BOOL, T.HANDLE, C.POINTER(T.DWORD))
        handles, process, initialized = [], b.ProcessInfo(), False
        try:
            sa = b.SecurityAttributes(C.sizeof(b.SecurityAttributes), None, True)
            if variant in ('handles','basic-stdio','basic-detached'):
                log_name='worker.log' if variant=='handles' else 'worker-basic-stdio.log'
                self.launch_index=getattr(self,'launch_index',0)+1
                if self.launch_index>1:log_name=log_name.removesuffix('.log')+'-'+str(self.launch_index)+'.log'
                self.log_path=self.work/log_name
                log_access=0x40000000 if variant=='handles' else 0x40000080
                for path, access, disposition in ((str(self.work/log_name), log_access, 1), ('NUL', 0x80000000, 3)):
                    handle = k.CreateFileW(path, access, 3, C.byref(sa), disposition, 0x80, None)
                    if handle == C.c_void_p(-1).value:
                        raise C.WinError(C.get_last_error())
                    handles.append(handle)
            if variant=='handles':
                size = C.c_size_t()
                k.InitializeProcThreadAttributeList(None, 1, 0, C.byref(size))
                attributes = C.create_string_buffer(size.value)
                self.require(k.InitializeProcThreadAttributeList(attributes, 1, 0, C.byref(size)))
                initialized = True
                inherited = (T.HANDLE * 2)(*handles)
                self.require(k.UpdateProcThreadAttribute(attributes, 0, 0x20002, inherited,
                                                         C.sizeof(inherited), None, None))
            basic=variant.startswith('basic-')
            startup = b.StartupInfo() if basic else b.StartupInfoEx()
            info=startup if basic else startup.startup
            info.cb=C.sizeof(startup)
            if not basic:startup.attributes=C.addressof(attributes) if initialized else None
            info.desktop,info.flags=self.desktop_name,0 if variant=='basic-default' else 0x100
            empty=None if variant in ('basic-null','basic-default') else C.c_void_p(-1).value
            info.stdin=handles[1] if handles else empty
            info.stdout=info.stderr=handles[0] if handles else empty
            env = {key: str(value) for key, value in env.items() if not key.startswith('DISKED_TEST_ACTOR_')}
            env.update(TEMP=str(self.native_temp), TMP=str(self.native_temp), TMPDIR=str(self.native_temp),
                       USERPROFILE=str(self.work/'profile'), HOME=str(self.work/'profile'),
                       APPDATA=str(self.work/'roaming'), LOCALAPPDATA=str(self.work/'local'),
                       PROGRAMDATA=str(self.work/'common'), ALLUSERSPROFILE=str(self.work/'common'),
                       PUBLIC=str(self.work/'public'), USERNAME=self.username)
            env.update(HOMEDRIVE=self.work.drive, HOMEPATH=str(self.work/'profile')[len(self.work.drive):])
            block = C.create_unicode_buffer('\0'.join(key+'='+value for key,value in
                       sorted(env.items(), key=lambda row: row[0].upper()))+'\0\0')
            # No LOGON_WITH_PROFILE, network-only logon, fallback API or policy
            # grant. Ownership in the job precedes the first worker instruction.
            flags=(0x0000040c if variant=='basic-detached' else 0x08000404) | (0x80000 if not basic else 0)
            self.last_launch=dict(variant=variant,creation_flags=flags,startup_size=C.sizeof(startup),
                                  attribute_count=int(initialized),allowed_inherited_handles=len(handles),api_succeeded=False)
            if variant in ('basic-stdio','basic-detached'):
                class FileIdentity(C.Structure):
                    _fields_=[('volume',C.c_ulonglong),('identity',C.c_ubyte*16)]
                self.bind(k,'GetFileInformationByHandleEx',T.BOOL,T.HANDLE,C.c_int,P,T.DWORD)
                identity=FileIdentity()
                self.require(k.GetFileInformationByHandleEx(handles[0],18,C.byref(identity),C.sizeof(identity)))
                self.last_launch['stdout_identity']=dict(volume=str(identity.volume),identity=bytes(identity.identity).hex())
            observer_control=(len(command)==4 and Path(command[2])==ROOT/'loader-observer.py' and command[-1]=='loader-standard.log')
            startup_control=(len(command)==5 and command[-1] in ('startup','bootstrap') and Path(command[2])==ROOT/'target.py')
            forensic_control=(len(command)==5 and Path(command[2])==ROOT/'loader-forensics.py' and command[3] in ('--actor','--namespace') and Path(command[4])==self.work/'debug-plan.json')
            native_alias_control=(len(command)==2 and Path(command[0])==self.work/'store-journey.exe' and command[1]=='--namespace-aliases')
            if diagnostic_original and not (observer_control or startup_control or forensic_control or native_alias_control):
                raise ValueError('Unrestricted baseline is limited to the owned startup observer')
            selected_token=self.original if diagnostic_original else self.token
            self.last_launch['token_kind']='fresh_standard_baseline' if diagnostic_original else 'write_restricted'
            token_session=T.DWORD();token_size=T.DWORD()
            if a.GetTokenInformation(selected_token,12,C.byref(token_session),C.sizeof(token_session),C.byref(token_size)):
                self.last_launch['input_token_session_id']=token_session.value
            self.require(a.CreateProcessWithTokenW(selected_token, 0, executable,
                C.create_unicode_buffer(line), flags, block, str(self.work),
                C.byref(startup), C.byref(process)))
            self.last_launch['api_succeeded']=True
            # Read the actual suspended child's session before its first
            # instruction; do not infer it from the coordinator or input token.
            child_token=T.HANDLE();session=T.DWORD();needed=T.DWORD()
            self.bind(k,'ProcessIdToSessionId',T.BOOL,T.DWORD,C.POINTER(T.DWORD))
            if k.ProcessIdToSessionId(process.pid,C.byref(session)):
                self.last_launch['child_process_session_id']=session.value
            if a.OpenProcessToken(process.process,8,C.byref(child_token)):
                try:
                    if a.GetTokenInformation(child_token,12,C.byref(session),C.sizeof(session),C.byref(needed)):
                        self.last_launch['child_token_session_id']=session.value
                    else:self.last_launch['child_token_session_error']=C.get_last_error()
                finally:k.CloseHandle(child_token)
            else:self.last_launch['child_token_open_error']=C.get_last_error()
            self.require(job.api.AssignProcessToJobObject(job.handle, process.process))
            if k.ResumeThread(process.thread) == 0xffffffff:
                raise C.WinError(C.get_last_error())
            child = b.Child(k, process.process, process.pid)
            process.process = None
            return child
        finally:
            if process.process:
                k.TerminateProcess(process.process, 78)
                k.WaitForSingleObject(process.process, 10000)
                k.CloseHandle(process.process)
            if process.thread:
                k.CloseHandle(process.thread)
            if initialized:
                k.DeleteProcThreadAttributeList(attributes)
            for handle in handles:
                k.CloseHandle(handle)

    def close(self):
        # Caller must retire the containing job before releasing token/UI state.
        for name in ('token', 'original'):
            handle = getattr(self, name, None)
            if handle:
                self.k.CloseHandle(handle)
                setattr(self, name, None)
        if self.desktop:
            self.u.CloseDesktop(self.desktop)
            self.desktop = None
        if self.station:
            self.u.CloseWindowStation(self.station)
            self.station = None
