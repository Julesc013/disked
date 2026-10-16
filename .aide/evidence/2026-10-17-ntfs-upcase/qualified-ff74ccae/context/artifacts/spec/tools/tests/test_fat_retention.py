"""Schema-selected parameter bounds; no runtime qualification."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from specctl import Bundle,SpecError


class FatRetentionSchemas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundle=Bundle()

    def test_identifier_bounds(self):
        schema='urn:disked:schema:command-capture-release-parameters:1'
        prefix='fat-capture:'+'a'*32+':'
        for serial in ('1',str(2**64-1)):self.bundle.validate(schema,dict(capture_id=prefix+serial))
        for serial in ('0','01',str(2**64),'99999999999999999999'):
            with self.subTest(serial=serial),self.assertRaises(SpecError):self.bundle.validate(schema,dict(capture_id=prefix+serial))

    def test_list_read_constraints(self):
        schema='urn:disked:schema:command-capture-inspect-parameters:1';cid='fat-capture:'+'a'*32+':1'
        self.bundle.validate(schema,{})
        self.bundle.validate(schema,dict(phase='list'))
        for offset in ('0',str(2**64-1)):
            for count in ('1','196608'):self.bundle.validate(schema,dict(phase='read',capture_id=cid,byte_offset=offset,byte_count=count))
        for value in [dict(capture_id=cid),dict(phase='release'),dict(phase='read'),dict(phase='list',byte_offset='0'),
            *[dict(phase='read',capture_id=cid,byte_offset='0',byte_count=n) for n in ('0','196609')],
            dict(phase='read',capture_id=cid,byte_offset=str(2**64),byte_count='1')]:
            with self.subTest(value=value),self.assertRaises(SpecError):self.bundle.validate(schema,value)


if __name__=='__main__':unittest.main()
