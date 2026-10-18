"""Owned temporary-fixture policy; actual AppContainer access is a native gate."""
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location('fixture_temp', ROOT/'tests/support/tempdir.py')
F = importlib.util.module_from_spec(spec)
spec.loader.exec_module(F)

class Tests(unittest.TestCase):
    def setUp(self):
        self.outer = tempfile.TemporaryDirectory(prefix='disked-temp-policy-')
        self.addCleanup(self.outer.cleanup)
        self.base = Path(self.outer.name).resolve()
        self.work = self.base/'work'
        self.parent = self.work/'temporary'
        self.parent.mkdir(parents=True)
        (self.work/'owner.json').write_text(json.dumps(dict(root=str(ROOT))))
        for patch in (mock.patch.dict(os.environ, DISKED_WORK_ROOT=str(self.work)),
                      mock.patch.object(F.tempfile,'gettempdir',return_value=str(self.parent))):
            patch.start()
            self.addCleanup(patch.stop)

    def test_ordinary_process_preserves_standard_tempfile_behavior(self):
        with mock.patch.object(F,'_is_appcontainer',return_value=False):
            directory = F.temporary_directory(prefix='ordinary-')
        self.assertIsInstance(directory, tempfile.TemporaryDirectory)
        directory.cleanup()

    def test_inherited_directory_writes_and_removes_only_its_own_root(self):
        sentinel = self.parent/'other-project'
        sentinel.write_bytes(b'preserve')
        with mock.patch.object(F,'_is_appcontainer',return_value=True):
            directory = F.temporary_directory(prefix='fixture-')
        with directory as name:
            self.assertEqual(Path(name).parent,self.parent)
            (Path(name)/'generated.img').write_bytes(b'fixture bytes')
        self.assertFalse(Path(directory.name).exists())
        directory.cleanup()
        self.assertEqual(sentinel.read_bytes(),b'preserve')

    def test_external_parent_is_refused(self):
        with mock.patch.object(F,'_is_appcontainer',return_value=True), mock.patch.object(F.tempfile,'gettempdir',return_value=str(self.base)):
            with self.assertRaisesRegex(ValueError,'outside'): F.temporary_directory(prefix='fixture-')

    def test_wrong_source_marker_is_refused(self):
        (self.work/'owner.json').write_text(json.dumps(dict(root=str(self.base/'other-source'))))
        with mock.patch.object(F,'_is_appcontainer',return_value=True):
            with self.assertRaisesRegex(ValueError,'another source'): F.temporary_directory(prefix='fixture-')

    def test_replaced_directory_is_preserved(self):
        with mock.patch.object(F,'_is_appcontainer',return_value=True):
            directory = F.temporary_directory(prefix='fixture-')
        path = Path(directory.name)
        path.rename(self.parent/'original')
        path.mkdir()
        (path/'other-data').write_bytes(b'preserve')
        with self.assertRaisesRegex(ValueError,'identity changed'): directory.cleanup()
        self.assertEqual((path/'other-data').read_bytes(),b'preserve')

    def test_prefix_cannot_escape_the_parent(self):
        with mock.patch.object(F,'_is_appcontainer',return_value=True):
            for prefix in ('../other', 'C:\\other', '', 'null\0'):
                with self.subTest(prefix=prefix), self.assertRaises(ValueError): F.temporary_directory(prefix=prefix)

    def test_linked_parent_is_refused(self):
        target = self.base/'elsewhere'
        self.parent.rename(target)
        if os.name == 'nt':
            result = subprocess.run(['cmd.exe','/d','/c','mklink','/J',str(self.parent),str(target)],capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0,result.stderr)
        else:
            self.parent.symlink_to(target,target_is_directory=True)
        try:
            with mock.patch.object(F,'_is_appcontainer',return_value=True):
                with self.assertRaisesRegex(ValueError,'Linked'): F.temporary_directory(prefix='fixture-')
        finally:
            self.parent.rmdir() if os.name == 'nt' else self.parent.unlink()

    def test_token_query_failure_is_not_a_fallback(self):
        with mock.patch.object(F,'_is_appcontainer',side_effect=OSError('unverified token')):
            with self.assertRaises(OSError): F.temporary_directory(prefix='fixture-')
