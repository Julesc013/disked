"""Windows AppContainer worker for trusted development tools, not hostile code.

This supplies process/write confinement, not a filesystem capacity limit. A normal
directory is never qualified capped storage. No elevation or disk operations here.
"""
import ctypes
from ctypes import wintypes as T
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import time
import uuid


class SecurityAttributes(ctypes.Structure):
    _fields_ = [('length', T.DWORD), ('descriptor', ctypes.c_void_p), ('inherit', T.BOOL)]


class SidAttributes(ctypes.Structure):
    _fields_ = [('sid', ctypes.c_void_p), ('attributes', T.DWORD)]


class StartupInfo(ctypes.Structure):
    _fields_ = [('cb', T.DWORD), ('reserved', T.LPWSTR), ('desktop', T.LPWSTR),
                ('title', T.LPWSTR), ('x', T.DWORD), ('y', T.DWORD),
                ('width', T.DWORD), ('height', T.DWORD), ('chars_x', T.DWORD),
                ('chars_y', T.DWORD), ('fill', T.DWORD), ('flags', T.DWORD),
                ('show', T.WORD), ('reserved_bytes', T.WORD),
                ('reserved_pointer', ctypes.c_void_p), ('stdin', T.HANDLE),
                ('stdout', T.HANDLE), ('stderr', T.HANDLE)]


class StartupInfoEx(ctypes.Structure):
    _fields_ = [('startup', StartupInfo), ('attributes', ctypes.c_void_p)]


class ProcessInfo(ctypes.Structure):
    _fields_ = [('process', T.HANDLE), ('thread', T.HANDLE), ('pid', T.DWORD), ('tid', T.DWORD)]


def bind(dll, name, result, *arguments):
    function = getattr(dll, name)
    function.restype, function.argtypes = result, list(arguments)
    return function


def require(ok):
    if not ok:
        raise ctypes.WinError(ctypes.get_last_error())
    return ok


def plain_directory(path):
    """Only owned ordinary directories; do not change ACLs through a junction."""
    path = Path(path).absolute()
    for ancestor in (path, *path.parents):
        info = ancestor.lstat()
        if ancestor.is_symlink() or getattr(info, 'st_file_attributes', 0) & 0x400:
            raise ValueError('Worker directory has a linked ancestor: ' + str(ancestor))
    if not path.is_dir():
        raise ValueError('Worker root must exist and be a directory')
    return path


def profiles(control):
    path = Path(control) / 'appcontainer-profiles.json'
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {}
    if path.is_symlink() or info.st_file_attributes & 0x400 or info.st_size > 16384:
        raise ValueError('Untrusted or oversized worker profile journal')
    result = json.loads(path.read_bytes())
    if not isinstance(result, dict) or len(result) > 8:
        raise ValueError('Invalid worker profile journal')
    return result


def save_profiles(control, value):
    path = Path(control) / 'appcontainer-profiles.json'
    data = (json.dumps(value, sort_keys=True) + '\n').encode()
    if len(data) > 16384:
        raise ValueError('Worker profile journal budget exceeded')
    temporary = path.with_suffix('.new')
    if temporary.exists() or temporary.is_symlink():
        raise ValueError('Unresolved worker profile journal transaction')
    with temporary.open('xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def retire_profile(name, target):
    """Remove only our exact identity and its alias, never the aliased contents."""
    if not re.fullmatch(r'org\.disked\.worker\.[0-9a-f]{32}', name):
        raise ValueError('Unrecognized temporary worker identity')
    folder = Path(os.environ['LOCALAPPDATA']) / 'Packages' / name
    plain_directory(folder.parent)
    if folder.is_junction():
        def normalized(value):
            return str(value).removeprefix('\\??\\').removeprefix('\\\\?\\').casefold().rstrip('\\')
        if normalized(folder.readlink()) != normalized(target):
            raise ValueError('Worker profile junction target changed')
        folder.rmdir()
    elif folder.exists():
        plain_directory(folder)
        # Only the tiny initial profile may exist without its scratch alias.
        size, count = 0, 0
        for current, directories, files in os.walk(folder, followlinks=False):
            for leaf in directories + files:
                path = Path(current) / leaf
                info = path.lstat()
                count += 1
                size += info.st_size if path.is_file() else 0
                if info.st_file_attributes & 0x400 or count > 256 or size > 1048576:
                    raise ValueError('Unexpected unredirected worker profile; preserve for review')
    userenv = ctypes.WinDLL('userenv', use_last_error=True)
    hr = bind(userenv, 'DeleteAppContainerProfile', ctypes.c_long, T.LPCWSTR)(name)
    if hr < 0:
        raise OSError('Cannot retire owned AppContainer profile: ' + hex(hr & 0xffffffff))


def recover_profiles(control):
    """Caller must first retire its job/processes. Ambiguous ownership blocks reuse."""
    control = plain_directory(control)
    records = profiles(control)
    for name, record in list(records.items()):
        if not isinstance(record, dict) or record.get('phase') != 'created':
            raise ValueError('Ambiguous profile creation interrupted; review before reuse')
        retire_profile(name, record['target'])
        del records[name]
        save_profiles(control, records)


class Capabilities(ctypes.Structure):
    _fields_ = [('sid', ctypes.c_void_p), ('capabilities', ctypes.c_void_p),
                ('count', T.DWORD), ('reserved', T.DWORD)]


class Worker:
    """Scratch-mapped AppContainer, private desktop and suspended launch into a job.

    Writes still need both the user's ordinary access and the unique restricting
    SID's access. Only the freshly owned work directory receives that SID. The
    caller must close the containing job before closing this worker.
    """
    def __init__(self, work, *, control=None):
        if os.name != 'nt':
            raise OSError('Windows worker requires Windows')
        self.work = plain_directory(work)
        marker = self.work / 'owner.json'
        if (not marker.is_file() or marker.stat().st_size > 16384 or
                marker.lstat().st_file_attributes & 0x400):
            raise ValueError('Worker root lacks a bounded ownership marker')
        if set(p.name for p in self.work.iterdir()) != {'owner.json'}:
            raise ValueError('Worker root must be fresh, containing only owner.json')
        if control is None:
            control = os.environ.get('DISKED_WORK_ROOT')
            if not control:
                raise ValueError('A managed controller workspace is required')
        self.control = plain_directory(control)
        owner = self.control / 'owner.json'
        if (not owner.is_file() or owner.stat().st_size > 16384 or
                owner.lstat().st_file_attributes & 0x400):
            raise ValueError('Missing bounded controller ownership marker')
        expected = str(Path(__file__).resolve().parents[1])
        if (json.loads(owner.read_bytes()).get('root') != expected or
                json.loads(marker.read_bytes()).get('root') != expected):
            raise ValueError('Worker/controller source ownership mismatch')
        self.journaled = False
        self.sid = self.descriptor = self.desktop = None
        self.profile_created = False
        self.profile_path = None
        self.k = ctypes.WinDLL('kernel32', use_last_error=True)
        self.a = ctypes.WinDLL('advapi32', use_last_error=True)
        self.u = ctypes.WinDLL('user32', use_last_error=True)
        self.e = ctypes.WinDLL('userenv', use_last_error=True)
        P = ctypes.c_void_p
        bind(self.k, 'CloseHandle', T.BOOL, T.HANDLE)
        bind(self.k, 'LocalFree', P, P)
        bind(self.k, 'GetCurrentProcess', T.HANDLE)
        bind(self.a, 'FreeSid', P, P)
        bind(self.a, 'OpenProcessToken', T.BOOL, T.HANDLE, T.DWORD, ctypes.POINTER(T.HANDLE))
        bind(self.a, 'GetTokenInformation', T.BOOL, T.HANDLE, ctypes.c_int, P, T.DWORD, ctypes.POINTER(T.DWORD))
        bind(self.a, 'ConvertSidToStringSidW', T.BOOL, P, ctypes.POINTER(T.LPWSTR))
        bind(self.a, 'ConvertStringSecurityDescriptorToSecurityDescriptorW', T.BOOL,
             T.LPCWSTR, T.DWORD, ctypes.POINTER(P), ctypes.POINTER(T.DWORD))
        bind(self.a, 'GetSecurityDescriptorDacl', T.BOOL, P, ctypes.POINTER(T.BOOL),
             ctypes.POINTER(P), ctypes.POINTER(T.BOOL))
        bind(self.a, 'GetSecurityDescriptorSacl', T.BOOL, P, ctypes.POINTER(T.BOOL),
             ctypes.POINTER(P), ctypes.POINTER(T.BOOL))
        bind(self.a, 'SetNamedSecurityInfoW', T.DWORD, T.LPWSTR, ctypes.c_int, T.DWORD, P, P, P, P)
        bind(self.e, 'DeriveAppContainerSidFromAppContainerName', ctypes.c_long, T.LPCWSTR, ctypes.POINTER(P))
        bind(self.e, 'CreateAppContainerProfile', ctypes.c_long, T.LPCWSTR, T.LPCWSTR,
             T.LPCWSTR, P, T.DWORD, ctypes.POINTER(P))
        bind(self.e, 'DeleteAppContainerProfile', ctypes.c_long, T.LPCWSTR)
        bind(self.e, 'GetAppContainerFolderPath', ctypes.c_long, T.LPCWSTR, ctypes.POINTER(T.LPWSTR))
        bind(self.u, 'GetProcessWindowStation', T.HANDLE)
        bind(self.u, 'GetUserObjectInformationW', T.BOOL, T.HANDLE, ctypes.c_int, P,
             T.DWORD, ctypes.POINTER(T.DWORD))
        bind(self.u, 'CreateDesktopW', T.HANDLE, T.LPCWSTR, P, P, T.DWORD, T.DWORD,
             ctypes.POINTER(SecurityAttributes))
        bind(self.u, 'CloseDesktop', T.BOOL, T.HANDLE)
        original = T.HANDLE()
        try:
            require(self.a.OpenProcessToken(self.k.GetCurrentProcess(), 8, ctypes.byref(original)))
            size = T.DWORD()
            self.a.GetTokenInformation(original, 1, None, 0, ctypes.byref(size))
            user_info = ctypes.create_string_buffer(size.value)
            require(self.a.GetTokenInformation(original, 1, user_info, size, ctypes.byref(size)))
            user_string = T.LPWSTR()
            require(self.a.ConvertSidToStringSidW(ctypes.cast(user_info, ctypes.POINTER(SidAttributes)).contents.sid,
                                                 ctypes.byref(user_string)))
            try:
                self.user_sid = user_string.value
            finally:
                self.k.LocalFree(ctypes.cast(user_string, P))
            # Create only a new temporary identity. Its default filesystem profile
            # is redirected into owned work before any worker starts.
            self.profile_name = 'org.disked.worker.' + uuid.uuid4().hex
            self.sid = P()
            records = profiles(self.control)
            if records:
                raise ValueError('Retire unresolved worker profiles before another launch')
            records[self.profile_name] = {'phase': 'creating', 'target': str(self.work / 'profile')}
            save_profiles(self.control, records)
            self.journaled = True
            hr = self.e.CreateAppContainerProfile(self.profile_name, self.profile_name,
                    'Disposable DiskEd test worker', None, 0, ctypes.byref(self.sid))
            if hr < 0:
                raise OSError('Cannot create AppContainer profile: ' + hex(hr & 0xffffffff))
            self.profile_created = True
            records[self.profile_name]['phase'] = 'created'
            save_profiles(self.control, records)
            sid_string = T.LPWSTR()
            require(self.a.ConvertSidToStringSidW(self.sid, ctypes.byref(sid_string)))
            try:
                self.restricting_sid = sid_string.value
            finally:
                self.k.LocalFree(ctypes.cast(sid_string, P))
            sddl = ('D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;' + self.user_sid +
                    ')(A;OICI;0x1301bf;;;' + self.restricting_sid + ')S:(ML;OICI;NW;;;LW)')
            self.descriptor = P()
            require(self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(sddl, 1,
                    ctypes.byref(self.descriptor), None))
            present, defaulted, dacl, sacl = T.BOOL(), T.BOOL(), P(), P()
            require(self.a.GetSecurityDescriptorDacl(self.descriptor, ctypes.byref(present),
                    ctypes.byref(dacl), ctypes.byref(defaulted)))
            require(self.a.GetSecurityDescriptorSacl(self.descriptor, ctypes.byref(present),
                    ctypes.byref(sacl), ctypes.byref(defaulted)))
            error = self.a.SetNamedSecurityInfoW(str(self.work), 1, 0x80000014, None, None, dacl, sacl)
            if error:
                raise ctypes.WinError(error)
            folder = T.LPWSTR()
            hr = self.e.GetAppContainerFolderPath(self.restricting_sid, ctypes.byref(folder))
            if hr < 0:
                raise OSError('Cannot resolve owned profile: ' + hex(hr & 0xffffffff))
            try:
                folder_path = Path(folder.value)
                if folder_path.name != 'AC':
                    raise ValueError('Unexpected AppContainer AC directory')
                self.profile_path = folder_path.parent
            finally:
                ole = ctypes.WinDLL('ole32')
                bind(ole, 'CoTaskMemFree', None, P)(ctypes.cast(folder, P))
            expected_parent = Path(os.environ['LOCALAPPDATA']) / 'Packages'
            if (self.profile_path.parent.resolve() != expected_parent.resolve() or
                    self.profile_path.name.casefold() != self.profile_name.casefold()):
                raise ValueError('Unexpected AppContainer profile location: ' + str(self.profile_path) +
                                 '; expected parent ' + str(expected_parent))
            plain_directory(self.profile_path)
            entries, initial_bytes = [], 0
            for path in self.profile_path.rglob('*'):
                entries.append(path)
                initial_bytes += path.stat().st_size if path.is_file() else 0
                if len(entries) > 256 or initial_bytes > 1048576:
                    raise ValueError('Initial owned profile exceeds tiny setup allowance')
            for path in entries:
                if path.is_symlink() or getattr(path.lstat(), 'st_file_attributes', 0) & 0x400:
                    raise ValueError('Initial profile contains a link')
            target = self.work / 'profile'
            shutil.copytree(self.profile_path, target)
            # Delete only entries in the newly created, checked profile, deepest
            # first; never recursively delete through its eventual junction.
            for path in sorted(entries, key=lambda p: len(p.parts), reverse=True):
                path.rmdir() if path.is_dir() else path.unlink()
            self.profile_path.rmdir()
            if any(c in str(self.profile_path) + str(target) for c in '&|<>^%!"'):
                raise ValueError('Unsupported junction path characters')
            subprocess.run(['cmd', '/d', '/c', 'mklink', '/J', str(self.profile_path), str(target)],
                           check=True, capture_output=True, timeout=10)
            station_name, needed = ctypes.create_unicode_buffer(256), T.DWORD()
            require(self.u.GetUserObjectInformationW(self.u.GetProcessWindowStation(), 2,
                    station_name, ctypes.sizeof(station_name), ctypes.byref(needed)))
            name = 'DiskEd-' + uuid.uuid4().hex
            self.desktop_name = station_name.value + '\\' + name
            ui_descriptor = P()
            ui_sddl = ('D:P(A;;0xf01ff;;;SY)(A;;0xf01ff;;;' + self.user_sid +
                       ')(A;;0xf01ff;;;' + self.restricting_sid + ')S:(ML;;NW;;;LW)')
            require(self.a.ConvertStringSecurityDescriptorToSecurityDescriptorW(ui_sddl, 1,
                    ctypes.byref(ui_descriptor), None))
            try:
                attributes = SecurityAttributes(ctypes.sizeof(SecurityAttributes), ui_descriptor, False)
                self.desktop = require(self.u.CreateDesktopW(name, None, None, 0,
                                                             0xf01ff, ctypes.byref(attributes)))
            finally:
                self.k.LocalFree(ui_descriptor)
        except BaseException:
            self.close()
            raise
        finally:
            if original:
                self.k.CloseHandle(original)

    def launch(self, command, env, job):
        """Return a process suspended until ownership in the supplied job is proven."""
        P = ctypes.c_void_p
        executable = shutil.which(command[0])
        if not executable:
            raise FileNotFoundError(command[0])
        command = [executable, *command[1:]]
        if any('\0' in item for item in command):
            raise ValueError('NUL in worker command')
        bind(self.k, 'CreateFileW', T.HANDLE, T.LPCWSTR, T.DWORD, T.DWORD,
             ctypes.POINTER(SecurityAttributes), T.DWORD, T.DWORD, T.HANDLE)
        bind(self.k, 'InitializeProcThreadAttributeList', T.BOOL, P, T.DWORD, T.DWORD,
             ctypes.POINTER(ctypes.c_size_t))
        bind(self.k, 'UpdateProcThreadAttribute', T.BOOL, P, T.DWORD, ctypes.c_size_t,
             P, ctypes.c_size_t, P, P)
        bind(self.k, 'DeleteProcThreadAttributeList', None, P)
        bind(self.k, 'CreateProcessW', T.BOOL, T.LPCWSTR, T.LPWSTR,
             P, P, T.BOOL, T.DWORD, P, T.LPCWSTR, ctypes.POINTER(StartupInfoEx), ctypes.POINTER(ProcessInfo))
        bind(self.k, 'ResumeThread', T.DWORD, T.HANDLE)
        bind(self.k, 'TerminateProcess', T.BOOL, T.HANDLE, T.UINT)
        bind(self.k, 'WaitForSingleObject', T.DWORD, T.HANDLE, T.DWORD)
        bind(self.k, 'GetExitCodeProcess', T.BOOL, T.HANDLE, ctypes.POINTER(T.DWORD))
        sa = SecurityAttributes(ctypes.sizeof(SecurityAttributes), None, True)
        handles, attributes, initialized, process = [], None, False, ProcessInfo()
        try:
            for name, access, disposition in [(str(self.work / 'worker.log'), 0x40000000, 1), ('NUL', 0x80000000, 3)]:
                handle = self.k.CreateFileW(name, access, 3, ctypes.byref(sa), disposition, 0x80, None)
                if handle == ctypes.c_void_p(-1).value:
                    raise ctypes.WinError(ctypes.get_last_error())
                handles.append(handle)
            size = ctypes.c_size_t()
            self.k.InitializeProcThreadAttributeList(None, 2, 0, ctypes.byref(size))
            attributes = ctypes.create_string_buffer(size.value)
            require(self.k.InitializeProcThreadAttributeList(attributes, 2, 0, ctypes.byref(size)))
            initialized = True
            inherited = (T.HANDLE * len(handles))(*handles)
            require(self.k.UpdateProcThreadAttribute(attributes, 0, 0x20002, inherited,
                                                     ctypes.sizeof(inherited), None, None))
            capabilities = Capabilities(self.sid, None, 0, 0)
            require(self.k.UpdateProcThreadAttribute(attributes, 0, 0x20009, ctypes.byref(capabilities),
                                                     ctypes.sizeof(capabilities), None, None))
            startup = StartupInfoEx()
            startup.startup.cb = ctypes.sizeof(startup)
            startup.startup.desktop = self.desktop_name
            startup.startup.flags = 0x100
            startup.startup.stdin = handles[1]
            startup.startup.stdout = startup.startup.stderr = handles[0]
            startup.attributes = ctypes.addressof(attributes)
            env = dict(env, LOCALAPPDATA=str(self.work / 'local'), APPDATA=str(self.work / 'roaming'),
                       USERPROFILE=str(self.work / 'profile'))
            block = ctypes.create_unicode_buffer('\0'.join(k + '=' + str(v) for k, v in
                    sorted(env.items(), key=lambda row: row[0].upper())) + '\0\0')
            line = ctypes.create_unicode_buffer(subprocess.list2cmdline(command))
            require(self.k.CreateProcessW(executable, line, None, None,
                    True, 0x08080404, block, str(self.work), ctypes.byref(startup), ctypes.byref(process)))
            # The worker cannot execute even one instruction before job assignment.
            require(job.api.AssignProcessToJobObject(job.handle, process.process))
            if self.k.ResumeThread(process.thread) == 0xffffffff:
                raise ctypes.WinError(ctypes.get_last_error())
            child = Child(self.k, process.process, process.pid)
            process.process = None
            return child
        finally:
            if process.process:
                self.k.TerminateProcess(process.process, 78)
                self.k.WaitForSingleObject(process.process, 10000)
                self.k.CloseHandle(process.process)
            if process.thread:
                self.k.CloseHandle(process.thread)
            if initialized:
                self.k.DeleteProcThreadAttributeList(attributes)
            for handle in handles:
                self.k.CloseHandle(handle)

    def close(self):
        if self.desktop:
            self.u.CloseDesktop(self.desktop)
            self.desktop = None
        cleanup_error = None
        try:
            if self.profile_created:
                retire_profile(self.profile_name, self.work / 'profile')
                self.profile_created = False
            if self.journaled:
                records = profiles(self.control)
                records.pop(self.profile_name, None)
                save_profiles(self.control, records)
                self.journaled = False
        except Exception as error:
            cleanup_error = error
        if self.sid:
            self.a.FreeSid(self.sid)
            self.sid = None
        if self.descriptor:
            self.k.LocalFree(self.descriptor)
            self.descriptor = None
        if cleanup_error:
            raise cleanup_error


class Child:
    def __init__(self, api, handle, pid):
        self.api, self.handle, self.pid = api, handle, pid

    def poll(self):
        state = self.api.WaitForSingleObject(self.handle, 0)
        if state == 0x102:
            return None
        if state != 0:
            raise ctypes.WinError(ctypes.get_last_error())
        code = T.DWORD()
        require(self.api.GetExitCodeProcess(self.handle, ctypes.byref(code)))
        return code.value

    def wait(self, timeout=10):
        deadline = time.monotonic() + timeout
        while self.poll() is None:
            if time.monotonic() >= deadline:
                raise TimeoutError('Restricted worker did not exit')
            time.sleep(0.02)
        return self.poll()

    def close(self):
        if self.handle:
            self.api.CloseHandle(self.handle)
            self.handle = None
