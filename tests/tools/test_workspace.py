"""Exercise real process cleanup and storage refusal with tiny disposable fixtures."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

TOOL = Path(__file__).resolve().parents[2] / 'tools/workspace.py'
spec = importlib.util.spec_from_file_location('disked_workspace', TOOL)
W = importlib.util.module_from_spec(spec)
spec.loader.exec_module(W)


class WorkspaceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='disked-storage-test-')
        self.root = Path(self.temp.name).resolve()
        self.created_stale = []

    def tearDown(self):
        for path in self.created_stale:
            if path.exists():
                shutil.rmtree(path)
        self.temp.cleanup()

    def run_child(self, source, **kwargs):
        return W.run([sys.executable, '-c', source], self.root, min_free=0,
                     local_limit=4096, poll=0.01, **kwargs)

    def test_policy_caps_cannot_silently_grow(self):
        self.assertLessEqual(W.LOCAL_LIMIT, 32 * 1024 * 1024)
        self.assertLessEqual(W.WORK_LIMIT, 1024 * 1024 * 1024)
        self.assertGreaterEqual(W.MIN_FREE, 20 * 1024 * 1024 * 1024)
        self.assertLessEqual(W.WORK_FILES, 20000)

    def test_aggregate_local_and_planned_bytes(self):
        local = self.root / '.aide-local'
        (local / 'nested').mkdir(parents=True)
        (local / 'a').write_bytes(b'a' * 30)
        (local / 'nested/b').write_bytes(b'b' * 34)
        self.assertEqual(W.check(self.root, local_limit=64, min_free=0)['local_bytes'], 64)
        with self.assertRaises(W.StorageLimit):
            W.check(self.root, planned_bytes=1, local_limit=64, min_free=0)

    def test_free_space_refuses_before_launch(self):
        with mock.patch.object(W.shutil, 'disk_usage', return_value=shutil._ntuple_diskusage(100, 99, 1)):
            with mock.patch.object(W.subprocess, 'Popen') as spawn:
                with self.assertRaises(W.StorageLimit):
                    W.run([sys.executable, '-c', 'pass'], self.root, min_free=2)
                spawn.assert_not_called()

    def test_success_removes_the_actual_child_workspace(self):
        result = self.run_child("import os,pathlib;pathlib.Path('observed-work.txt').write_text(os.environ['DISKED_WORK_ROOT']);pathlib.Path(os.environ['DISKED_WORK_ROOT'],'object.bin').write_bytes(b'x'*8192)")
        observed = Path((self.root / 'observed-work.txt').read_text())
        self.assertEqual(result['exit_code'], 0)
        self.assertTrue(result['workspace_removed'])
        self.assertFalse(observed.exists())

    def test_failed_command_also_removes_workspace(self):
        result = self.run_child("import os,pathlib;pathlib.Path('observed-work.txt').write_text(os.environ['DISKED_WORK_ROOT']);raise SystemExit(7)")
        self.assertEqual((result['status'], result['exit_code']), ('fail', 7))
        self.assertFalse(Path((self.root / 'observed-work.txt').read_text()).exists())

    def test_readonly_generated_output_is_removed(self):
        result = self.run_child("import os,pathlib;w=pathlib.Path(os.environ['DISKED_WORK_ROOT']);pathlib.Path('observed-work.txt').write_text(str(w));p=w/'readonly.obj';p.write_bytes(b'x'*100);p.chmod(0o444)")
        self.assertEqual(result['exit_code'], 0)
        self.assertFalse(Path((self.root / 'observed-work.txt').read_text()).exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows read-only deletion semantics')
    def test_readonly_hardlink_does_not_change_external_sentinel_attributes(self):
        work = self.root / 'owned-work'
        work.mkdir()
        sentinel = self.root / 'keep.txt'
        sentinel.write_text('keep')
        link = work / 'linked.txt'
        os.link(sentinel, link)
        sentinel.chmod(0o444)
        before = sentinel.stat().st_file_attributes
        try:
            with self.assertRaises(W.StorageLimit):
                W.remove_owned_work(work, self.root, 'owned-')
            self.assertEqual(sentinel.read_text(), 'keep')
            self.assertEqual(sentinel.stat().st_file_attributes, before)
        finally:
            sentinel.chmod(0o666)

    def test_storage_overrun_kills_and_cleans(self):
        result = self.run_child("import os,pathlib,time;pathlib.Path('observed-work.txt').write_text(os.environ['DISKED_WORK_ROOT']);pathlib.Path(os.environ['DISKED_WORK_ROOT'],'oversize.bin').write_bytes(b'x'*131072);time.sleep(30)", work_limit=65536)
        self.assertEqual((result['status'], result['exit_code']), ('blocked', 78))
        self.assertIn('budget', result['reason'])
        self.assertGreater(result['peak_work_bytes'], 65536)
        self.assertFalse(Path((self.root / 'observed-work.txt').read_text()).exists())

    def test_interruption_uses_the_same_cleanup(self):
        with mock.patch.object(W.time, 'sleep', side_effect=KeyboardInterrupt):
            result = self.run_child('import time;time.sleep(30)')
        self.assertEqual((result['status'], result['exit_code']), ('blocked', 78))
        self.assertTrue(result['workspace_removed'])

    def stale(self, owner):
        identity = W.hashlib.sha256(str(self.root).encode('utf-8')).hexdigest()[:16]
        path = Path(tempfile.mkdtemp(prefix='disked-work-' + identity + '-', dir=tempfile.gettempdir()))
        (path / 'owner.json').write_text(json.dumps(dict(root=str(owner))))
        (path / 'old.bin').write_bytes(b'x' * 512)
        self.created_stale.append(path)
        return path

    def test_identified_stale_workspace_removed_before_next_run(self):
        stale = self.stale(self.root)
        result = self.run_child('pass')
        self.assertEqual(result['exit_code'], 0)
        self.assertFalse(stale.exists())

    def test_other_owner_is_preserved_and_new_run_refused(self):
        stale = self.stale(self.root / 'other-owner')
        with mock.patch.object(W.subprocess, 'Popen') as spawn:
            with self.assertRaises(W.StorageLimit):
                self.run_child('pass')
            spawn.assert_not_called()
        self.assertTrue((stale / 'old.bin').exists())

    def test_lock_refuses_a_second_process(self):
        lock = self.root / 'single-run.lock'
        source = "import importlib.util,pathlib,sys;s=importlib.util.spec_from_file_location('w',sys.argv[1]);w=importlib.util.module_from_spec(s);s.loader.exec_module(w)\ntry:\n with w.exclusive_run(pathlib.Path(sys.argv[2])): pass\nexcept w.StorageLimit: raise SystemExit(42)"
        with W.exclusive_run(lock):
            p = subprocess.run([sys.executable, '-c', source, str(TOOL), str(lock)], capture_output=True)
            self.assertEqual(p.returncode, 42, p.stderr)

    def test_disked_checkouts_share_actual_campaign_admission(self):
        roots = [self.root / 'checkout-one', self.root / 'checkout-two']
        for root in roots:
            (root / 'spec').mkdir(parents=True)
            (root / 'spec/bundle.json').write_text(json.dumps(dict(bundle_id='org.disked.spec')))
        identity = W.workspace_identity(roots[0])
        self.assertEqual(identity, W.workspace_identity(roots[1]))
        lock = Path(tempfile.gettempdir()) / ('disked-work-' + identity + '-lock')
        source = ("import importlib.util,pathlib,sys;"
                  "s=importlib.util.spec_from_file_location('w',sys.argv[1]);"
                  "w=importlib.util.module_from_spec(s);s.loader.exec_module(w)\n"
                  "try:\n w.run([sys.executable,'-c','pass'],pathlib.Path(sys.argv[2]),min_free=0)\n"
                  "except w.StorageLimit: raise SystemExit(42)")
        with W.exclusive_run(lock):
            p = subprocess.run([sys.executable, '-c', source, str(TOOL), str(roots[1])],
                               capture_output=True)
        self.assertEqual(p.returncode, 42, p.stderr)

    def test_invalid_bundle_cannot_silently_get_another_lock(self):
        (self.root / 'spec').mkdir()
        (self.root / 'spec/bundle.json').write_text('not json')
        with mock.patch.object(W.subprocess, 'Popen') as spawn:
            with self.assertRaises(W.StorageLimit):
                self.run_child('pass')
            spawn.assert_not_called()

    def directory_link(self, link, target):
        try:
            link.symlink_to(target, target_is_directory=True)
        except OSError as error:
            if os.name != 'nt':
                self.skipTest('Symlink unavailable: ' + str(error))
            p = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(target)], capture_output=True)
            if p.returncode:
                self.skipTest('Neither unprivileged symlinks nor junctions available')

    def test_links_are_not_counted_as_owned_storage(self):
        outside = self.root / 'outside'
        outside.mkdir()
        sentinel = outside / 'keep.txt'
        sentinel.write_text('untouched')
        local = self.root / '.aide-local'
        local.mkdir()
        self.directory_link(local / 'link', outside)
        with self.assertRaises(W.StorageLimit):
            W.tree_bytes(local)
        self.assertEqual(W.tree_bytes(local, allow_links=True), 4096)
        with self.assertRaises(W.StorageLimit):
            W.tree_bytes(local, allow_links=True, file_limit=0)
        self.assertEqual(sentinel.read_text(), 'untouched')

    def test_cleanup_refuses_linked_root_and_preserves_target(self):
        target = self.root / 'other-project'
        target.mkdir()
        sentinel = target / 'keep.txt'
        sentinel.write_text('untouched')
        link = self.root / 'owned-link'
        self.directory_link(link, target)
        with self.assertRaises(W.StorageLimit):
            W.remove_owned_work(link, self.root, 'owned-')
        self.assertEqual(sentinel.read_text(), 'untouched')

    def test_broken_link_is_not_mistaken_for_an_absent_workspace(self):
        target = self.root / 'old-target'
        target.mkdir()
        link = self.root / 'owned-link'
        self.directory_link(link, target)
        target.rmdir()
        with self.assertRaises(W.StorageLimit):
            W.tree_bytes(link)
        with self.assertRaises(W.StorageLimit):
            W.remove_owned_work(link, self.root, 'owned-')

    def test_file_count_limit(self):
        for i in range(6):
            (self.root / str(i)).write_bytes(b'')
        with self.assertRaises(W.StorageLimit):
            W.tree_bytes(self.root, file_limit=5)

    def test_empty_directories_also_consume_the_entry_budget(self):
        for i in range(6):
            (self.root / str(i)).mkdir()
        with self.assertRaises(W.StorageLimit):
            W.tree_bytes(self.root, file_limit=5)

    def test_sparse_fixture_counts_allocated_storage(self):
        path = self.root / 'sparse.img'
        with path.open('wb') as f:
            if os.name == 'nt':
                import msvcrt
                api = W.ctypes.WinDLL('kernel32', use_last_error=True)
                api.DeviceIoControl.argtypes = [W.wintypes.HANDLE, W.wintypes.DWORD, W.ctypes.c_void_p,
                    W.wintypes.DWORD, W.ctypes.c_void_p, W.wintypes.DWORD,
                    W.ctypes.POINTER(W.wintypes.DWORD), W.ctypes.c_void_p]
                returned = W.wintypes.DWORD()
                self.assertTrue(api.DeviceIoControl(msvcrt.get_osfhandle(f.fileno()), 0x900c4,
                    None, 0, None, 0, W.ctypes.byref(returned), None))
            f.seek(4 * 1024 * 1024)
            f.write(b'x')
        self.assertEqual(W.tree_bytes(self.root), 4 * 1024 * 1024 + 1)
        self.assertLess(W.tree_bytes(self.root, allocated=True), 4 * 1024 * 1024)

    def cmake_gate(self, work, binary):
        if not shutil.which('cmake'):
            self.skipTest('CMake unavailable')
        module = TOOL.with_suffix('.cmake').as_posix()
        script = self.root / 'gate.cmake'
        script.write_text('set(CMAKE_BINARY_DIR "' + Path(binary).as_posix() + '")\ninclude("' + module + '")\n')
        env = dict(os.environ, DISKED_WORK_ROOT=str(work))
        return subprocess.run(['cmake', '-P', str(script)], cwd=self.root, env=env, capture_output=True, text=True)

    def test_native_configure_refuses_unmanaged_before_compiler_discovery(self):
        if not shutil.which('cmake'):
            self.skipTest('CMake unavailable')
        env = dict(os.environ)
        env.pop('DISKED_WORK_ROOT', None)
        output = self.root / 'refused-build'
        p = subprocess.run(['cmake', '-S', str(TOOL.parents[1]), '-B', str(output)],
                           cwd=self.root, env=env, capture_output=True, text=True)
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('managed development workspace', p.stdout + p.stderr)
        self.assertFalse(list(output.rglob('CMakeCCompiler.cmake')))
        self.assertLess(W.tree_bytes(output), 65536)

    def test_cmake_gate_refuses_work_in_checkout(self):
        work = TOOL.parents[1] / '.aide-local'
        p = self.cmake_gate(work, work / 'build')
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('outside the source checkout', p.stdout + p.stderr)

    def test_cmake_gate_refuses_output_outside_owned_work(self):
        p = self.cmake_gate(self.root / 'work', self.root / 'elsewhere')
        self.assertNotEqual(p.returncode, 0)
        self.assertIn('inside DISKED_WORK_ROOT', p.stdout + p.stderr)

    def test_cmake_gate_accepts_owned_output(self):
        p = self.cmake_gate(self.root / 'work', self.root / 'work/build')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)

    def test_preset_disabled_without_owned_workspace(self):
        if not shutil.which('cmake'):
            self.skipTest('CMake unavailable')
        env = dict(os.environ)
        env.pop('DISKED_WORK_ROOT', None)
        p = subprocess.run(['cmake', '--list-presets'], cwd=TOOL.parents[1], env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertNotIn('windows-bootstrap', p.stdout)
        env['DISKED_WORK_ROOT'] = str(self.root / 'work')
        p = subprocess.run(['cmake', '--list-presets'], cwd=TOOL.parents[1], env=env, capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn('windows-bootstrap', p.stdout)

    @unittest.skipUnless(os.name == 'nt', 'Windows Job Object observation')
    def test_descendant_is_terminated_when_parent_finishes(self):
        source = "import pathlib,subprocess,sys;p=subprocess.Popen([sys.executable,'-c','import time;time.sleep(30)']);pathlib.Path('child.pid').write_text(str(p.pid))"
        result = self.run_child(source)
        self.assertEqual(result['exit_code'], 0)
        pid = int((self.root / 'child.pid').read_text())
        api = W.ctypes.WinDLL('kernel32', use_last_error=True)
        api.OpenProcess.argtypes = [W.wintypes.DWORD, W.wintypes.BOOL, W.wintypes.DWORD]
        api.OpenProcess.restype = W.wintypes.HANDLE
        api.WaitForSingleObject.argtypes = [W.wintypes.HANDLE, W.wintypes.DWORD]
        api.CloseHandle.argtypes = [W.wintypes.HANDLE]
        handle = api.OpenProcess(0x100000, False, pid)
        if handle:
            try:
                self.assertEqual(api.WaitForSingleObject(handle, 3000), 0)
            finally:
                api.CloseHandle(handle)


if __name__ == '__main__':
    unittest.main()
