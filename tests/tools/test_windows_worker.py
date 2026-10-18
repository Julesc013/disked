"""Actual Windows write checks with owned tiny stand-ins; never physical storage."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest


ROOT = Path(__file__).resolve().parents[2]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


W = load('disked_windows_worker', ROOT / 'tools/windows-worker.py')
S = load('disked_workspace', ROOT / 'tools/workspace.py')


@unittest.skipUnless(os.name == 'nt', 'Windows token/desktop tests')
class WindowsWorkerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='disked-restricted-test-')
        self.base = Path(self.temp.name).resolve()
        (self.base / 'owner.json').write_bytes(json.dumps({'root': str(ROOT)}).encode())
        self.work = self.base / 'allowed'
        self.work.mkdir()
        (self.work / 'owner.json').write_text(json.dumps({'root': str(ROOT)}), encoding='utf-8')
        self.outside = self.base / 'outside'
        self.outside.mkdir()
        self.sentinel = self.outside / 'sentinel'
        self.sentinel.write_bytes(b'unchanged')
        self.worker = None
        self.job = None
        self.child = None

    def tearDown(self):
        if self.job:
            self.job.close()
        if self.child:
            self.child.wait()
            self.child.close()
        if self.worker:
            self.worker.close()
        self.assertEqual(self.sentinel.read_bytes(), b'unchanged')
        self.temp.cleanup()

    def launch(self, source, *arguments):
        self.worker = W.Worker(self.work, control=self.base)
        self.job = S.WindowsJob()
        env = dict(os.environ, TMP=str(self.work), TEMP=str(self.work), TMPDIR=str(self.work),
                   PYTHONDONTWRITEBYTECODE='1')
        self.child = self.worker.launch([sys.executable, '-B', '-c', source, *map(str, arguments)], env, self.job)
        return self.child

    def result(self):
        code = self.child.wait(timeout=15)
        self.assertEqual(code, 0, (self.work / 'worker.log').read_text(errors='replace'))
        return json.loads((self.work / 'result.json').read_text())

    def test_worker_and_descendant_cannot_write_outside(self):
        source = r'''
import ctypes, json, os, pathlib, subprocess, sys
outside = pathlib.Path(sys.argv[1])
result = {}
for name, path in [('create', outside/'new'), ('modify', outside/'sentinel')]:
    try:
        path.write_bytes(b'incorrect')
        result[name] = 'ALLOWED'
    except OSError as error:
        result[name] = {'winerror': error.winerror, 'errno': error.errno}
pathlib.Path('inside').write_bytes(b'allowed')
child_source = "import pathlib,sys; p=pathlib.Path(sys.argv[1]); p.write_bytes(b'incorrect')"
child = subprocess.run([sys.executable, '-B', '-c', child_source, str(outside/'child')], capture_output=True)
result['descendant_code'] = child.returncode
result['descendant_denied'] = b'PermissionError' in child.stderr
result['inside'] = pathlib.Path('inside').read_text()
result['stdout'] = str(sys.stdout)
a = ctypes.WinDLL('advapi32', use_last_error=True)
a.OpenProcessToken.argtypes = [ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_void_p)]
a.GetTokenInformation.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_void_p, ctypes.c_ulong, ctypes.POINTER(ctypes.c_ulong)]
k = ctypes.WinDLL('kernel32', use_last_error=True)
k.GetCurrentProcess.restype = ctypes.c_void_p
k.CloseHandle.argtypes = [ctypes.c_void_p]
token = ctypes.c_void_p(); needed = ctypes.c_ulong(); elevated = ctypes.c_ulong()
assert a.OpenProcessToken(k.GetCurrentProcess(), 8, ctypes.byref(token))
try:
    assert a.GetTokenInformation(token, 20, ctypes.byref(elevated), ctypes.sizeof(elevated), ctypes.byref(needed))
    result['elevated'] = elevated.value
finally:
    k.CloseHandle(token)
k.CreateFileW.argtypes = [ctypes.c_wchar_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_void_p]
k.CreateFileW.restype = ctypes.c_void_p
handle = k.CreateFileW(str(outside/'api-new'), 0x40000000, 3, None, 1, 0x80, None)
result['api_error'] = ctypes.get_last_error()
result['api_denied'] = handle == ctypes.c_void_p(-1).value
pathlib.Path('result.json').write_text(json.dumps(result))
print(json.dumps(result))
'''
        self.launch(source, self.outside)
        result = self.result()
        self.assertEqual(result['create']['errno'], 13, result)
        self.assertEqual(result['modify']['errno'], 13, result)
        self.assertTrue(result['api_denied'], result)
        self.assertEqual(result['api_error'], 5, result)
        self.assertEqual(result['inside'], 'allowed')
        self.assertEqual(result['elevated'], 0)
        self.assertNotEqual(result['descendant_code'], 0)
        self.assertTrue(result['descendant_denied'])
        self.assertEqual(sorted(p.name for p in self.outside.iterdir()), ['sentinel'])

    def test_job_retires_restricted_worker_and_descendant(self):
        source = r'''
import pathlib, subprocess, sys, time
subprocess.Popen([sys.executable, '-B', '-c', "import pathlib,time; held=open('held','wb'); pathlib.Path('child-ready').write_text('ready'); time.sleep(60); pathlib.Path('late').write_text('bad')"])
pathlib.Path('parent-ready').write_text('ready')
time.sleep(60)
'''
        self.launch(source)
        deadline = time.monotonic() + 10
        while not (self.work / 'child-ready').exists():
            if self.child.poll() is not None or time.monotonic() >= deadline:
                self.fail((self.work / 'worker.log').read_text(errors='replace'))
            time.sleep(0.02)
        self.job.close()
        self.assertNotEqual(self.child.wait(), 0)
        self.assertFalse((self.work / 'late').exists())
        # Windows refuses this deletion while the descendant owns the open file.
        (self.work / 'held').unlink()

    def test_refuses_unowned_directory(self):
        with self.assertRaises(ValueError):
            W.Worker(self.outside)

    def test_private_station_never_requests_elevation(self):
        import ctypes
        if ctypes.windll.shell32.IsUserAnAdmin():
            self.skipTest('Refusal check requires an ordinary coordinator token')
        with self.assertRaisesRegex(PermissionError, 'existing administrator coordinator'):
            W.Worker(self.work, control=self.base, private_station=True)
        self.assertFalse((self.base / 'appcontainer-profiles.json').exists())

    def test_preselected_identity_requires_our_uuid_namespace(self):
        with self.assertRaisesRegex(ValueError, 'Unrecognized temporary worker identity'):
            W.Worker(self.work, control=self.base, profile_name='unrelated.identity')
        self.assertFalse((self.base / 'appcontainer-profiles.json').exists())

    def test_preselected_existing_identity_is_never_adopted_or_deleted(self):
        self.worker = W.Worker(self.work, control=self.base)
        original = self.worker.profile_path
        other = self.base / 'other'
        other.mkdir()
        (other / 'owner.json').write_text(json.dumps({'root': str(ROOT)}))
        target = other / 'work'
        target.mkdir()
        (target / 'owner.json').write_text(json.dumps({'root': str(ROOT)}))
        with self.assertRaises(OSError):
            W.Worker(target, control=other, profile_name=self.worker.profile_name)
        self.assertTrue(original.is_junction())
        self.assertEqual(W.profiles(other), {})

    def test_linked_root_is_refused_before_acl_changes(self):
        junction = self.base / 'junction'
        subprocess.run(['cmd', '/c', 'mklink', '/J', str(junction), str(self.outside)],
                       check=True, capture_output=True)
        try:
            with self.assertRaises(ValueError):
                W.Worker(junction)
        finally:
            junction.rmdir()

    def test_profile_is_removed_after_controller_is_killed(self):
        controller = r'''
import importlib.util, json, pathlib, sys, time
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path); module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module); return module
root,base,work=map(pathlib.Path,sys.argv[1:])
W=load('worker',root/'tools/windows-worker.py'); S=load('workspace',root/'tools/workspace.py')
worker=W.Worker(work,control=base); job=S.WindowsJob()
child=worker.launch([sys.executable,'-B','-c',"import pathlib,time; held=open('held','wb'); pathlib.Path('ready').write_text('ready'); time.sleep(60)"],dict(__import__('os').environ),job)
(base/'controller-ready').write_text(json.dumps({'profile':str(worker.profile_path)}))
time.sleep(60)
'''
        job = S.WindowsJob()
        process = subprocess.Popen([sys.executable, '-B', '-c', controller,
                                    str(ROOT), str(self.base), str(self.work)],
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        try:
            job.assign(process)
            deadline = time.monotonic() + 10
            while not (self.work / 'ready').exists():
                if process.poll() is not None or time.monotonic() >= deadline:
                    job.close()
                    self.fail(process.communicate(timeout=10)[0].decode(errors='replace'))
                time.sleep(0.02)
            profile = Path(json.loads((self.base / 'controller-ready').read_text())['profile'])
            self.assertTrue(profile.is_junction())
            job.close()
            process.communicate(timeout=10)
            (self.work / 'held').unlink()
            W.recover_profiles(self.base)
            self.assertFalse(profile.exists())
            self.assertFalse(profile.is_junction())
            self.assertEqual(W.profiles(self.base), {})
        finally:
            job.close()
            if process.poll() is None:
                process.kill()
            process.communicate(timeout=10)
            W.recover_profiles(self.base)

    def test_ambiguous_profile_creation_blocks_reuse(self):
        name = 'org.disked.worker.' + 'f' * 32
        W.save_profiles(self.base, {name: {'phase': 'creating', 'target': str(self.work / 'profile')}})
        with self.assertRaisesRegex(ValueError, 'Ambiguous'):
            W.recover_profiles(self.base)
        with self.assertRaisesRegex(S.StorageLimit, 'requires review'):
            S.remove_owned_work(self.base, self.base.parent, 'disked-restricted-test-')
        self.assertTrue(self.sentinel.exists())
        self.assertEqual(W.profiles(self.base)[name]['phase'], 'creating')
        # No OS identity was created; remove only this synthetic journal.
        (self.base / 'appcontainer-profiles.json').unlink()

    def test_profile_retirement_is_idempotent(self):
        self.worker = W.Worker(self.work, control=self.base)
        name = self.worker.profile_name
        profile = self.worker.profile_path
        self.worker.close()
        W.retire_profile(name, self.work / 'profile')
        self.assertFalse(profile.exists())

    def test_worker_identity_and_stdout_are_observable(self):
        source = r'''
import ctypes,json,pathlib,sys
from ctypes import wintypes as T
k=ctypes.WinDLL('kernel32',use_last_error=True); a=ctypes.WinDLL('advapi32',use_last_error=True)
k.GetCurrentProcess.restype=T.HANDLE; k.CloseHandle.argtypes=[T.HANDLE]
a.OpenProcessToken.argtypes=[T.HANDLE,T.DWORD,ctypes.POINTER(T.HANDLE)]
a.GetTokenInformation.argtypes=[T.HANDLE,ctypes.c_int,ctypes.c_void_p,T.DWORD,ctypes.POINTER(T.DWORD)]
handle=T.HANDLE(); assert a.OpenProcessToken(k.GetCurrentProcess(),8,ctypes.byref(handle))
result={}
for name,kind in [('appcontainer',29),('elevated',20)]:
    value=T.DWORD(); needed=T.DWORD(); assert a.GetTokenInformation(handle,kind,ctypes.byref(value),4,ctypes.byref(needed)); result[name]=value.value
k.CloseHandle(handle)
pathlib.Path('result.json').write_text(json.dumps(result))
print('worker-output'); print('worker-error',file=sys.stderr)
'''
        self.launch(source)
        self.assertEqual(self.result(), {'appcontainer': 1, 'elevated': 0})
        # Both streams share the log; retain any interpreter startup diagnostic.
        lines = (self.work / 'worker.log').read_text().splitlines()
        self.assertIn('worker-output', lines)
        self.assertIn('worker-error', lines)


if __name__ == '__main__':
    unittest.main()
