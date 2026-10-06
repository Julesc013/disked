import copy
import hashlib
import unittest
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import specctl as sc

class FakeOperation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bundle=sc.Bundle(Path(__file__).resolve().parents[2])

    def initial(self):
        ident='fake-op:'+'1'*32
        return dict(schema='org.disked.fake-operation/1',scope='fake-only',
            binding=dict(operation_id=ident,attempt_id=ident+':attempt:1',worker_epoch='worker:'+'2'*32,
                fixture_id='fake:complete',host_id='3'*64,source_revision='4'*40,input_digest='sha256:'+'5'*64,
                image_digest='6'*64,process_id='123',process_created='456',provider_id='provider.fake.bootstrap/1',
                target_profile='windows.nt10.x64.win32'),sequence='1',phase='pending',logical_state='pending',
            attempt_state='prepared',effect_certainty='not_started',cancellation='not_requested',recovery='unnecessary',
            outcome=None,synthetic_effect_count='0',last_event='initialized')

    def validate(self,value):
        self.bundle.validate('urn:disked:schema:fake-operation:1',value)

    def test_valid_initial_and_cancelled_checkpoint(self):
        value=self.initial();self.validate(value)
        value.update(sequence='3',phase='finished',logical_state='completed',attempt_state='finished',
            cancellation='acknowledged',outcome='cancelled',last_event='cancel_acknowledged')
        self.validate(value)

    def test_bounded_identity_fields_and_sequence_dispatch(self):
        for field,replacement in [('sequence','18446744073709551616'),('sequence','64')]:
            value=self.initial();value[field]=replacement
            with self.assertRaises(sc.SpecError):self.validate(value)
        for field,replacement in [('process_id','4294967296'),('process_created','18446744073709551616'),('attempt_id','fake-op:'+'0'*32+':attempt:1')]:
            value=self.initial();value['binding'][field]=replacement
            with self.assertRaises(sc.SpecError):self.validate(value)

    def test_individually_valid_fields_do_not_allow_contradictions(self):
        for field,replacement in [('outcome','succeeded'),('effect_certainty','observed'),('cancellation','acknowledged'),
                                  ('last_event','verified'),('synthetic_effect_count','1'),('recovery','required')]:
            value=self.initial();value[field]=replacement
            with self.assertRaises(sc.SpecError):self.validate(value)

    def test_record_hash_and_nested_semantics(self):
        record=dict(schema='org.disked.fake-operation-record/1',state=self.initial(),previous='0'*64)
        record['digest']=hashlib.sha256(sc.fake_graph_bytes(record)).hexdigest()
        self.bundle.validate('urn:disked:schema:fake-operation-record:1',record)
        bad=copy.deepcopy(record);bad['digest']='f'*64
        with self.assertRaises(sc.SpecError):self.bundle.validate('urn:disked:schema:fake-operation-record:1',bad)

        bad=copy.deepcopy(record);bad['state']['sequence']='18446744073709551616'
        with self.assertRaises(sc.SpecError):self.bundle.validate('urn:disked:schema:fake-operation-record:1',bad)

    def test_event_identity_and_nested_record_semantics(self):
        record=dict(schema='org.disked.fake-operation-record/1',state=self.initial(),previous='0'*64)
        record['digest']=hashlib.sha256(sc.fake_graph_bytes(record)).hexdigest()
        event=dict(schema='org.disked.event/1',operation_id=record['state']['binding']['operation_id'],sequence='1',type='fake.operation.record',
            payload=dict(schema='org.disked.fake-operation-event/1',request_id='watch:1',observer_epoch='watch:'+'7'*32,record=record))
        self.bundle.validate('urn:disked:schema:fake-operation-event:1',event)
        for field,value in [('sequence','2'),('sequence','18446744073709551616'),('operation_id','fake-op:'+'0'*32)]:
            bad=copy.deepcopy(event);bad[field]=value
            with self.assertRaises(sc.SpecError):self.bundle.validate('urn:disked:schema:fake-operation-event:1',bad)
        bad=copy.deepcopy(event);bad['payload']['record']['state']['logical_state']='completed'
        with self.assertRaises(sc.SpecError):self.bundle.validate('urn:disked:schema:fake-operation-event:1',bad)

    def test_watch_cursor_relationships_and_budget(self):
        base=dict(operation_id='fake-op:'+'1'*32,state_directory='C:\\Fixture')
        self.bundle.validate('urn:disked:schema:command-watch-parameters:1',base)
        cursor=dict(base,after_sequence='2',worker_epoch='worker:'+'2'*32,after_digest='3'*64,follow_ms='2000')
        self.bundle.validate('urn:disked:schema:command-watch-parameters:1',cursor)
        for bad in [dict(base,after_sequence='1'),dict(base,follow_ms='2001'),dict(base,after_sequence='18446744073709551616'),dict(cursor,snapshot=True),dict(base,after_digest='3'*64)]:
            with self.assertRaises(sc.SpecError):self.bundle.validate('urn:disked:schema:command-watch-parameters:1',bad)

if __name__=='__main__':unittest.main()
