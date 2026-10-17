"""Refusal checks for storage qualification; no provisioning or elevation here."""
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

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

    @unittest.skipUnless(os.name == 'nt' and shutil.which('pwsh.exe'), 'PowerShell 7 on Windows')
    def test_setup_rejects_ungranted_size_before_effects(self):
        result = subprocess.run([shutil.which('pwsh.exe'), '-NoProfile', '-File',
                                 str(ROOT / 'tools/capped-scratch.ps1'), '-SizeMiB', '256'],
                                capture_output=True, timeout=15)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(b'ValidateSet', result.stderr)


if __name__ == '__main__':
    unittest.main()
