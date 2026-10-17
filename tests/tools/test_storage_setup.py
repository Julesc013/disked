"""Refusal checks for storage qualification; no provisioning or elevation here."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
definition = importlib.util.spec_from_file_location('disked_storage_proof', ROOT / 'tools/qualify-storage.py')
Q = importlib.util.module_from_spec(definition)
definition.loader.exec_module(Q)


class StorageSetupTests(unittest.TestCase):
    def test_ordinary_filesystem_is_not_a_tiny_capped_volume(self):
        with tempfile.TemporaryDirectory(prefix='disked-cap-refusal-') as directory:
            with self.assertRaisesRegex(ValueError, 'capped filesystem'):
                Q.capped_volume(Path(directory).anchor, 32 * 1024 * 1024)

    def test_directory_on_volume_does_not_prove_its_capacity(self):
        with tempfile.TemporaryDirectory(prefix='disked-cap-refusal-') as directory:
            with self.assertRaises(ValueError):
                Q.capped_volume(directory, 32 * 1024 * 1024)

    def test_metadata_is_bounded_before_json_parse(self):
        with tempfile.TemporaryDirectory(prefix='disked-cap-refusal-') as directory:
            path = Path(directory) / 'state.json'
            path.write_bytes(b' ' * 1025)
            with self.assertRaisesRegex(ValueError, 'Oversized'):
                Q.small_json(path, 1024)

    def test_unknown_option_is_rejected_without_setup(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'tools/qualify-storage.py'),
                                 '--unknown-option'], capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 2)
        self.assertIn(b'unrecognized arguments', result.stderr)

    def test_pending_consent_refuses_before_shell_launch(self):
        records = [{'pid': 123, 'session_id': 1, 'session_query_error': None}]
        with mock.patch.object(Q, 'pending_elevation_requests', return_value=records), \
                mock.patch.object(Q.ctypes, 'WinDLL', create=True,
                                  side_effect=AssertionError('Must not load a launch API')):
            with self.assertRaises(Q.SetupAdmissionBlocked) as caught:
                Q.start_setup(32, elevate=True)
        self.assertEqual(caught.exception.processes, records)

    @unittest.skipUnless(os.name == 'nt', 'Windows process/session snapshot')
    def test_real_pending_snapshot_is_bounded_and_has_no_command_lines(self):
        records = Q.pending_elevation_requests()
        self.assertLessEqual(len(records), 65536)
        for record in records:
            self.assertEqual(set(record), {'pid', 'session_id', 'session_query_error'})
            self.assertGreater(record['pid'], 0)
            self.assertEqual(record['session_id'] is None, record['session_query_error'] is not None)

    @unittest.skipUnless(os.name == 'nt' and shutil.which('pwsh.exe'), 'Windows setup mutex')
    def test_setup_mutex_blocks_a_second_helper_before_storage_changes(self):
        if (str(ROOT).casefold() != 'd:\\projects\\disked\\disked' or
                os.environ.get('COMPUTERNAME', '').casefold() != 'blackglass-win1' or
                os.environ.get('USERNAME', '').casefold() != 'jules'):
            self.skipTest('Fixed local setup grant does not apply to this checkout/user')
        import ctypes
        from ctypes import wintypes as T
        api = ctypes.WinDLL('kernel32', use_last_error=True)
        Q.W.bind(api, 'CreateMutexW', T.HANDLE, ctypes.c_void_p, T.BOOL, T.LPCWSTR)
        Q.W.bind(api, 'WaitForSingleObject', T.DWORD, T.HANDLE, T.DWORD)
        Q.W.bind(api, 'ReleaseMutex', T.BOOL, T.HANDLE)
        Q.W.bind(api, 'CloseHandle', T.BOOL, T.HANDLE)
        handle = Q.W.require(api.CreateMutexW(None, False, 'Global\\DiskEd.CappedScratch'))
        owned = False
        try:
            wait = api.WaitForSingleObject(handle, 0)
            if wait == 0x102:
                self.skipTest('An actual scratch helper already owns its lease')
            self.assertIn(wait, (0, 0x80))
            owned = True
            before = Path('D:/Projects/DiskEd/scratch').exists()
            result = subprocess.run([shutil.which('pwsh.exe'), '-NoProfile', '-File',
                                     str(ROOT / 'tools/capped-scratch.ps1'), '-SizeMiB', '32'],
                                    capture_output=True, timeout=15)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(b'Another bounded scratch setup is active', result.stderr)
            self.assertEqual(Path('D:/Projects/DiskEd/scratch').exists(), before)
        finally:
            if owned:
                Q.W.require(api.ReleaseMutex(handle))
            Q.W.require(api.CloseHandle(handle))

    @unittest.skipUnless(os.name == 'nt' and shutil.which('pwsh.exe'), 'PowerShell 7 on Windows')
    def test_setup_rejects_ungranted_size_before_effects(self):
        result = subprocess.run([shutil.which('pwsh.exe'), '-NoProfile', '-File',
                                 str(ROOT / 'tools/capped-scratch.ps1'), '-SizeMiB', '256'],
                                capture_output=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'ValidateSet', result.stderr)


if __name__ == '__main__':
    unittest.main()
