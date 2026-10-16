"""Independent cursor domains/digests and real detached wait/watch observations."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import time
import threading
import unittest
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'spec/tools'))
import specctl as sc
import test_fat_tree_admission as admission
import test_fat_tree_controller as controller
from test_fat_tree_review import canonical
from test_fat_tree_reconnect import rechain, load

PROBE = None
RESULTS = []


def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()


def invoke(value,error=None):
    run=subprocess.run([str(PROBE)],input=canonical(value),capture_output=True,timeout=15)
    assert not run.stderr,run.stderr
    out=json.loads(run.stdout)
    if error:assert run.returncode==20 and out.get('error')==error,out
    else:assert run.returncode==0 and 'error' not in out,out
    RESULTS.append(dict(input_sha256=sha(canonical(value)),exit_code=run.returncode,result=out))
    return out


def native(root,options=None,wait=None):
    header=json.loads((root/'store/recursive-request.json').read_bytes())
    p=dict(operation_id=header['operation_id'],store=str(root/'store'))
    if wait is None:p['watch']=options or {}
    else:p['wait_ms']=str(wait)
    return invoke(p)


class WatchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.root,inputs,expected=admission.fixture()
        review=admission.prepare(cls.root,inputs)['review']
        row=controller.call(dict(review=review,controller_mode='dispatch'))
        controller.wait_history(cls.root)
        controller.actual_exit(row['observation']['controller'])
        cls.header,cls.history=load(cls.root)
        cls.records=[json.loads(line) for line in cls.history.splitlines()]

    def pure(self,options=None,**extra):
        return invoke(dict(header=self.header,history=self.history,watch=options or {},**extra))

    def test_exact_envelopes_include_admission_and_original_digest_domain(self):
        out=self.pure()
        bundle=sc.Bundle(Path(__file__).resolve().parents[2]/'spec')
        for event in out['events']:
            bundle.validate('urn:disked:schema:fat-tree-operation-event-prototype:1',event)
        self.assertEqual(len(self.records),len(out['events']))
        for i,(event,record) in enumerate(zip(out['events'],self.records)):
            self.assertEqual(str(i+1),event['sequence'])
            self.assertEqual(str(i),event['payload']['record']['sequence'])
            self.assertEqual('fat-tree-control-record-index-plus-one',event['payload']['sequence_domain'])
            self.assertEqual(record,event['payload']['record'])
            self.assertEqual(sha(canonical(record)+b'\n'),event['payload']['record_digest'])
            self.assertEqual(self.header['operation_id'],event['operation_id'])
            self.assertEqual(self.header['review_digest'],event['payload']['review_digest'])
            self.assertEqual(sha(canonical(self.header)),event['payload']['header_digest'])
            self.assertLessEqual(len(canonical(event)),16384)
        self.assertEqual(sha(canonical(self.records[-1])+b'\n'),out['cursor']['last_digest'])


    def test_producer_is_closed_and_checks_rehashed_relationships(self):
        bundle=sc.Bundle(Path(__file__).resolve().parents[2]/'spec')
        uri='urn:disked:schema:fat-tree-operation-event-prototype:1'
        events=self.pure()['events']
        cases=[]
        for path,value in [('extra_observation',True),('payload.extra_observation',True),
            ('sequence','18446744073709551616'),('sequence','2'),
            ('payload.worker_epoch','worker:'+'f'*32),('payload.record_digest','sha256:'+'0'*64),
            ('payload.request_id','\u00e9'*100),('payload.request_id','bad\0id'),
            ('payload.record.payload.worker.progress_pulse','18446744073709551616'),
            ('payload.record.payload.worker.worker.pid','0'),
            ('payload.record.payload.worker.worker.created','0'),
            ('payload.record.payload.worker.worker.exit_code',str(2**32)),
            ('payload.record.payload.worker.dependencies_retained',False),
            ('payload.record.payload.worker.effects_possible',True),
            ('payload.record.payload.phase','observing')]:
            event=copy.deepcopy(events[0]);target=event;parts=path.split('.')
            for key in parts[:-1]:target=target[key]
            target[parts[-1]]=value
            if path.startswith('payload.record.'):
                event['payload']['record_digest']=sha(canonical(event['payload']['record'])+b'\n')
            cases.append((path,event))
        completed=next(e for e in events if e['payload']['record']['payload']['worker']['outcome'] is not None)
        for key,value in [('attempt_id','fat-tree-write-attempt:'+'f'*32),('checkpointed_bytes',str(2**64)),
                          ('source_writes',True),('cancellation_observed',True)]:
            event=copy.deepcopy(completed)
            event['payload']['record']['payload']['worker']['outcome'][key]=value
            event['payload']['record_digest']=sha(canonical(event['payload']['record'])+b'\n')
            cases.append(('outcome.'+key,event))
        for name,event in cases:
            with self.subTest(case=name),self.assertRaises(sc.SpecError):bundle.validate(uri,event)
        # Reader compatibility still accepts additive outer/payload observations;
        # they are outside the current producer's conformance schema.
        additive=copy.deepcopy(events);additive[0]['extra_observation']=True
        additive[0]['payload']['extra_observation']=True
        read=invoke(dict(header=self.header,reader_events=additive))
        self.assertTrue(all(r.get('accepted') for r in read['results']))

    def test_compatible_reader_preserves_extensions_and_refuses_conflicts(self):
        events=self.pure()['events']
        extended=copy.deepcopy(events)
        for e in extended:e['future_observation']={'retained':True};e['payload']['future_label']='data'
        out=invoke(dict(header=self.header,reader_events=extended+[extended[-1]]))
        self.assertTrue(all(r.get('accepted') for r in out['results'][:-1]))
        self.assertFalse(out['results'][-1]['accepted'])
        self.assertTrue(out['cursor']['omitted_prefix_verified'])
        for change in ('digest','sequence','required','worker','observer'):
            corrupt=copy.deepcopy(events[1])
            if change=='digest':corrupt['payload']['record_digest']='sha256:'+'0'*64
            if change=='sequence':corrupt['sequence']='18446744073709551616'
            if change=='required':corrupt['required_features']=['unknown']
            if change=='worker':corrupt['payload']['worker_epoch']='worker:'+'0'*32
            if change=='observer':corrupt['payload']['observer_epoch']='watch:'+'0'*32
            checked=invoke(dict(header=self.header,reader_events=[events[0],corrupt]))
            self.assertIn('error',checked['results'][-1]);self.assertEqual('1',checked['cursor']['sequence'])
        snap=self.pure(dict(snapshot=True))['events']
        checked=invoke(dict(header=self.header,reader_events=snap,snapshot=True))
        self.assertTrue(checked['results'][0]['accepted']);self.assertFalse(checked['cursor']['omitted_prefix_verified'])
        projection=self.pure(dict(snapshot=True),batches=[dict(history=rechain(copy.deepcopy(self.records[:2]))),dict(history=self.history)])
        followed=invoke(dict(header=self.header,reader_events=projection['events'],snapshot=True))
        self.assertTrue(all(r.get('accepted') for r in followed['results']))
        self.assertEqual(str(len(self.records)),followed['cursor']['sequence'])
        changed=copy.deepcopy(snap[0]);changed['payload']['record']['payload']['worker']['outcome']['source_writes']=True
        changed['payload']['record_digest']=sha(canonical(changed['payload']['record'])+b'\n')
        checked=invoke(dict(header=self.header,reader_events=[changed],snapshot=True))
        self.assertIn('error',checked['results'][0]);self.assertEqual('0',checked['cursor']['sequence'])
        changed=copy.deepcopy(snap[0]);changed['payload']['record']['payload']['phase']='admitted'
        changed['payload']['record_digest']=sha(canonical(changed['payload']['record'])+b'\n')
        checked=invoke(dict(header=self.header,reader_events=[changed],snapshot=True))
        self.assertIn('error',checked['results'][0]);self.assertEqual('0',checked['cursor']['sequence'])

    def test_resume_snapshot_and_same_prefix_do_not_duplicate(self):
        prefix=rechain(copy.deepcopy(self.records[:2]))
        out=self.pure(batches=[dict(history=prefix),dict(history=self.history),dict(history=self.history)])
        self.assertEqual(len(self.records),len(out['events']))
        self.assertEqual('2',out['steps'][0]['cursor']['sequence'])
        options=dict(after_sequence='2',after_digest=sha(canonical(self.records[1])+b'\n')[7:],
                     worker_epoch=self.header['process_owner']['worker_epoch'])
        resumed=self.pure(options)
        self.assertEqual([str(i+1) for i in range(2,len(self.records))],[e['sequence'] for e in resumed['events']])
        snapshot=self.pure(dict(snapshot=True))
        self.assertEqual(1,len(snapshot['events']))
        self.assertEqual('fat.tree.operation.snapshot',snapshot['events'][0]['type'])
        self.assertEqual(str(len(self.records)),snapshot['events'][0]['sequence'])

    def test_invalid_options_are_rejected_before_native_paths(self):
        invalid=[(dict(after_sequence='1'),'fat_tree_watch_cursor_incomplete'),
                 (dict(after_sequence='01'),'fat_tree_watch_integer'),
                 (dict(after_sequence='18446744073709551616'),'fat_tree_watch_integer'),
                 (dict(after_sequence='65'),'fat_tree_watch_cursor_ahead'),
                 (dict(follow_ms='2001'),'fat_tree_watch_budget'),
                 (dict(snapshot='yes'),'fat_tree_watch_shape'),
                 (dict(unknown=True),'fat_tree_watch_shape'),
                 (dict(after_digest='0'*64),'fat_tree_watch_cursor_conflict')]
        for options,error in invalid:
            out=invoke(dict(operation_id=self.header['operation_id'],store='unopened-invalid-store',watch=options))
            self.assertEqual('0',out['polls']);self.assertEqual(error,out['diagnostic'],out)
        opts=dict(after_sequence='1',after_digest='0'*64,worker_epoch=self.header['process_owner']['worker_epoch'],snapshot=True)
        out=invoke(dict(operation_id=self.header['operation_id'],store='unopened-invalid-store',watch=opts))
        self.assertEqual('fat_tree_watch_cursor_conflict',out['diagnostic'])

    def test_wrong_digest_epoch_ahead_and_changed_prefix_keep_cursor(self):
        for options,error in [(dict(worker_epoch='worker:'+'0'*32),'fat_tree_watch_epoch'),
            (dict(after_sequence='1',after_digest='0'*64,worker_epoch=self.header['process_owner']['worker_epoch']),'fat_tree_watch_cursor_conflict'),
            (dict(after_sequence='64',after_digest='0'*64,worker_epoch=self.header['process_owner']['worker_epoch']),'fat_tree_watch_cursor_ahead')]:
            out=self.pure(options)
            self.assertEqual(error,out['steps'][0]['error'])
            self.assertFalse(out['events'])
        changed=copy.deepcopy(self.records);changed[0]['payload']['observed_at']=str(int(changed[0]['payload']['observed_at'])+1)
        out=self.pure(batches=[dict(history=rechain(copy.deepcopy(self.records[:2]))),dict(history=rechain(changed))])
        self.assertEqual('fat_tree_watch_cursor_conflict',out['steps'][1]['error'])
        self.assertEqual('2',out['cursor']['sequence'])
        header=copy.deepcopy(self.header);header['controller']['created']=str(int(header['controller']['created'])+1)
        out=self.pure(batches=[dict(history=self.history),dict(header=header,history=self.history)])
        self.assertEqual('fat_tree_watch_header_changed',out['steps'][1]['error'])
        out=self.pure(batches=[dict(history=self.history),dict(history=rechain(copy.deepcopy(self.records[:2])))])
        self.assertEqual('fat_tree_watch_cursor_ahead',out['steps'][1]['error'])

    def test_torn_and_uncertain_histories_have_no_successful_empty_batch(self):
        out=self.pure(batches=[dict(history=self.history+'{"torn"')])
        self.assertEqual('fat_tree_watch_history_unresolved',out['steps'][0]['error'])
        self.assertFalse(out['events'])
        out=self.pure(batches=[dict(history='')])
        self.assertEqual('fat_tree_watch_no_records',out['steps'][0]['error'])
        raw=self.root/'store/recursive-state.ndjson';saved=raw.read_bytes()
        try:
            raw.write_bytes(saved+b'{"torn"')
            out=native(self.root)
            self.assertEqual('unknown',out['status']);self.assertEqual('fat_tree_watch_torn_history',out['diagnostic'])
            self.assertFalse(out['events'])
            self.assertEqual(saved+b'{"torn"',raw.read_bytes())
        finally:raw.write_bytes(saved)

    def test_closed_and_throwing_sinks_do_not_advance_unadmitted_cursor(self):
        out=self.pure(stop_after='2',batches=[dict(history=self.history),dict(history=self.history)])
        self.assertEqual(2,len(out['events']));self.assertEqual('2',out['cursor']['sequence'])
        self.assertTrue(out['cursor']['closed']);self.assertFalse(out['steps'][1]['open'])
        out=self.pure(throw_after='2')
        self.assertEqual('probe_sink_failed',out['steps'][0]['error'])
        self.assertEqual(2,len(out['events']));self.assertEqual('2',out['cursor']['sequence'])
        self.assertTrue(out['cursor']['closed'])

    def test_event_budget_preserves_prior_cursor(self):
        rows=copy.deepcopy(self.records[:2])
        rows[1]['payload']['worker']['diagnostic']='x'*(16292-len(canonical(rows[1])))
        out=self.pure(batches=[dict(history=rechain(rows))])
        self.assertEqual('fat_tree_watch_event_budget',out['steps'][0]['error'])
        self.assertEqual('1',out['cursor']['sequence']);self.assertEqual(1,len(out['events']))

    def test_actual_completed_wait_and_watch_preserve_all_artifacts(self):
        paths=[self.root/'source.img',self.root/'metadata.ndjson',*sorted((self.root/'store').iterdir())]
        before={str(p):p.read_bytes() for p in paths}
        out=native(self.root)
        self.assertEqual('recorded_terminal',out['status'],out)
        self.assertEqual(len(self.records),len(out['events']))
        waited=native(self.root,wait=2000)
        self.assertEqual('recorded_terminal',waited['status'],waited)
        self.assertEqual(1,len(waited['events']))
        self.assertEqual('1',waited['polls'])
        for p in paths:self.assertEqual(before[str(p)],p.read_bytes())

    def test_actual_live_follow_boundary_then_cancel_and_resume(self):
        root,inputs,expected,review=controller.prepared(fault=True)
        source=(root/'source.img').read_bytes()
        caller=controller.call(dict(review=review,controller_mode='dispatch',fixture=dict(worker_fault='execute_wait_cancel')),fault=True)
        controller.wait_history(root,terminal=False)
        out=native(root,dict(follow_ms='100'))
        self.assertEqual('following_boundary',out['status'],out)
        self.assertGreater(int(out['polls']),1);self.assertLessEqual(int(out['polls']),81)
        cursor=out['cursor'];self.assertTrue(out['events'])
        cancelled=controller.inspect(root,cancel=True)
        self.assertEqual('requested',cancelled['cancellation_request'])
        resumed=native(root,dict(follow_ms='2000',after_sequence=cursor['sequence'],
            after_digest=cursor['last_digest'][7:],worker_epoch=cursor['worker_epoch']))
        self.assertEqual('recorded_terminal',resumed['status'],resumed)
        self.assertTrue(resumed['events'])
        self.assertEqual(int(cursor['sequence'])+1,int(resumed['events'][0]['sequence']))
        self.assertTrue(resumed['observation']['history']['last_worker']['outcome']['cancellation_observed'])
        self.assertEqual(source,(root/'source.img').read_bytes())
        controller.actual_exit(caller['observation']['controller'])

    def test_actual_wait_follows_live_operation_until_recorded_exit(self):
        root,inputs,expected,review=controller.prepared(fault=True)
        caller=controller.call(dict(review=review,controller_mode='dispatch',fixture=dict(worker_fault='execute_wait_cancel')),fault=True)
        header=json.loads((root/'store/recursive-request.json').read_bytes())
        waiter=subprocess.Popen([str(PROBE)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        value=dict(operation_id=header['operation_id'],store=str(root/'store'),wait_ms='2000',stream_watch=True)
        waiter.stdin.write(canonical(value));waiter.stdin.close()
        rows=[];entered=threading.Event()
        def drain():
            for line in waiter.stdout:
                row=json.loads(line);rows.append(row)
                if row.get('schema')=='org.disked.event/1':entered.set()
        reader=threading.Thread(target=drain,daemon=True);reader.start()
        ready=entered.wait(5)
        cancelled=controller.inspect(root,cancel=True)
        self.assertEqual('requested',cancelled['cancellation_request'])
        waiter.wait(timeout=10);reader.join(timeout=10)
        self.assertTrue(ready);self.assertFalse(reader.is_alive())
        self.assertEqual(0,waiter.returncode);self.assertFalse(waiter.stderr.read())
        events=[r for r in rows if r.get('schema')=='org.disked.event/1'];out=rows[-1]
        RESULTS.append(dict(input_sha256=sha(canonical(value)),exit_code=waiter.returncode,stream_events=events,result=out))
        self.assertEqual('recorded_terminal',out['status'],out)
        self.assertGreater(int(out['polls']),1)
        self.assertEqual('fat.tree.operation.snapshot',events[0]['type'])
        self.assertEqual('exited',events[-1]['payload']['record']['payload']['phase'])
        controller.actual_exit(caller['observation']['controller'])


def main():
    global PROBE
    parser=argparse.ArgumentParser();parser.add_argument('--probe',type=Path,required=True)
    parser.add_argument('--controller',type=Path,required=True);parser.add_argument('--fault-controller',type=Path,required=True)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    PROBE=args.probe.resolve();controller.NORMAL=args.controller.resolve();controller.FAULT=args.fault_controller.resolve();controller.RECONNECT=PROBE
    admission.PROBE=controller.NORMAL;admission.FAULT=controller.FAULT
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(WatchTests))
    args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(),methods=result.testsRun,observations=len(RESULTS),records=RESULTS,
        native_callers=controller.RESULTS,native_preparations=admission.RESULTS),indent=2)+'\n',encoding='utf-8',newline='\n')
    return 0 if result.wasSuccessful() else 1


if __name__=='__main__':raise SystemExit(main())
