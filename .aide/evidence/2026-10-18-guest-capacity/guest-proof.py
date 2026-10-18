"""Guest adapter: retain existing storage assertions and test abrupt controller death."""
import ctypes
from ctypes import wintypes as T
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import traceback

ROOT = Path(__file__).resolve().parent


def load(name, file):
    spec = importlib.util.spec_from_file_location(name, file)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def security(path):
    a = ctypes.WinDLL('advapi32', use_last_error=True)
    k = ctypes.WinDLL('kernel32', use_last_error=True)
    pointer = ctypes.c_void_p
    a.GetNamedSecurityInfoW.argtypes = [T.LPWSTR, ctypes.c_int, T.DWORD, pointer, pointer, pointer, pointer, ctypes.POINTER(pointer)]
    a.GetNamedSecurityInfoW.restype = T.DWORD
    a.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes = [pointer, T.DWORD, T.DWORD, ctypes.POINTER(T.LPWSTR), pointer]
    k.LocalFree.argtypes = [pointer]
    descriptor = pointer(); text = T.LPWSTR()
    try:
        code = a.GetNamedSecurityInfoW(str(path), 1, 0x15, None, None, None, None, ctypes.byref(descriptor))
        if code:
            return dict(error=code)
        if not a.ConvertSecurityDescriptorToStringSecurityDescriptorW(descriptor, 1, 0x15, ctypes.byref(text), None):
            return dict(error=ctypes.get_last_error())
        return dict(sddl=text.value)
    finally:
        if text: k.LocalFree(ctypes.cast(text, pointer))
        if descriptor: k.LocalFree(descriptor)


def main():
    if not __debug__ or sys.flags.optimize:
        raise RuntimeError('Storage qualification requires active assertions')
    q = load('guest_storage', ROOT / 'tools/qualify-storage.py')
    q.SCRATCH = ROOT / 'scratch'
    state = q.small_json(q.SCRATCH / 'state.json')
    capacity = state['size_mib'] * 1024 * 1024
    if state['size_mib'] not in (32, 512):
        raise ValueError('Only the approved proof capacities are permitted')
    identities = iter(zip(state['profile_names'], state['profile_sids']))
    base_worker = q.W.Worker
    class GuestWorker(base_worker):
        def __init__(self, work, *, control=None):
            name, expected_sid = next(identities)
            super().__init__(work, control=control, private_station=True, profile_name=name)
            if self.restricting_sid != expected_sid:
                self.close()
                raise RuntimeError('Worker SID differs from its admitted device identity')
    q.W.Worker = GuestWorker
    diagnostic = r'''
probes=[]
for probe_path in ('inside-relative.tmp', str(pathlib.Path.cwd()/'inside-absolute.tmp')):
    descriptor=None
    try:
        descriptor=os.open(probe_path,os.O_RDWR|os.O_CREAT|os.O_EXCL,0o600)
        os.write(descriptor,b'x');os.close(descriptor);descriptor=None;os.unlink(probe_path)
        probes.append(dict(path=probe_path,success=True))
    except OSError as error:
        probes.append(dict(path=probe_path,success=False,errno=error.errno,winerror=error.winerror,detail=str(error)))
    finally:
        if descriptor is not None: os.close(descriptor)
result['inside_probes']=probes
native=k.CreateFileW('inside-native.tmp',0x40000000,3,None,1,0x80,None)
result['native_inside_created']=native!=ctypes.c_void_p(-1).value
result['native_inside_error']=ctypes.get_last_error()
if native!=ctypes.c_void_p(-1).value:
    k.CloseHandle(native)
    try: os.unlink('inside-native.tmp')
    except OSError as error: result['native_unlink_error']=str(error)
result['native_access_probes']=[]
for name,access in [('read',0x80000000),('readwrite',0xc0000000),('readwrite_delete',0xc0010000)]:
    path='inside-native-'+name+'.tmp'
    handle=k.CreateFileW(path,access,3,None,1,0x80,None)
    success=handle!=ctypes.c_void_p(-1).value
    probe=dict(access=hex(access),success=success,error=0 if success else ctypes.get_last_error())
    if success:
        k.CloseHandle(handle)
        try: os.unlink(path)
        except OSError as error: probe['unlink_error']=str(error)
    result['native_access_probes'].append(probe)
print(json.dumps(dict(native_access_probes=result['native_access_probes'])),flush=True)
try: result['initial_space']=shutil.disk_usage('.')._asdict()
except OSError as error: result['initial_space_error']=str(error)
print(json.dumps(dict(initial_probes=probes,space=result.get('initial_space'),space_error=result.get('initial_space_error'))),flush=True)
'''
    needle="result['temporary_directory']=tempfile.gettempdir()"
    if q.WRITER.count(needle) != 1:
        raise RuntimeError('Storage writer diagnostic insertion point changed')
    backing = "\nbacking=" + repr(state['image']) + r'''
handle=k.CreateFileW(backing,0x40000000,3,None,3,0x80,None)
result['backing_write_denied']=handle==ctypes.c_void_p(-1).value
result['backing_write_error']=ctypes.get_last_error()
if handle!=ctypes.c_void_p(-1).value: k.CloseHandle(handle)
token=T.HANDLE(); assert a.OpenProcessToken(k.GetCurrentProcess(),8,ctypes.byref(token))
a.ConvertSidToStringSidW.argtypes=[ctypes.c_void_p,ctypes.POINTER(T.LPWSTR)]
k.LocalFree.argtypes=[ctypes.c_void_p]
result['token_sids']={}
for label,kind in [('user',1),('integrity',25),('package',31)]:
    required=T.DWORD(); a.GetTokenInformation(token,kind,None,0,ctypes.byref(required))
    buffer=ctypes.create_string_buffer(required.value)
    assert a.GetTokenInformation(token,kind,buffer,required,ctypes.byref(required))
    sid=ctypes.cast(buffer,ctypes.POINTER(ctypes.c_void_p)).contents.value
    text=T.LPWSTR(); assert a.ConvertSidToStringSidW(sid,ctypes.byref(text))
    result['token_sids'][label]=text.value;k.LocalFree(ctypes.cast(text,ctypes.c_void_p))
elevated=T.DWORD();needed=T.DWORD();assert a.GetTokenInformation(token,20,ctypes.byref(elevated),4,ctypes.byref(needed))
result['initial_elevated']=elevated.value;k.CloseHandle(token)
print(json.dumps(dict(inside_native=result['native_inside_created'],inside_native_error=result['native_inside_error'],token_sids=result['token_sids'],elevated=result['initial_elevated'],backing_denied=result['backing_write_denied'],backing_error=result['backing_write_error'])),flush=True)
'''
    q.WRITER = q.WRITER.replace(needle, diagnostic+backing+'\n'+needle)
    q.WRITER += r'''
u=ctypes.WinDLL('user32',use_last_error=True)
u.GetProcessWindowStation.restype=T.HANDLE
u.GetUserObjectInformationW.argtypes=[T.HANDLE,ctypes.c_int,ctypes.c_void_p,T.DWORD,ctypes.POINTER(T.DWORD)]
name=ctypes.create_unicode_buffer(256); needed=T.DWORD()
assert u.GetUserObjectInformationW(u.GetProcessWindowStation(),2,name,ctypes.sizeof(name),ctypes.byref(needed))
result['window_station']=name.value
token=T.HANDLE(); assert a.OpenProcessToken(k.GetCurrentProcess(),8,ctypes.byref(token))
elevated=T.DWORD(); assert a.GetTokenInformation(token,20,ctypes.byref(elevated),4,ctypes.byref(needed)); k.CloseHandle(token)
result['elevated']=elevated.value
pathlib.Path('result.json').write_text(json.dumps(result))
'''
    receipt = {'schema': 'org.disked.guest-capacity-proof/1', 'status': 'running',
               'product_tests_run': False, 'existing_assertions_unchanged': True,
               'source_hashes': {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                                 for p in [*sorted(ROOT.glob('*.py')), *sorted((ROOT / 'tools').glob('*.py'))]}}
    try:
        try:
            q.capped_volume(Path(ROOT.anchor), capacity)
        except ValueError:
            receipt['ordinary_os_volume_rejected'] = True
        else:
            raise AssertionError('Ordinary OS volume admitted as capped storage')
        ui = ctypes.WinDLL('user32', use_last_error=True)
        ui.GetProcessWindowStation.restype = T.HANDLE
        parent_station = ui.GetProcessWindowStation()
        try:
            receipt['checks'] = q.exercise(state, capacity_bytes=capacity)
        finally:
            receipt['parent_station_restored'] = ui.GetProcessWindowStation() == parent_station
        assert receipt['parent_station_restored']
        assert receipt['checks']['allocation']['window_station'].startswith('DiskEdStation-')
        assert receipt['checks']['allocation']['elevated'] == 0
        assert all(p['success'] for p in receipt['checks']['allocation']['inside_probes'])
        assert receipt['checks']['allocation']['backing_write_denied']
        assert receipt['checks']['allocation']['backing_write_error'] == 5
        work = Path(state['work']) / 'controller-death'
        work.mkdir()
        # Keep the recovery journal at the managed control root so the outer
        # runner can recover it even if this driver terminates unexpectedly.
        control = Path(os.environ['DISKED_WORK_ROOT'])
        (work / 'owner.json').write_text(json.dumps({'root': str(ROOT)}))
        source = r'''
import importlib.util,json,os,pathlib,sys,time
root,control,work=map(pathlib.Path,sys.argv[1:4])
def load(n,p):
 s=importlib.util.spec_from_file_location(n,p);m=importlib.util.module_from_spec(s);s.loader.exec_module(m);return m
w=load('w',root/'tools/windows-worker.py');s=load('s',root/'tools/workspace.py')
worker=w.Worker(work,control=control,private_station=True,profile_name=sys.argv[4]);job=s.WindowsJob()
child=worker.launch([sys.executable,'-B','-c',"import pathlib,time; f=open('held','wb'); pathlib.Path('ready').write_text('ready'); time.sleep(60)"],dict(os.environ,TMP=str(work),TEMP=str(work),TMPDIR=str(work)),job)
(control/'identity.json').write_text(json.dumps(dict(worker_pid=child.pid,profile=str(worker.profile_path))))
time.sleep(60)
'''
        controller = subprocess.Popen([sys.executable, '-B', '-c', source, str(ROOT), str(control), str(work), state['profile_names'][2]])
        handle = None
        try:
            deadline = time.monotonic() + 20
            while not (work / 'ready').exists() or not (control / 'identity.json').exists():
                if controller.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Abrupt-death worker did not become ready')
                time.sleep(.05)
            identity = q.small_json(control / 'identity.json')
            api = ctypes.WinDLL('kernel32', use_last_error=True)
            q.W.bind(api, 'OpenProcess', T.HANDLE, T.DWORD, T.BOOL, T.DWORD)
            q.W.bind(api, 'WaitForSingleObject', T.DWORD, T.HANDLE, T.DWORD)
            q.W.bind(api, 'CloseHandle', T.BOOL, T.HANDLE)
            handle = q.W.require(api.OpenProcess(0x100000, False, identity['worker_pid']))
            controller.kill()
            controller.wait(timeout=10)
            if api.WaitForSingleObject(handle, 10000) != 0:
                raise RuntimeError('Worker survived controller termination')
            q.W.recover_profiles(control)
            profile = Path(identity['profile'])
            if profile.exists() or profile.is_junction():
                raise RuntimeError('Owned profile mapping survived recovery')
            (work / 'held').unlink()
            receipt['controller_death'] = dict(controller_pid=controller.pid, worker_pid=identity['worker_pid'],
                                              worker_retired=True, profile_removed=True, held_file_removed=True)
        finally:
            if controller.poll() is None:
                controller.kill()
            controller.wait(timeout=10)
            if handle:
                api.CloseHandle(handle)
        receipt['status'] = 'pass'
    except BaseException as error:
        receipt.update(status='fail', error=str(error), traceback=traceback.format_exc())
        receipt['filesystem_security'] = {str(p): security(p) for p in
                                          [Path(state['drive']), Path(state['work']), Path(state['work'])/'allocation'] if p.exists()}
        # Preserve only bounded diagnostics; never retain the generated image.
        receipt['worker_logs'] = {p.relative_to(Path(state['work'])).as_posix(): p.read_bytes()[:8192].decode(errors='replace')
                                  for p in Path(state['work']).rglob('worker.log')}
        control = Path(os.environ['DISKED_WORK_ROOT'])
        receipt['profile_journals_at_failure'] = {p.relative_to(control).as_posix(): q.small_json(p)
                                                for p in control.rglob('appcontainer-profiles.json')}
    finally:
        (ROOT / 'proof-result.json').write_text(json.dumps(receipt, indent=2)+'\n', encoding='utf-8', newline='\n')
    return 0 if receipt['status'] == 'pass' else 1


if __name__ == '__main__':
    raise SystemExit(main())
