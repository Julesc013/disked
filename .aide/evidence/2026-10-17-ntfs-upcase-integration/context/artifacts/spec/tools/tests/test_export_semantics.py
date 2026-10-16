"""Independent public producer/selection contradictions; synthetic, no ports."""
import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import specctl as sc
from test_report_semantics import state,event
ROOT=Path(__file__).resolve().parents[2]

def unresolved(joined=True):
    v=dict(scope='recorded-acquisition-verification-support-export' if joined else 'recorded-acquisition-case-support-export',authenticity='not_established',request_kind='operation-observation',request_state='unresolved')
    if joined:v.update(custody_authentication='not_established',current_image_state='not_established',power_loss_persistence='not_established')
    else:v['current_image_verification']='not_performed'
    return v

class ExportSemantics(unittest.TestCase):
    def setUp(self):self.bundle=sc.Bundle(ROOT)
    def validate(self,v,joined=True):self.bundle.validate('urn:disked:schema:export-operation-result:'+('2' if joined else '1'),v)
    def reject(self,v,joined=True):
        with self.assertRaises(sc.SpecError):self.validate(v,joined)
    def test_unknown_observation_claims_do_not_establish_completion(self):
        self.validate(unresolved());self.validate(unresolved(False),False)
    def test_strict_producer_versions_are_distinct(self):
        self.reject(unresolved(False));self.reject(unresolved(),False)
    def test_no_new_current_image_or_custody_claim(self):
        for key in ('authenticity','custody_authentication','current_image_state','power_loss_persistence'):
            with self.subTest(key=key):v=unresolved();v[key]='established';self.reject(v)
    def test_unknown_fields_are_not_producer_conformance(self):
        v=unresolved();v['unexpected']=True;self.reject(v)
    def test_observed_state_requires_exact_definition(self):
        v=unresolved();v['state']=state();self.reject(v)
    def test_retained_last_state_also_requires_exact_definition(self):
        v=unresolved();v['last_validated_state']=state();self.reject(v)
    def test_events_cannot_bypass_definition_binding(self):
        v=unresolved();v['events']=[event()];self.reject(v)
    def test_u64_and_cursor_bounds_are_automatic(self):
        for value in ('17',str(2**64),'01'):
            with self.subTest(value=value):v=unresolved();v['last_sequence']=value;self.reject(v)
    def test_collection_pair_is_required_and_prepare_remains_inert(self):
        p=dict(phase='prepare',case_operation_id='image-op:'+'a'*32,case_directory='D:\\synthetic-case',destination='D:\\synthetic-output',state_directory='D:\\synthetic-state')
        schema='urn:disked:schema:export-command-parameters:1'
        self.bundle.validate(schema,p)
        for add in (dict(collection_path='D:\\synthetic-collection'),dict(collection_digest='sha256:'+'b'*64),dict(allow_collection_read=True)):
            with self.subTest(add=add),self.assertRaises(sc.SpecError):self.bundle.validate(schema,dict(p,**add))
        self.bundle.validate(schema,dict(p,collection_path='D:\\synthetic-collection',collection_digest='sha256:'+'b'*64))
    def test_cancellation_requires_actual_observation(self):
        v=unresolved();v['cancellation_request']='too_late';self.reject(v)
