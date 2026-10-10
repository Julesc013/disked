"""Automatic provisional producer relationships; archived facts confer no grant."""
import copy,hashlib,json,sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import specctl as sc
ROOT=Path(__file__).resolve().parents[2]
FIXTURE=ROOT.parent/'tests/evidence/fixtures/verification-contracts.json'
class VerificationSemantics(unittest.TestCase):
    def setUp(self):self.bundle=sc.Bundle(ROOT);self.f=json.loads(FIXTURE.read_text());self.d=self.f['definition'];self.s=self.f['state']
    def validate(self,kind,value):self.bundle.validate('urn:disked:schema:'+kind+':1',value)
    def bad(self,kind,value):
        with self.assertRaises(sc.SpecError):self.validate(kind,value)
    def result(self):
        return dict(scope='recorded-acquired-image-verification',authenticity='not_established',latest_image_state='not_established',source_preservation='not_established',physical_admission=False,mutation_authority=False,request_kind='operation-observation',definition=copy.deepcopy(self.d),definition_digest='sha256:'+hashlib.sha256(sc.acquisition_record_bytes(self.d)).hexdigest(),state=copy.deepcopy(self.s),request_binding={k:v for k,v in self.s['binding'].items() if k not in ['process_id','process_created']})
    def test_archived_valid_definition_state_and_result(self):
        self.validate('verification-worker-definition',self.d);self.validate('verification-worker-state',self.s);self.validate('verification-operation-result',self.result())
    def test_automatic_unsigned_integer_bounds(self):
        for owner,key,value in [('state','sequence',str(2**64)),('state','observed_filetime','0'),('binding','process_id',str(2**32)),('binding','process_created',str(2**64)),('progress','read_bytes',str(2**64))]:
            s=copy.deepcopy(self.s);(s if owner=='state' else s[owner])[key]=value
            with self.subTest(owner=owner,key=key):self.bad('verification-worker-state',s)
    def test_phase_counters_and_retention_relationships(self):
        for alter in [lambda s:s.update(quiescent=False),lambda s:s.update(disposition='running'),lambda s:s['progress'].update(covered_bytes='0'),lambda s:s['retention'].update(bytes='0'),lambda s:s['retention'].update(flush='uncertain'),lambda s:s['outcome'].update(matched_bytes='0')]:
            s=copy.deepcopy(self.s);alter(s);self.bad('verification-worker-state',s)
    def test_definition_raw_bytes_and_nested_digests(self):
        for alter in [lambda d:d.update(request_raw=d['request_raw']+' '),lambda d:d['verification'].update(plan_digest='sha256:'+'0'*64),lambda d:d['case_source']['files'][0]['metadata'].update(bytes='1'),lambda d:d['image_binding']['image']['metadata'].update(bytes=str(2**64))]:
            d=copy.deepcopy(self.d);alter(d);self.bad('verification-worker-definition',d)
    def test_private_store_generation_and_alias(self):
        d=copy.deepcopy(self.d);d['store']['generation']=d['case_source']['store']['generation'];d['store']['ancestors']=d['case_source']['ancestors'];self.bad('verification-worker-definition',d)
    def test_result_requires_exact_retained_request_binding(self):
        for change in [lambda r:r.pop('request_binding'),lambda r:r['request_binding'].update(capture_epoch='capture:'+'0'*32),lambda r:r['state']['binding'].update(verifier=dict(r['state']['binding']['verifier'],source_revision='0'*40))]:
            r=self.result();change(r);self.bad('verification-operation-result',r)
    def test_record_hash_and_event_domains(self):
        row=dict(schema='org.disked.verification-worker-record-prototype/1',state=self.s,previous='0'*64);row['digest']=hashlib.sha256(sc.acquisition_record_bytes(row)).hexdigest()
        self.validate('verification-worker-record',row)
        e=dict(schema='org.disked.event/1',operation_id=self.s['binding']['operation_id'],sequence=self.s['sequence'],type='verify.operation.record',payload=dict(schema='org.disked.verification-operation-event/1',request_id='archived-model',observer_epoch='watch:'+'1'*32,record=row))
        self.validate('verification-operation-event',e)
        for alter in [lambda e:e.update(operation_id='verify-op:'+'0'*32),lambda e:e.update(sequence=str(2**64)),lambda e:e['payload']['record'].update(digest='0'*64),lambda e:e['payload'].update(request_id='')]:
            bad=copy.deepcopy(e);alter(bad);self.bad('verification-operation-event',bad)
    def test_inspection_does_not_promote_attachment_or_verdict(self):
        r=self.result();r.update(collection_validation='passed',attachment_applicability='changed');self.validate('verification-operation-result',r)
        r.pop('collection_validation');self.bad('verification-operation-result',r)
    def test_public_command_requires_six_flags_and_closed_phase(self):
        q=dict(phase='execute',definition=self.d,definition_digest=self.result()['definition_digest'],**{'allow_'+k:True for k in ['case_read','image_read','map_read','store_write','host_effects','private_metadata']});self.validate('verification-command-parameters',q)
        for key in q:
            bad=copy.deepcopy(q);bad.pop(key);self.bad('verification-command-parameters',bad)
        bad=copy.deepcopy(q);bad['allow_private_metadata']=False;self.bad('verification-command-parameters',bad)
    def test_review_must_fit_complete_execute_envelope(self):
        sys.path.insert(0,str(ROOT.parent/'tests/evidence'))
        from verification_budget_fixture import envelope_boundary
        q=envelope_boundary(self.d,sc.acquisition_record_bytes)
        self.validate('verification-worker-definition',q['definition']);self.validate('verification-command-parameters',q)
        self.assertLess(len(sc.acquisition_record_bytes(q['definition'])),65536)
        self.assertEqual(len(sc.acquisition_record_bytes(q)),65500)
        review={k:q[k] for k in ['definition','definition_digest']}
        review.update(phase='prepare',execution_admitted=False,scope='recorded-acquired-image-verification',authenticity='not_established',latest_image_state='not_established',source_preservation='not_established',physical_admission=False,mutation_authority=False)
        self.bad('verification-preparation-result',review)
    def test_cursor_and_resource_revalidation_contradictions(self):
        r=self.result();r['last_sequence']=str(2**64);self.bad('verification-operation-result',r)
        for after in [None,self.s['outcome']['before']]:
            o=copy.deepcopy(self.s['outcome']);o.update(status='unknown',resource_revalidation='changed',after=after);self.bad('acquired-image-verification-outcome',o)
        o=copy.deepcopy(self.s['outcome']);o.update(status='unknown',resource_revalidation='unavailable');self.bad('acquired-image-verification-outcome',o)
