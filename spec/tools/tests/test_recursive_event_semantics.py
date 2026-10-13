"""Recursive emitted event shape/relationships; no native authority claims."""
import copy, hashlib, sys, unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import specctl as sc
ROOT=Path(__file__).resolve().parents[2]
URI='urn:disked:schema:fat-tree-operation-event-prototype:1'


def event():
    w=dict(schema='org.disked.fat-tree-extraction-worker-observation/1',admitted=True,
        attempt_id='fat-tree-write-attempt:'+'a'*32,cancellation_requested=False,capture_epoch='17',
        claims=dict(compiled_effects_capable=True,durable_reconnect=False,live_namespace=False,
                    mutation_authority=False,physical_admission=False),code_sha256='b'*64,
        dependencies_retained=True,diagnostic=None,effects_possible=False,grant_sent=False,
        observer_epoch='observer:'+'c'*32,outcome=None,phase='prepared',
        preparation=dict(definition_digest='sha256:'+'d'*64),progress_pulse='1',request_digest='e'*64,
        result=None,retired=False,status='awaiting_grant',
        worker=dict(pid='123',created='1',exit_code='259',observation='running'),worker_epoch='worker:'+'f'*32)
    r=dict(schema='org.disked.fat-tree-state-record-prototype/1',operation_id='tree-op:'+'1'*32,
        review_digest='sha256:'+'2'*64,sequence='0',previous='sha256:'+'0'*64,
        payload=dict(observed_at='1',phase='admitted',worker=w))
    return dict(schema='org.disked.event/1',operation_id=r['operation_id'],sequence='1',
        type='fat.tree.operation.record',payload=dict(schema='org.disked.fat-tree-operation-event-prototype/1',
        request_id='fixture',observer_epoch='watch:'+'3'*32,worker_epoch=w['worker_epoch'],
        review_digest=r['review_digest'],header_digest='sha256:'+'4'*64,
        sequence_domain='fat-tree-control-record-index-plus-one',record_digest=digest(r),record=r))


def digest(record):return 'sha256:'+hashlib.sha256(sc.acquisition_record_bytes(record)+b'\n').hexdigest()


class RecursiveEventSemantics(unittest.TestCase):
    def setUp(self):self.bundle=sc.Bundle(ROOT)

    def test_automatic_valid_record_and_snapshot_producers(self):
        for kind in ('fat.tree.operation.record','fat.tree.operation.snapshot'):
            value=event();value['type']=kind;self.bundle.validate(URI,value)

    def test_numeric_bindings_digest_and_request_bytes_are_automatic(self):
        for path,value in [('sequence','0'),('sequence','18446744073709551616'),
            ('payload.request_id','\u00e9'*100),('payload.request_id','bad\0value'),
            ('payload.record_digest','sha256:'+'0'*64),('payload.worker_epoch','worker:'+'0'*32),
            ('payload.record.sequence','1'),('payload.record.payload.observed_at','0'),
            ('payload.record.payload.worker.capture_epoch',str(2**64)),
            ('payload.record.payload.worker.worker.pid','0'),
            ('payload.record.payload.worker.worker.exit_code',str(2**32)),
            ('payload.record.payload.worker.dependencies_retained',False),
            ('payload.record.payload.worker.grant_sent',True)]:
            v=event();target=v;parts=path.split('.')
            for key in parts[:-1]:target=target[key]
            target[parts[-1]]=value
            if path.startswith('payload.record.'):v['payload']['record_digest']=digest(v['payload']['record'])
            with self.subTest(path=path),self.assertRaises(sc.SpecError):self.bundle.validate(URI,v)

    def test_producer_additions_and_frame_overflow_are_refused(self):
        for target in ('outer','payload','record','worker'):
            v=event();p=v['payload'];r=p['record']
            destination={'outer':v,'payload':p,'record':r,'worker':r['payload']['worker']}[target]
            destination['new_field']=True
            p['record_digest']=digest(r)
            with self.subTest(target=target),self.assertRaises(sc.SpecError):self.bundle.validate(URI,v)
        v=event();v['payload']['record']['payload']['worker']['diagnostic']='x'*17000
        v['payload']['record_digest']=digest(v['payload']['record'])
        with self.assertRaises(sc.SpecError):self.bundle.validate(URI,v)


if __name__=='__main__':unittest.main()
