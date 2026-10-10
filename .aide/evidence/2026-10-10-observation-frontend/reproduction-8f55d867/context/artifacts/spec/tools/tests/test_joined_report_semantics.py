"""Independent strict producer relationships; entirely synthetic, no I/O grant."""
import copy,hashlib,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import specctl as sc
from test_report_semantics import state
ROOT=Path(__file__).resolve().parents[2]
OUTCOME='urn:disked:schema:acquisition-verification-export-outcome:1'

def outcome():
    output=dict(schema='org.disked.report-export-outcome-prototype/1',status='completed',diagnostic=None,phase='completed',output_state='created',submitted_bytes='12',written_bytes='12',read_bytes='12',verified_bytes='12',flush='api_confirmed',uncertain_effect=False,worker_exit='unobserved',physical_backing_qualified=False,power_loss_persistence='not_established',source_preservation='not_established',authenticity='not_established')
    return dict(schema='org.disked.acquisition-verification-export-outcome-prototype/1',status='completed',diagnostic=None,source_checks='4',source_observations=dict(case=dict(state='matched',check_sequence='3'),collection=dict(state='matched',check_sequence='4')),output=output,scope='recorded-acquisition-verification-support-export',authenticity='not_established',custody_authentication='not_established',current_image_state='not_established',power_loss_persistence='not_established')

class JoinedReportSemantics(unittest.TestCase):
    def setUp(self):self.bundle=sc.Bundle(ROOT)
    def reject(self,value):
        with self.assertRaises(sc.SpecError):self.bundle.validate(OUTCOME,value)
    def test_exact_completed_producer(self):self.bundle.validate(OUTCOME,outcome())
    def test_identity_dispatch_enforces_u64_and_visit_budget(self):
        for value in (str(2**64),'257','-1','01'):
            with self.subTest(value=value):v=outcome();v['source_checks']=value;self.reject(v)
    def test_roles_require_last_adjacent_positions(self):
        for role,value in (('case','1'),('case','4'),('collection','2'),('collection','3'),('case',str(2**64))):
            with self.subTest(role=role,value=value):v=outcome();v['source_observations'][role]['check_sequence']=value;self.reject(v)
    def test_completed_requires_initial_and_final_pairs(self):
        v=outcome();v['source_checks']='2';v['source_observations']['case']['check_sequence']='1';v['source_observations']['collection']['check_sequence']='2';self.reject(v)
        for value in ('changed','unresolved','not_observed'):
            v=outcome();v['source_observations']['case']['state']=value;self.reject(v)
    def test_completed_requires_exact_verified_output(self):
        v=outcome();v['diagnostic']='unresolved';self.reject(v)
        for change in (dict(submitted_bytes='0',written_bytes='0',read_bytes='0',verified_bytes='0'),dict(verified_bytes='11'),dict(written_bytes=None),dict(flush='uncertain'),dict(uncertain_effect=True),dict(output_state='not_created'),dict(diagnostic='unresolved')):
            with self.subTest(change=change):v=outcome();v['output'].update(change);self.reject(v)
    def test_unknown_does_not_mean_completed(self):
        v=outcome();v['status']='unknown';self.reject(v)
        v['output'].update(status='failed',phase='write',output_state='uncertain',uncertain_effect=True,written_bytes=None,read_bytes='0',verified_bytes='0');self.bundle.validate(OUTCOME,v)
    def test_zero_visits_are_unobserved_with_no_output(self):
        v=outcome();v.update(status='refused',source_checks='0');v['source_observations']={k:dict(state='not_observed',check_sequence='0') for k in ('case','collection')};v['output'].update(status='refused',phase='admission',output_state='not_created',submitted_bytes='0',written_bytes='0',read_bytes='0',verified_bytes='0',flush='not_attempted');self.bundle.validate(OUTCOME,v)
        v['source_observations']['case']['state']='matched';self.reject(v)
    def test_unknown_fields_scope_and_rehashed_record_contradictions(self):
        for changes in (dict(unexpected=True),dict(scope='recorded-acquisition-case-support-export'),dict(custody_authentication='authenticated')):
            v=outcome();v.update(changes);self.reject(v)
        # Rehashing a well-formed row cannot repair its contradictory outcome.
        s=state();s.update(sequence='3',phase='finished',quiescent=True,effect_certainty='observed',outcome=outcome());s['outcome']['source_observations']['case']['state']='changed'
        r=dict(schema='org.disked.report-worker-record-prototype/2',state=s,previous='1'*64);r['digest']=hashlib.sha256(sc.acquisition_record_bytes(r)).hexdigest()
        with self.assertRaises(sc.SpecError):self.bundle.validate('urn:disked:schema:report-worker-record:2',r)
    def test_diagnostic_byte_bound_is_distinct_from_character_length(self):
        v=outcome();v.update(status='failed',diagnostic='é'*129);self.reject(v)
        v['diagnostic']='é'*128;self.bundle.validate(OUTCOME,v)
        v['output'].update(status='failed',diagnostic='é'*129);self.reject(v)
