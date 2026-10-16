"""Contradictory private report conformance models; no native execution claim."""
import copy,hashlib,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import specctl as sc
ROOT=Path(__file__).resolve().parents[2]
def state():
    return dict(schema='org.disked.report-worker-state-prototype/2',binding=dict(operation_id='report-op:'+'a'*32,worker_epoch='worker:'+'b'*32,attempt_id='attempt:'+'c'*32,definition_digest='sha256:'+'d'*64,image_digest='e'*64,host_id='f'*64,process_id='123',process_created='1'),sequence='1',phase='prepared',cancellation_observation='not_observed',effect_certainty='not_started',observed_filetime='1',quiescent=False,outcome=None,receipt=None)
def record(s=None):
    r=dict(schema='org.disked.report-worker-record-prototype/2',state=s or state(),previous='0'*64)
    r['digest']=hashlib.sha256(sc.acquisition_record_bytes(r)).hexdigest();return r
def event(r=None):
    r=r or record();return dict(schema='org.disked.event/1',operation_id=r['state']['binding']['operation_id'],sequence=r['state']['sequence'],type='report.operation.record',payload=dict(schema='org.disked.report-operation-event/1',request_id='model-only',observer_epoch='watch:'+'1'*32,record=r))
class ReportSemantics(unittest.TestCase):
    def setUp(self):self.bundle=sc.Bundle(ROOT)
    def test_valid_prepared_record_and_event(self):
        self.bundle.validate('urn:disked:schema:report-worker-record:2',record());self.bundle.validate('urn:disked:schema:report-operation-event:1',event())
    def test_state_u64_u32_and_nonzero_bounds_are_automatic(self):
        for path,value in [('sequence',str(2**64)),('observed_filetime',str(2**64)),('binding.process_created',str(2**64)),('binding.process_id',str(2**32)),('binding.process_id','0'),('sequence','0')]:
            v=state();parts=path.split('.');target=v if len(parts)==1 else v[parts[0]];target[parts[-1]]=value
            with self.subTest(path=path,value=value),self.assertRaises(sc.SpecError):self.bundle.validate('urn:disked:schema:report-worker-state:2',v)
    def test_active_quiescence_and_first_anchor_contradictions(self):
        for v in [dict(state(),quiescent=True),dict(state(),effect_certainty='observed'),dict(state(),phase='finished')]:
            with self.subTest(value=v),self.assertRaises(sc.SpecError):self.bundle.validate('urn:disked:schema:report-worker-state:2',v)
        r=record();r['previous']='1'*64;r['digest']=hashlib.sha256(sc.acquisition_record_bytes({k:v for k,v in r.items() if k!='digest'})).hexdigest()
        with self.assertRaises(sc.SpecError):self.bundle.validate('urn:disked:schema:report-worker-record:2',r)
    def test_event_identity_sequence_and_record_digest(self):
        for change in [lambda v:v.update(sequence=str(2**64)),lambda v:v.update(operation_id='report-op:'+'0'*32),lambda v:v['payload']['record'].update(digest='0'*64)]:
            v=event();change(v)
            with self.subTest(value=v),self.assertRaises(sc.SpecError):self.bundle.validate('urn:disked:schema:report-operation-event:1',v)
    def test_zero_byte_completed_effect_is_not_qualification(self):
        out=dict(status='completed',source_state='matched',output=dict(status='completed',output_state='created',flush='api_confirmed',uncertain_effect=False,submitted_bytes='0',written_bytes='0',read_bytes='0',verified_bytes='0'))
        with self.assertRaises(sc.SpecError):sc.semantic_validate('acquisition-case-export-outcome',out)
