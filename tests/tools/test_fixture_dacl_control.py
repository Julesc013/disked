"""Coordinator metadata boundaries; native permission changes run only in guest."""
import copy
import importlib.util
from pathlib import Path
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
spec=importlib.util.spec_from_file_location('fixture_control',ROOT/'.aide/evidence/2026-10-18-ordinary-worker/fixture-dacl.py')
control=importlib.util.module_from_spec(spec);spec.loader.exec_module(control)
NONCE='a'*32


class FixtureControlTests(unittest.TestCase):
    def hold(self):
        return dict(nonce=NONCE,request_id='b'*32,fixture_id='c'*32,action='hold',
                    path='R:\\owned\\temp\\source.bin',volume='17',file_id='d'*32,directory=False)

    def test_exact_identity_and_action_fields(self):
        good=self.hold();self.assertEqual('hold',control.validate_request(good,NONCE))
        for key,value in [('nonce','f'*32),('request_id','b'*31),('fixture_id','C'*32),
                          ('directory',1),('volume','01'),('volume',str(2**64)),
                          ('file_id','z'*32),('path','x'*1025)]:
            with self.subTest(key=key,value=value):
                row=copy.deepcopy(good);row[key]=value
                with self.assertRaises(ValueError):control.validate_request(row,NONCE)
        row=dict(good,descriptor='D:(A;;FA;;;WD)')
        with self.assertRaises(ValueError):control.validate_request(row,NONCE)

    def test_no_arbitrary_permission_or_restore_path(self):
        base=dict(nonce=NONCE,request_id='b'*32,fixture_id='c'*32)
        for mode in ('denied','metadata_only'):
            self.assertEqual('narrow',control.validate_request(dict(base,action='narrow',mode=mode),NONCE))
        for mode in ('full_control','D:(A;;FA;;;WD)',None):
            with self.assertRaises(ValueError):control.validate_request(dict(base,action='narrow',mode=mode),NONCE)
        self.assertEqual('restore',control.validate_request(dict(base,action='restore'),NONCE))
        with self.assertRaises(ValueError):control.validate_request(dict(base,action='restore',path='C:\\outside'),NONCE)

    def test_only_existing_descendants_of_exact_temp_root(self):
        with tempfile.TemporaryDirectory(prefix='disked-fixture-control-') as name:
            root=Path(name).resolve();temp=root/'temp';temp.mkdir();source=temp/'source.bin';source.write_bytes(b'owned')
            sibling=root/'temp-other';sibling.mkdir();other=sibling/'source.bin';other.write_bytes(b'outside')
            self.assertEqual(source,control.fixture_path(str(source),temp))
            for path in (root,temp,other,temp/'..'/'temp-other'/'source.bin',Path('relative.bin'),temp/'source.bin:stream'):
                with self.subTest(path=path),self.assertRaises((ValueError,FileNotFoundError)):
                    control.fixture_path(str(path),temp)
            self.assertEqual(b'outside',other.read_bytes())

    def test_network_and_device_paths_rejected_before_filesystem_lookup(self):
        temp=Path('R:/owned/temp')
        for path in ('\\\\server\\share\\source','\\\\.\\PhysicalDrive0','C:\\outside\\source'):
            with self.subTest(path=path),self.assertRaises(ValueError):control.fixture_path(path,temp)


if __name__=='__main__':unittest.main()
