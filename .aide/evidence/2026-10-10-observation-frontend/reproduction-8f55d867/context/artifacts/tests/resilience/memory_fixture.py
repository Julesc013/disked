"""Observe only owned test processes; assign host jobs atomically at creation."""
import ctypes as C
from ctypes import wintypes as W
import msvcrt
import os
from pathlib import Path
import subprocess
import tempfile

K = C.WinDLL('kernel32', use_last_error=True)
A = C.WinDLL('advapi32', use_last_error=True)
PTR = C.c_void_p
MIB = 1024 * 1024

def bind(dll, name, result, args):
    value = getattr(dll, name); value.restype = result; value.argtypes = args
    return value

bind(K, 'GetCurrentProcess', W.HANDLE, [])
bind(K, 'CloseHandle', W.BOOL, [W.HANDLE])
bind(K, 'LocalFree', PTR, [PTR])
bind(K, 'CreateJobObjectW', W.HANDLE, [PTR, W.LPCWSTR])
bind(K, 'OpenJobObjectW', W.HANDLE, [W.DWORD, W.BOOL, W.LPCWSTR])
bind(K, 'SetInformationJobObject', W.BOOL, [W.HANDLE, C.c_int, PTR, W.DWORD])
bind(K, 'QueryInformationJobObject', W.BOOL, [W.HANDLE, C.c_int, PTR, W.DWORD, PTR])
bind(K, 'IsProcessInJob', W.BOOL, [W.HANDLE, W.HANDLE, C.POINTER(W.BOOL)])
bind(K, 'CreateMutexW', W.HANDLE, [PTR, W.BOOL, W.LPCWSTR])
bind(K, 'ReleaseMutex', W.BOOL, [W.HANDLE])
bind(K, 'WaitForSingleObject', W.DWORD, [W.HANDLE, W.DWORD])
bind(K, 'GetExitCodeProcess', W.BOOL, [W.HANDLE, C.POINTER(W.DWORD)])
bind(K, 'TerminateProcess', W.BOOL, [W.HANDLE, W.UINT])
bind(K, 'K32GetProcessMemoryInfo', W.BOOL, [W.HANDLE, PTR, W.DWORD])
bind(A, 'OpenProcessToken', W.BOOL, [W.HANDLE, W.DWORD, C.POINTER(W.HANDLE)])
bind(A, 'GetTokenInformation', W.BOOL, [W.HANDLE, C.c_int, PTR, W.DWORD, C.POINTER(W.DWORD)])
bind(A, 'ConvertSidToStringSidW', W.BOOL, [PTR, C.POINTER(PTR)])

def checked(ok):
    if not ok: raise C.WinError(C.get_last_error())
    return ok

class Basic(C.Structure):
    _fields_ = [('process_time', C.c_int64), ('job_time', C.c_int64), ('flags', W.DWORD),
                ('minimum_working', C.c_size_t), ('maximum_working', C.c_size_t), ('active_limit', W.DWORD),
                ('affinity', C.c_size_t), ('priority', W.DWORD), ('scheduling', W.DWORD)]
class Limits(C.Structure):
    _fields_ = [('basic', Basic), ('io', C.c_uint64 * 6), ('process_memory', C.c_size_t),
                ('job_memory', C.c_size_t), ('peak_process', C.c_size_t), ('peak_job', C.c_size_t)]
class Memory(C.Structure):
    _fields_ = [('cb', W.DWORD), ('faults', W.DWORD), ('peak_working', C.c_size_t),
                ('working', C.c_size_t), ('peak_paged', C.c_size_t), ('paged', C.c_size_t),
                ('peak_nonpaged', C.c_size_t), ('nonpaged', C.c_size_t),
                ('pagefile', C.c_size_t), ('peak_pagefile', C.c_size_t), ('private', C.c_size_t)]
class Startup(C.Structure):
    _fields_ = [('cb', W.DWORD), ('reserved', W.LPWSTR), ('desktop', W.LPWSTR), ('title', W.LPWSTR),
                ('x', W.DWORD), ('y', W.DWORD), ('width', W.DWORD), ('height', W.DWORD),
                ('chars_x', W.DWORD), ('chars_y', W.DWORD), ('fill', W.DWORD), ('flags', W.DWORD),
                ('show', W.WORD), ('reserved_size', W.WORD), ('reserved2', PTR),
                ('input', W.HANDLE), ('output', W.HANDLE), ('error', W.HANDLE)]
class StartupEx(C.Structure):
    _fields_ = [('startup', Startup), ('attributes', PTR)]
class ProcessInfo(C.Structure):
    _fields_ = [('process', W.HANDLE), ('thread', W.HANDLE), ('pid', W.DWORD), ('tid', W.DWORD)]

bind(K, 'InitializeProcThreadAttributeList', W.BOOL, [PTR, W.DWORD, W.DWORD, C.POINTER(C.c_size_t)])
bind(K, 'UpdateProcThreadAttribute', W.BOOL, [PTR, W.DWORD, C.c_size_t, PTR, C.c_size_t, PTR, PTR])
bind(K, 'DeleteProcThreadAttributeList', None, [PTR])
bind(K, 'CreateProcessW', W.BOOL, [W.LPCWSTR, W.LPWSTR, PTR, PTR, W.BOOL, W.DWORD, PTR,
                                  W.LPCWSTR, C.POINTER(StartupEx), C.POINTER(ProcessInfo)])

def sid():
    token = W.HANDLE(); raw = PTR()
    checked(A.OpenProcessToken(K.GetCurrentProcess(), 8, C.byref(token)))
    try:
        user = (C.c_uint64 * 128)(); needed = W.DWORD()
        checked(A.GetTokenInformation(token, 1, user, C.sizeof(user), C.byref(needed)))
        checked(A.ConvertSidToStringSidW(C.cast(user, C.POINTER(PTR))[0], C.byref(raw)))
        return C.wstring_at(raw)
    finally:
        if raw: K.LocalFree(raw)
        K.CloseHandle(token)

def name(test=False, mutex=False):
    return 'Local\\DiskEd.Fake.Memory.' + ('Test.' if test else '') + 'v1.' + ('Init.' if mutex else '') + sid()

def memory(handle):
    value = Memory(); value.cb = C.sizeof(value)
    checked(K.K32GetProcessMemoryInfo(handle, C.byref(value), C.sizeof(value)))
    return dict(private_bytes=value.private, peak_commit_bytes=value.peak_pagefile,
                working_set_bytes=value.working, peak_working_set_bytes=value.peak_working)

def limits(handle):
    value = Limits()
    checked(K.QueryInformationJobObject(handle, 9, C.byref(value), C.sizeof(value), None))
    return dict(flags=value.basic.flags, process_bytes=value.process_memory,
                job_bytes=value.job_memory, active_limit=value.basic.active_limit,
                peak_process_bytes=value.peak_process, peak_job_bytes=value.peak_job)

def member(process, job):
    value = W.BOOL(); checked(K.IsProcessInJob(process, job, C.byref(value)))
    return bool(value.value)

class Job:
    def __init__(self, cap, named=None, ui=False):
        self.handle = checked(K.CreateJobObjectW(None, named))
        if named and C.get_last_error() == 183:
            K.CloseHandle(self.handle); self.handle = None
            raise RuntimeError('isolated test job already exists; refusing to change it')
        try:
            value = Limits(); value.basic.flags = 0x100; value.process_memory = cap
            checked(K.SetInformationJobObject(self.handle, 9, C.byref(value), C.sizeof(value)))
            if ui:
                restrictions = W.DWORD(1)  # JOB_OBJECT_UILIMIT_HANDLES prevents nested assignment.
                checked(K.SetInformationJobObject(self.handle, 4, C.byref(restrictions), C.sizeof(restrictions)))
        except BaseException:
            K.CloseHandle(self.handle); self.handle = None; raise
    def __enter__(self): return self
    def __exit__(self, *_):
        if self.handle: K.CloseHandle(self.handle); self.handle = None

class AssignedProcess:
    """File-backed stdio, explicit handle list and pre-start host-job assignment.

    Cleanup may terminate only this fixture-owned frontend. No fake worker is
    launched by these host restriction/allocation cases.
    """
    def __init__(self, argv, job, env=None):
        self.temp = tempfile.TemporaryDirectory(prefix='disked-memory-host-')
        self.files = []; self.handle = None; self.pid = None
        attributes = None; initialized = False
        try:
            self.files = [open(Path(self.temp.name)/n, 'w+b') for n in ('in', 'out', 'err')]
            handles = (W.HANDLE * 3)(*(msvcrt.get_osfhandle(f.fileno()) for f in self.files))
            for f in self.files: os.set_inheritable(f.fileno(), True)
            size = C.c_size_t()
            K.InitializeProcThreadAttributeList(None, 2, 0, C.byref(size))
            attributes = C.create_string_buffer(size.value)
            checked(K.InitializeProcThreadAttributeList(attributes, 2, 0, C.byref(size))); initialized = True
            checked(K.UpdateProcThreadAttribute(attributes, 0, 0x20002, handles, C.sizeof(handles), None, None))
            jobs = (W.HANDLE * 1)(job.handle)
            checked(K.UpdateProcThreadAttribute(attributes, 0, 0x2000D, jobs, C.sizeof(jobs), None, None))
            startup = StartupEx(); startup.startup.cb = C.sizeof(startup); startup.attributes = C.addressof(attributes)
            startup.startup.flags = 0x101; startup.startup.show = 0
            startup.startup.input, startup.startup.output, startup.startup.error = handles
            command = C.create_unicode_buffer(subprocess.list2cmdline(list(map(str, argv))))
            environment = C.create_unicode_buffer('\0'.join(k+'='+v for k,v in sorted((env or os.environ).items()))+'\0\0')
            info = ProcessInfo()
            checked(K.CreateProcessW(str(argv[0]), command, None, None, True, 0x08080400,
                                    environment, self.temp.name, C.byref(startup), C.byref(info)))
            self.handle = info.process; self.pid = info.pid; K.CloseHandle(info.thread)
        except BaseException:
            self.close(); raise
        finally:
            if initialized: K.DeleteProcThreadAttributeList(attributes)
            for f in self.files:
                if not f.closed: os.set_inheritable(f.fileno(), False)
    def poll(self):
        if K.WaitForSingleObject(self.handle, 0) == 258: return None
        value = W.DWORD(); checked(K.GetExitCodeProcess(self.handle, C.byref(value))); return value.value
    def result(self, timeout=8):
        if K.WaitForSingleObject(self.handle, int(timeout*1000)) != 0:
            raise subprocess.TimeoutExpired('owned memory fixture', timeout)
        for f in self.files: f.seek(0)
        return self.poll(), self.files[1].read(), self.files[2].read()
    def close(self):
        if self.handle:
            if self.poll() is None:
                K.TerminateProcess(self.handle, 99); K.WaitForSingleObject(self.handle, 3000)
            K.CloseHandle(self.handle); self.handle = None
        for f in self.files: f.close()
        self.temp.cleanup()
    def __enter__(self): return self
    def __exit__(self, *_): self.close()
