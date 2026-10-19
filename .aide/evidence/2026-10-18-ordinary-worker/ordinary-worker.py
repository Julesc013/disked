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
    def __init__(self, base, work, control, username, password, expected_sid):
        if (os.name != 'nt' or socket.gethostname().casefold() != 'blackglass-hyperv' or
                Path(__file__).resolve().parent != ROOT or
                not re.fullmatch(r'DiskEdTest-[0-9a-f]{8}', username)):
            raise ValueError('Fixed guest and disposable actor identity required')
        self.base, self.bind, self.require = base, base.bind, base.require
        self.username = username
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
            self.require(self.a.LogonUserW(username, '.', password, 2, 0, C.byref(self.original)))
            self.user_sid = self.identity(self.original)
            if self.user_sid != expected_sid or self.user_sid == self.coordinator_sid:
                raise ValueError('Actual logon SID differs from owned disposable actor')
            restricting = P()
            self.require(self.a.ConvertStringSidToSidW(self.user_sid, C.byref(restricting)))
            try:
                entry = base.SidAttributes(restricting, 0)
                # Win10: DISABLE_MAX_PRIVILEGE | WRITE_RESTRICTED. No LUA or
                # SANDBOX_INERT flag and no broad restricting SID.
                self.require(self.a.CreateRestrictedToken(self.original, 9, 0, None,
                             0, None, 1, C.byref(entry), C.byref(self.token)))
            finally:
                self.k.LocalFree(restricting)
            for kind in (20, 29):  # TokenElevation, TokenIsAppContainer
                value, size = T.DWORD(), T.DWORD()
                self.require(self.a.GetTokenInformation(self.token, kind, C.byref(value),
                                                       C.sizeof(value), C.byref(size)))
                if value.value:
                    raise PermissionError('Actor must be nonelevated and non-AppContainer')
            if self.identity(self.token) != expected_sid:
                raise ValueError('Restricted token user identity changed')
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

    def identity(self, token):
        needed = T.DWORD()
        self.a.GetTokenInformation(token, 1, None, 0, C.byref(needed))
        if not 0 < needed.value <= 4096:
            raise ValueError('Invalid token user size')
        info = C.create_string_buffer(needed.value)
        self.require(self.a.GetTokenInformation(token, 1, info, needed, C.byref(needed)))
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
        station_descriptor = self.descriptor('D:P(A;;0xf037f;;;SY)(A;;0xf037f;;;' +
            self.coordinator_sid + ')(A;;0x2037f;;;' + self.user_sid + ')')
        desktop_descriptor = self.descriptor('D:P(A;;0xf01ff;;;SY)(A;;0xf01ff;;;' +
            self.coordinator_sid + ')(A;;0xf01ff;;;' + self.user_sid + ')')
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
        finally:
            self.k.LocalFree(desktop_descriptor)
            self.k.LocalFree(station_descriptor)

    def launch(self, command, env, job, *, variant='handles'):
        self.last_launch=None
        if variant not in ('handles','ex-empty','basic-empty'):
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
            if variant=='handles':
                for path, access, disposition in ((str(self.work/'worker.log'), 0x40000000, 1), ('NUL', 0x80000000, 3)):
                    handle = k.CreateFileW(path, access, 3, C.byref(sa), disposition, 0x80, None)
                    if handle == C.c_void_p(-1).value:
                        raise C.WinError(C.get_last_error())
                    handles.append(handle)
                size = C.c_size_t()
                k.InitializeProcThreadAttributeList(None, 1, 0, C.byref(size))
                attributes = C.create_string_buffer(size.value)
                self.require(k.InitializeProcThreadAttributeList(attributes, 1, 0, C.byref(size)))
                initialized = True
                inherited = (T.HANDLE * 2)(*handles)
                self.require(k.UpdateProcThreadAttribute(attributes, 0, 0x20002, inherited,
                                                         C.sizeof(inherited), None, None))
            startup = b.StartupInfo() if variant=='basic-empty' else b.StartupInfoEx()
            info=startup if variant=='basic-empty' else startup.startup
            info.cb=C.sizeof(startup)
            if variant!='basic-empty':startup.attributes=C.addressof(attributes) if initialized else None
            info.desktop,info.flags=self.desktop_name,0x100
            info.stdin=handles[1] if handles else C.c_void_p(-1).value
            info.stdout=info.stderr=handles[0] if handles else C.c_void_p(-1).value
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
            flags=0x08000404 | (0x80000 if variant!='basic-empty' else 0)
            self.last_launch=dict(variant=variant,creation_flags=flags,startup_size=C.sizeof(startup),
                                  attribute_count=int(initialized),allowed_inherited_handles=len(handles),api_succeeded=False)
            self.require(a.CreateProcessWithTokenW(self.token, 0, executable,
                C.create_unicode_buffer(line), flags, block, str(self.work),
                C.byref(startup), C.byref(process)))
            self.last_launch['api_succeeded']=True
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
