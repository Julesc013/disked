"""Prove the authorized disposable storage setup; does not qualify DiskEd itself."""
import ctypes
from ctypes import wintypes as T
import argparse
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
SCRATCH = Path('D:/Projects/DiskEd/scratch')
EVIDENCE = ROOT / '.aide/evidence/2026-10-17-workspace-cleanup'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


W = load('disked_windows_worker', ROOT / 'tools/windows-worker.py')
S = load('disked_workspace', ROOT / 'tools/workspace.py')


def small_json(path, maximum=16384):
    data = path.read_bytes()
    if len(data) > maximum:
        raise ValueError('Oversized metadata: ' + str(path))
    return json.loads(data)


def capped_volume(path, maximum):
    path = Path(path)
    if path.parent != path or shutil.disk_usage(path).total > maximum:
        raise ValueError('Not the selected small capped filesystem root')
    return shutil.disk_usage(path)._asdict()


class SetupAdmissionBlocked(RuntimeError):
    def __init__(self, processes):
        self.processes = processes
        super().__init__('Windows consent is already pending; complete or cancel it at the VM console. '
                         'No additional elevation request was submitted.')


def pending_elevation_requests():
    """Read OS process state. Never terminate or claim ownership of consent.exe."""
    class ProcessEntry(ctypes.Structure):
        _fields_ = [('size', T.DWORD), ('usage', T.DWORD), ('pid', T.DWORD),
                    ('heap', ctypes.c_size_t), ('module', T.DWORD), ('threads', T.DWORD),
                    ('parent', T.DWORD), ('priority', T.LONG), ('flags', T.DWORD),
                    ('name', T.WCHAR * 260)]
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    W.bind(api, 'CreateToolhelp32Snapshot', T.HANDLE, T.DWORD, T.DWORD)
    W.bind(api, 'Process32FirstW', T.BOOL, T.HANDLE, ctypes.POINTER(ProcessEntry))
    W.bind(api, 'Process32NextW', T.BOOL, T.HANDLE, ctypes.POINTER(ProcessEntry))
    W.bind(api, 'ProcessIdToSessionId', T.BOOL, T.DWORD, ctypes.POINTER(T.DWORD))
    W.bind(api, 'CloseHandle', T.BOOL, T.HANDLE)
    session = T.DWORD()
    W.require(api.ProcessIdToSessionId(os.getpid(), ctypes.byref(session)))
    snapshot = api.CreateToolhelp32Snapshot(2, 0)
    if snapshot == ctypes.c_void_p(-1).value:
        raise ctypes.WinError(ctypes.get_last_error())
    records, count = [], 0
    try:
        entry = ProcessEntry()
        entry.size = ctypes.sizeof(entry)
        available = api.Process32FirstW(snapshot, ctypes.byref(entry))
        while available:
            count += 1
            if count > 65536:
                raise RuntimeError('Process snapshot exceeds admission budget')
            if entry.name.casefold() == 'consent.exe':
                other = T.DWORD()
                known = api.ProcessIdToSessionId(entry.pid, ctypes.byref(other))
                # An unreadable session is ambiguous, not permission to queue more.
                if not known or other.value == session.value:
                    records.append({'pid': entry.pid, 'session_id': other.value if known else None,
                                    'session_query_error': None if known else ctypes.get_last_error()})
            available = api.Process32NextW(snapshot, ctypes.byref(entry))
        error = ctypes.get_last_error()
        if error != 18:  # ERROR_NO_MORE_FILES
            raise ctypes.WinError(error)
    finally:
        W.require(api.CloseHandle(snapshot))
    return records


def start_setup(size, elevate=False):
    if elevate:
        pending = pending_elevation_requests()
        if pending:
            raise SetupAdmissionBlocked(pending)
    class ExecuteInfo(ctypes.Structure):
        _fields_ = [('size', T.DWORD), ('mask', T.ULONG), ('window', T.HWND),
                    ('verb', T.LPCWSTR), ('file', T.LPCWSTR), ('parameters', T.LPCWSTR),
                    ('directory', T.LPCWSTR), ('show', ctypes.c_int), ('instance', T.HINSTANCE),
                    ('idlist', ctypes.c_void_p), ('class_name', T.LPCWSTR), ('key', T.HKEY),
                    ('hotkey', T.DWORD), ('icon', T.HANDLE), ('process', T.HANDLE)]
    shell = ctypes.WinDLL('shell32', use_last_error=True)
    W.bind(shell, 'ShellExecuteExW', T.BOOL, ctypes.POINTER(ExecuteInfo))
    info = ExecuteInfo()
    # Explicitly initialize COM and suppress error dialogs; UAC remains Windows'
    # own interactive confirmation when elevation is actually requested.
    info.size, info.mask, info.verb, info.show = ctypes.sizeof(info), 0x540, 'runas' if elevate else 'open', 0
    info.file = shutil.which('pwsh.exe')
    if not info.file:
        raise FileNotFoundError('PowerShell 7 is required; do not change execution policy')
    info.parameters = subprocess.list2cmdline(['-NoProfile', '-File', str(ROOT / 'tools/capped-scratch.ps1'),
                                              '-SizeMiB', str(size)])
    info.directory = str(ROOT)
    ole = ctypes.WinDLL('ole32', use_last_error=True)
    W.bind(ole, 'CoInitializeEx', ctypes.c_long, ctypes.c_void_p, T.DWORD)
    W.bind(ole, 'CoUninitialize', None)
    hr = ole.CoInitializeEx(None, 6)
    if hr < 0:
        raise OSError('Cannot initialize the setup launch apartment: ' + hex(hr & 0xffffffff))
    try:
        W.require(shell.ShellExecuteExW(ctypes.byref(info)))
    finally:
        ole.CoUninitialize()
    api = ctypes.WinDLL('kernel32', use_last_error=True)
    W.bind(api, 'WaitForSingleObject', T.DWORD, T.HANDLE, T.DWORD)
    W.bind(api, 'GetExitCodeProcess', T.BOOL, T.HANDLE, ctypes.POINTER(T.DWORD))
    W.bind(api, 'CloseHandle', T.BOOL, T.HANDLE)
    return W.Child(api, info.process, 0)


WRITER = r'''
import ctypes, hashlib, json, os, pathlib, shutil, subprocess, sys, tempfile
from ctypes import wintypes as T
k=ctypes.WinDLL('kernel32', use_last_error=True)
a=ctypes.WinDLL('advapi32', use_last_error=True)
k.GetCurrentProcess.restype=T.HANDLE
k.CreateFileW.argtypes=[T.LPCWSTR,T.DWORD,T.DWORD,ctypes.c_void_p,T.DWORD,T.DWORD,T.HANDLE]
k.CreateFileW.restype=T.HANDLE
k.WriteFile.argtypes=[T.HANDLE,ctypes.c_void_p,T.DWORD,ctypes.POINTER(T.DWORD),ctypes.c_void_p]
k.CloseHandle.argtypes=[T.HANDLE]
a.OpenProcessToken.argtypes=[T.HANDLE,T.DWORD,ctypes.POINTER(T.HANDLE)]
a.GetTokenInformation.argtypes=[T.HANDLE,ctypes.c_int,ctypes.c_void_p,T.DWORD,ctypes.POINTER(T.DWORD)]
token=T.HANDLE(); assert a.OpenProcessToken(k.GetCurrentProcess(),8,ctypes.byref(token))
is_container=T.DWORD(); needed=T.DWORD()
assert a.GetTokenInformation(token,29,ctypes.byref(is_container),4,ctypes.byref(needed)); k.CloseHandle(token)
result={'appcontainer':is_container.value,'pid':os.getpid(),'outside':[],'maximum_attempted_bytes':67108864}
for arg in sys.argv[1:]:
    h=k.CreateFileW(str(pathlib.Path(arg)/'forbidden'),0x40000000,3,None,1,0x80,None)
    result['outside'].append({'path':arg,'denied':h==ctypes.c_void_p(-1).value,'winerror':ctypes.get_last_error()})
    if h!=ctypes.c_void_p(-1).value: k.CloseHandle(h)
child_source="import pathlib,sys; pathlib.Path(sys.argv[1]).write_bytes(b'bad')"
child=subprocess.run([sys.executable,'-B','-c',child_source,str(pathlib.Path(sys.argv[1])/'descendant')],capture_output=True,timeout=10)
result['descendant_denied']=child.returncode!=0 and b'PermissionError' in child.stderr
result['temporary_directory']=tempfile.gettempdir()
result['before']=shutil.disk_usage('.')._asdict()
payload=pathlib.Path('allocation.bin'); h=k.CreateFileW(str(payload),0x40000000,3,None,1,0x80000080,None)
if h==ctypes.c_void_p(-1).value: raise ctypes.WinError(ctypes.get_last_error())
written=0; digest=hashlib.sha256(); failure=None
try:
    for number in range(1024):
        data=os.urandom(65536); count=T.DWORD()
        if not k.WriteFile(h,data,len(data),ctypes.byref(count),None):
            failure=ctypes.get_last_error(); break
        written+=count.value; digest.update(data[:count.value])
        if count.value!=len(data): raise RuntimeError('Unexpected partial allocation')
    result.update(written_bytes=written,allocation_error=failure,payload_sha256=digest.hexdigest(),full=shutil.disk_usage('.')._asdict())
finally:
    k.CloseHandle(h); payload.unlink()
result['after_payload_removal']=shutil.disk_usage('.')._asdict()
pathlib.Path('result.json').write_text(json.dumps(result))
'''


def exercise(state):
    work = Path(state['work'])
    outside_c = Path(os.environ['DISKED_WORK_ROOT']) / 'outside'
    outside_d = SCRATCH / 'outside'
    for directory in (outside_c, outside_d):
        directory.mkdir()
        (directory / 'sentinel').write_bytes(b'unchanged')
    results = {}
    for phase in ('allocation', 'interruption'):
        current = work / phase
        current.mkdir()
        (current / 'owner.json').write_bytes(json.dumps({'root': str(ROOT)}).encode())
        worker, job, child = None, None, None
        try:
            worker, job = W.Worker(current), S.WindowsJob()
            env = dict(os.environ, DISKED_WORK_ROOT=str(current), TMP=str(current), TEMP=str(current),
                       TMPDIR=str(current), PYTHONDONTWRITEBYTECODE='1')
            source = WRITER if phase == 'allocation' else (
                "import pathlib,time; held=open('held','wb'); pathlib.Path('ready').write_text('ready'); time.sleep(60)")
            child = worker.launch([sys.executable, '-B', '-c', source, str(outside_c), str(outside_d)], env, job)
            deadline = time.monotonic() + 25
            while child.poll() is None:
                # Host reserves stay on the two backing volumes, not the tiny FS.
                S.check(ROOT)
                total = S.tree_bytes(SCRATCH, allocated=True, allow_links=False, file_limit=S.WORK_FILES)
                total += S.tree_bytes(Path(os.environ['DISKED_WORK_ROOT']), allocated=True,
                                      allow_links=True, file_limit=S.WORK_FILES)
                if total > S.WORK_LIMIT:
                    raise S.StorageLimit('Aggregate scratch ceiling exceeded')
                if phase == 'interruption' and (current / 'ready').is_file():
                    job.close()
                    child.wait()
                    (current / 'held').unlink()
                    results[phase] = {'job_retired': True, 'held_file_removed': True}
                    break
                if time.monotonic() >= deadline:
                    raise TimeoutError('Storage proof worker deadline exceeded')
                time.sleep(0.05)
            if phase == 'allocation':
                if child.wait() != 0:
                    raise RuntimeError('Storage proof worker failed: ' + (current / 'worker.log').read_text(errors='replace'))
                result = small_json(current / 'result.json')
                results[phase] = result
                assert result['appcontainer'] == 1
                assert all(row['denied'] and row['winerror'] == 5 for row in result['outside'])
                assert result['descendant_denied']
                assert result['allocation_error'] in (39, 112), result
                assert 0 < result['written_bytes'] < 32 * 1024 * 1024
                assert result['after_payload_removal']['free'] > result['full']['free']
                assert Path(result['temporary_directory']).resolve().is_relative_to(current.resolve())
        finally:
            if job:
                job.close()
            if child:
                child.wait()
                child.close()
            if worker:
                profile = worker.profile_path
                worker.close()
                if profile.exists() or profile.is_junction():
                    raise RuntimeError('Worker profile cleanup failed')
    for directory in (outside_c, outside_d):
        if sorted(p.name for p in directory.iterdir()) != ['sentinel'] or (directory / 'sentinel').read_bytes() != b'unchanged':
            raise RuntimeError('Outside sentinel changed')
        (directory / 'sentinel').unlink()
        directory.rmdir()
    results['outside_sentinels_unchanged'] = True
    return results


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elevate', action='store_true',
                        help='Request the already-authorized setup through Windows UAC')
    arguments = parser.parse_args()
    if os.name != 'nt' or str(ROOT).casefold() != 'd:\\projects\\disked\\disked':
        raise RuntimeError('This grant is specific to the current Windows checkout')
    if not os.environ.get('DISKED_WORK_ROOT'):
        raise RuntimeError('Run through tools/workspace.py; no unmanaged fallback')
    size = 32
    receipt = {'schema': 'org.disked.storage-boundary-proof/1', 'size_mib': size, 'status': 'running',
               'requested_elevation': arguments.elevate,
               'source_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
               'source_hashes': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                   for p in (Path(__file__), ROOT / 'tools/windows-worker.py', ROOT / 'tools/capped-scratch.ps1')}}
    helper, state = None, None
    try:
        S.check(ROOT)
        if SCRATCH.exists() and any(SCRATCH.iterdir()):
            raise RuntimeError('Review existing scratch before setup; do not accumulate another image')
        try:
            capped_volume(ROOT.anchor, size * 1024 * 1024)
        except ValueError:
            receipt['ordinary_host_volume_rejected'] = True
        else:
            raise RuntimeError('Ordinary host volume was incorrectly admitted')
        helper = start_setup(size, elevate=arguments.elevate)
        deadline = time.monotonic() + 60
        while time.monotonic() < deadline:
            try:
                state = small_json(SCRATCH / 'state.json')
                if state['phase'] in ('failed', 'ready'):
                    break
            except (FileNotFoundError, ValueError):
                pass
            if helper.poll() is not None:
                raise RuntimeError('Setup exited before a ready receipt')
            time.sleep(0.1)
        if state is None or state['phase'] != 'ready':
            raise RuntimeError('Capped setup did not reach ready; inspect the retained cleanup receipt')
        receipt['setup'] = state
        if state['helper_sha256'] != receipt['source_hashes']['tools/capped-scratch.ps1']:
            raise RuntimeError('Setup helper changed during admission')
        receipt['volume'] = capped_volume(state['drive'], size * 1024 * 1024)
        receipt['checks'] = exercise(state)
        receipt['status'] = 'pass'
    except Exception as error:
        receipt.update(status='blocked', error=str(error), error_type=type(error).__name__)
        if isinstance(error, SetupAdmissionBlocked):
            receipt['pending_elevation_processes'] = error.processes
    finally:
        if state and state.get('phase') == 'ready':
            (SCRATCH / 'release.json').write_bytes(json.dumps({'nonce': state['nonce'], 'workers_stopped': True}).encode())
        if helper:
            try:
                receipt['helper_exit_code'] = helper.wait(timeout=140)
                if (SCRATCH / 'state.json').exists():
                    final = small_json(SCRATCH / 'state.json')
                    receipt['cleanup'] = final
                    if final['image_removed']:
                        (SCRATCH / 'state.json').unlink()
                        SCRATCH.rmdir()
                    if final['phase'] != 'retired' or not final['image_removed']:
                        receipt['status'] = 'blocked'
            except Exception as error:
                receipt.update(status='blocked', cleanup_error=str(error))
            finally:
                helper.close()
        receipt['host_free_bytes_after'] = {letter: shutil.disk_usage(letter + ':\\').free for letter in ('C', 'D')}
        # A launch refusal must not replace retained image/cleanup observations.
        name = 'capped-storage-32.json' if helper else 'storage-elevation-admission.json'
        (EVIDENCE / name).write_bytes((json.dumps(receipt, indent=2) + '\n').encode())
    return 0 if receipt['status'] == 'pass' else 78


if __name__ == '__main__':
    raise SystemExit(main())
