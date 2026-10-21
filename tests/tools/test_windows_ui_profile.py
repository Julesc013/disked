"""Bound the default-profile copy before running a third-party UI fixture."""
import importlib.util
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

@unittest.skipUnless(os.name=='nt','Windows profile attributes')
class ProfileCopyTests(unittest.TestCase):
    def setUp(self):
        path=Path(__file__).resolve().parents[2]/'.aide/evidence/2026-10-21-windows-reference/ui/profile.py'
        spec=importlib.util.spec_from_file_location('bounded_ui_profile',path)
        self.module=importlib.util.module_from_spec(spec);spec.loader.exec_module(self.module)
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        root=Path(self.temp.name);self.source=root/'default';self.target=root/'copy'
        self.source.mkdir();self.target.mkdir()
        patch=mock.patch.object(self.module,'DEFAULT',self.source);patch.start();self.addCleanup(patch.stop)

    def test_nested_bytes_and_empty_directory_preserved(self):
        (self.source/'empty').mkdir();(self.source/'nested').mkdir()
        (self.source/'nested'/'hive').write_bytes(b'\0profile\xff')
        value=self.module.copy_default(self.target)
        self.assertEqual(value,dict(entries=3,bytes=9,skipped_links=0,skipped_shortcuts=0))
        self.assertTrue((self.target/'empty').is_dir())
        self.assertEqual((self.target/'nested'/'hive').read_bytes(),b'\0profile\xff')

    def test_oversized_file_refused_before_copy(self):
        with (self.source/'large').open('wb') as stream:stream.truncate(8388609)
        with self.assertRaisesRegex(ValueError,'byte bound'):self.module.copy_default(self.target)
        self.assertFalse((self.target/'large').exists())

    def test_aggregate_bound_not_only_individual_files(self):
        for name in ('one','two'):
            with (self.source/name).open('wb') as stream:stream.truncate(4194305)
        with self.assertRaisesRegex(ValueError,'byte bound'):self.module.copy_default(self.target)
        self.assertEqual(len(list(self.target.iterdir())),1)

    def test_entry_limit_includes_empty_directories(self):
        for n in range(513):(self.source/str(n)).mkdir()
        with self.assertRaisesRegex(ValueError,'entry bound'):self.module.copy_default(self.target)
        self.assertEqual(len(list(self.target.iterdir())),512)

    def test_hardlinked_source_refused(self):
        source=self.source/'hive';source.write_bytes(b'not copied twice')
        os.link(source,self.source/'alias')
        with self.assertRaisesRegex(ValueError,'Unexpected'):self.module.copy_default(self.target)
        self.assertEqual(list(self.target.iterdir()),[])

    def test_unused_shell_shortcuts_are_omitted_including_hardlinks(self):
        source=self.source/'one.lnk';source.write_bytes(b'no shell in this fixture')
        os.link(source,self.source/'two.LNK')
        value=self.module.copy_default(self.target)
        self.assertEqual(value['skipped_shortcuts'],2)
        self.assertEqual(value['bytes'],0)
        self.assertEqual(list(self.target.iterdir()),[])

if __name__=='__main__':unittest.main()
