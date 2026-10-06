"""The private producer profile enforces relational and wide-integer bounds."""
import copy
from pathlib import Path
import sys
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import specctl as sc


class FakeGraphContract(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundle=sc.Bundle(Path(__file__).resolve().parents[2])

    def sample(self):
        value=dict(schema='org.disked.graph/1',capture_id='fake:1',nodes=[dict(id='fake:a@1',kind='block-device',observation_refs=[],properties=dict(identity='fixture:a',media_generation='1',label='A\n磁盘',state='current',capacity_bytes=str(sc.U64_MAX),aliases=[],scope='fake-only'))],edges=[],omissions=[])
        return self.rehash(value)

    def rehash(self,value):
        value['revision']=sc.digest_bytes(sc.fake_graph_bytes({k:v for k,v in value.items() if k!='revision'}));return value

    def validate(self,value):self.bundle.validate('urn:disked:schema:fake-graph:1',value)

    def test_revision_encoding_binds_exact_observations(self):
        self.assertEqual(b'"a\\u000a\\u0009/\\\\\\""',sc.fake_graph_bytes('a\n\t/\\"'))
        value=self.sample();self.validate(value)
        value['nodes'][0]['properties']['label']='different'
        with self.assertRaisesRegex(sc.SpecError,'revision mismatch'):self.validate(value)
        self.validate(self.rehash(value))

    def test_unknown_capacity_is_not_zero_and_current_needs_capacity(self):
        value=self.sample();p=value['nodes'][0]['properties'];p['capacity_bytes']=None
        with self.assertRaises(sc.SpecError):self.validate(self.rehash(value))
        for state in ['denied','stale','unknown']:
            p['state']=state;self.validate(self.rehash(value))

    def test_invalid_unicode_is_a_typed_contract_error(self):
        value=self.sample();value['nodes'][0]['properties']['label']='\ud800'
        with self.assertRaisesRegex(sc.SpecError,'Invalid Unicode'):self.validate(value)

    def test_u64_and_utf8_byte_bounds_apply_by_schema_identity(self):
        for field,item in [('capacity_bytes',str(sc.U64_MAX+1)),('media_generation',str(sc.U64_MAX+1)),('media_generation','0'),('identity','磁'*86),('label','磁'*1366)]:
            value=self.sample();value['nodes'][0]['properties'][field]=item
            with self.subTest(field=field),self.assertRaises(sc.SpecError):self.validate(self.rehash(value))
        value=self.sample();value['capture_id']='fake:'+str(sc.U64_MAX+1)
        with self.assertRaises(sc.SpecError):self.validate(self.rehash(value))

    def test_graph_relationships_remain_checked(self):
        value=self.sample();value['edges']=[dict(from_='fake:a@1',to='missing',kind='ref')]
        value['edges'][0]['from']=value['edges'][0].pop('from_')
        with self.assertRaisesRegex(sc.SpecError,'Dangling'):self.validate(self.rehash(value))
        value['edges'][0]['to']='fake:a@1';self.validate(self.rehash(value))
        value['nodes'].append(copy.deepcopy(value['nodes'][0]))
        with self.assertRaises(sc.SpecError):self.validate(self.rehash(value))
