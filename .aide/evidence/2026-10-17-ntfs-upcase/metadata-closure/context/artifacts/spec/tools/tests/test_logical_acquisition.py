"""Cross-field logical/backing footprint and alias contract regressions."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from specctl import Bundle,SpecError

class LogicalAcquisitionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundle=Bundle()
    def value(self):
        roles={}
        for name in ('source','destination','map','host','executable','provider','backing'):
            roles[name]=dict(identity=name,epoch='e1',access='read' if name in ('source','executable','backing') else 'create-write' if name=='destination' else 'create-append' if name=='map' else 'observe',
                             start='0',end='20' if name in ('source','destination') else '4096' if name=='backing' else '0',aliases=[name],failure_domain='fixture',
                             verification='readback-sha256' if name=='destination' else 'ordered-hash-chain' if name=='map' else 'identity-epoch')
        return dict(schema='org.disked.acquisition-plan-prototype/2',capture_epoch='fixture',resources=roles,bytes='20',chunk_bytes='4096',read_policy='ordinary',retry_limit='0',substitution='stop',
                    logical_source=dict(kind='fat-file',volume_offset='0',volume_bytes='4096',fat_copy='0',node_id='1',expected_file_bytes='20',metadata_digest='sha256:'+'a'*64))
    def test_basic_logical_backing_plan(self):
        self.bundle.validate('urn:disked:schema:acquisition-plan-logical-prototype:2',self.value())
    def test_cross_field_and_u64_contradictions_are_rejected_by_identity(self):
        changes=[(('logical_source','expected_file_bytes'),'21'),(('logical_source','node_id'),'128'),
                 (('logical_source','volume_bytes'),'4097'),(('logical_source','volume_offset'),'18446744073709551616'),
                 (('resources','source','end'),'4096'),(('resources','backing','end'),'0'),
                 (('resources','destination','aliases'),['destination','backing']),
                 (('resources','source','identity'),'backing')]
        for path,value in changes:
            with self.subTest(path=path):
                v=copy.deepcopy(self.value());at=v
                for key in path[:-1]:at=at[key]
                at[path[-1]]=value
                with self.assertRaises(SpecError):self.bundle.validate('urn:disked:schema:acquisition-plan-logical-prototype:2',v)
