"""Synthetic version/resource contradictions; declarations are not execution evidence."""
import copy,hashlib,json
from pathlib import Path
import sys,unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from specctl import Bundle,SpecError

ROOT=Path(__file__).resolve().parents[3]
encode=lambda v:json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
digest=lambda v:'sha256:'+hashlib.sha256(encode(v)).hexdigest()
class LogicalVerificationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.bundle=Bundle();cls.raw=json.loads((ROOT/'tests/evidence/fixtures/verification-contracts.json').read_bytes())['definition']
    def definition(self):
        d=copy.deepcopy(self.raw);plan=d['verification']['plan'];plan['schema']='org.disked.acquisition-plan-prototype/2'
        source=plan['resources']['source'];backing=copy.deepcopy(source);backing['end']='1048576';plan['resources']['backing']=backing
        source['identity']='synthetic-logical-file';source['aliases']=['synthetic-logical-file']
        selector=dict(kind='fat-file',volume_offset='0',volume_bytes='1048576',fat_copy='0',node_id='1',expected_file_bytes=plan['bytes'],metadata_digest='sha256:'+'a'*64)
        plan['logical_source']=selector;d['verification']['schema']='org.disked.acquired-image-verification-definition-prototype/2';d['schema']='org.disked.verification-worker-definition-prototype/2'
        h=json.loads(d['request_raw']);h['definition']['schema']='org.disked.acquisition-worker-definition/2';h['definition']['plan']=copy.deepcopy(plan);h['definition']['request']['logical_source']=copy.deepcopy(selector)
        self.rebind(d,h)
        return d
    def rebind(self,d,h):
        h['definition_digest']=h['grant']['definition_digest']=digest(h['definition']);raw=encode(h);d['request_raw']=raw.decode()
        d['case_source']['files'][0]['metadata']['bytes']=str(len(raw));d['case_source']['files'][0]['digest']='sha256:'+hashlib.sha256(raw).hexdigest()
        d['verification']['plan_digest']=digest(d['verification']['plan']);d['verification_digest']=digest(d['verification'])
    def test_strict_producers_and_exact_compatible_reader_dispatch(self):
        d=self.definition();self.bundle.validate('urn:disked:schema:verification-worker-definition:2',d)
        self.bundle.validate('urn:disked:schema:verification-definition-selection:2',d)
        self.bundle.validate('urn:disked:schema:verification-definition-selection:2',self.raw)
        with self.assertRaises(SpecError):self.bundle.validate('urn:disked:schema:verification-worker-definition:1',d)
        for bad in [{**d,'schema':'unknown'},{**d,'unexpected_mutation':True}]:
            with self.assertRaises(SpecError):self.bundle.validate('urn:disked:schema:verification-definition-selection:2',bad)
    def test_raw_relabelling_and_selector_mismatch_fail_after_rehashing(self):
        for change in ('version','selector'):
            d=self.definition();h=json.loads(d['request_raw'])
            if change=='version':h['definition']['schema']='org.disked.acquisition-worker-definition/1'
            else:h['definition']['request']['logical_source']['node_id']='0'
            self.rebind(d,h)
            with self.subTest(change=change),self.assertRaises(SpecError):self.bundle.validate('urn:disked:schema:verification-worker-definition:2',d)
    def test_logical_backing_alias_is_semantically_refused_by_schema_identity(self):
        d=self.definition();plan=d['verification']['plan'];plan['resources']['backing']['aliases'].append(plan['resources']['destination']['identity'])
        h=json.loads(d['request_raw']);h['definition']['plan']=copy.deepcopy(plan);self.rebind(d,h)
        with self.assertRaises(SpecError):self.bundle.validate('urn:disked:schema:verification-worker-definition:2',d)
