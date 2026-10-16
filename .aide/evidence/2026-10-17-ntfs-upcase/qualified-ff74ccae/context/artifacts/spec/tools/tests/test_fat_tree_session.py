"""Tree-session parameter relations; these do not qualify native behavior."""
import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from specctl import Bundle,SpecError

class TreeSessionSchema(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundle=Bundle()
    def validate(self,v):self.bundle.validate('urn:disked:schema:command-fat-tree-parameters:1',v)
    def test_phase_relationships(self):
        self.validate({})
        self.validate(dict(phase='open',path='fixture',volume_offset='0',volume_bytes='512'))
        sid='fat-tree:'+'a'*32+':1'
        for phase in ('next','status','cancel','close'):self.validate(dict(phase=phase,session_id=sid))
        self.validate(dict(phase='read',session_id=sid,page_sequence='1',byte_offset='0',byte_count='196608'))
        for value in [dict(phase='open'),dict(phase='next'),dict(session_id=sid),dict(phase='status',session_id=sid,path='fixture'),dict(phase='read',session_id=sid)]:
            with self.subTest(value=value),self.assertRaises(SpecError):self.validate(value)
    def test_bounded_quantities_and_range(self):
        for key,bad in [('volume_offset',str(2**64)),('fat_copy',str(2**32)),('page_records','1025'),('page_events','513'),('page_reads','513'),('page_read_bytes','4095'),('page_output_bytes','65537'),('bitmap_bytes','67108865'),('queued_directories','65537'),('depth','1025')]:
            with self.subTest(key=key),self.assertRaises(SpecError):self.validate(dict(phase='open',path='fixture',volume_bytes='512',volume_offset='0',**{key:bad}) if key!='volume_offset' else dict(phase='open',path='fixture',volume_bytes='512',volume_offset=bad))
        with self.assertRaises(SpecError):self.validate(dict(phase='open',path='fixture',volume_offset=str(2**64-1),volume_bytes='512'))
    def test_identifier_and_read_bounds(self):
        prefix='fat-tree:'+'a'*32+':'
        self.validate(dict(phase='status',session_id=prefix+str(2**64-1)))
        for serial in ('0','01',str(2**64)):
            with self.subTest(serial=serial),self.assertRaises(SpecError):self.validate(dict(phase='status',session_id=prefix+serial))
        for key,value in [('page_sequence','0'),('byte_offset',str(2**64)),('byte_count','0'),('byte_count','196609')]:
            p=dict(phase='read',session_id=prefix+'1',page_sequence='1',byte_offset='0',byte_count='1');p[key]=value
            with self.subTest(key=key,value=value),self.assertRaises(SpecError):self.validate(p)
    def test_stream_budget_relations(self):
        value=dict(phase='scan',path='fixture',volume_offset='0',volume_bytes='512',max_pages='65536',idle_ms='30000')
        self.validate(value)
        for key,bad in [('max_pages','0'),('max_pages','65537'),('idle_ms','0'),('idle_ms','30001')]:
            p=dict(value);p[key]=bad
            with self.subTest(key=key,bad=bad),self.assertRaises(SpecError):self.validate(p)
        value['phase']='open'
        with self.assertRaises(SpecError):self.validate(value)

if __name__=='__main__':unittest.main()
