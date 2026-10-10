"""Typed native watch events, strict identity and compatible observation readers."""
import argparse,copy,hashlib,json,subprocess,unittest
from pathlib import Path
P=argparse.ArgumentParser();P.add_argument('--probe',type=Path,required=True);P.add_argument('--evidence',type=Path);ARGS,REST=P.parse_known_args();OBS=[]
def encoded(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def records():
    ident='fake-op:'+'a'*32
    binding=dict(operation_id=ident,attempt_id=ident+':attempt:1',worker_epoch='worker:'+'b'*32,fixture_id='fake:complete',host_id='c'*64,source_revision='d'*40,input_digest='sha256:'+'e'*64,image_digest='f'*64,process_id='1',process_created='1',provider_id='provider.fake.bootstrap/1',target_profile='windows.nt10.x64.win32')
    state=dict(schema='org.disked.fake-operation/1',scope='fake-only',binding=binding,sequence='1',phase='pending',logical_state='pending',attempt_state='prepared',effect_certainty='not_started',cancellation='not_requested',recovery='unnecessary',outcome=None,synthetic_effect_count='0',last_event='initialized')
    updates=[{},dict(phase='prepared',logical_state='active',last_event='prepared'),dict(phase='in_flight',attempt_state='dispatched',effect_certainty='in_flight',synthetic_effect_count=None,last_event='effect_dispatched'),dict(phase='observed',attempt_state='observing',effect_certainty='observed',synthetic_effect_count='1',last_event='effect_observed'),dict(phase='finished',logical_state='completed',attempt_state='finished',outcome='succeeded',last_event='verified')]
    previous='0'*64;out=[]
    for i,change in enumerate(updates,1):
        state.update(change,sequence=str(i));r=dict(schema='org.disked.fake-operation-record/1',state=copy.deepcopy(state),previous=previous);previous=r['digest']=hashlib.sha256(encoded(r)).hexdigest()
        out.append(dict(schema='org.disked.event/1',operation_id=ident,sequence=str(i),type='fake.operation.record',payload=dict(schema='org.disked.fake-operation-event/1',request_id='watch:test',observer_epoch='watch:'+'1'*32,record=r)))
    return out
class Watch(unittest.TestCase):
    def probe(self,**value):
        p=subprocess.run([str(ARGS.probe)],input=json.dumps(value)+'\n',capture_output=True,text=True,encoding='utf-8',timeout=5)
        self.assertEqual((0,''),(p.returncode,p.stderr));return json.loads(p.stdout)
    def read(self,events,**fields):return self.probe(op='read',operation_id=records()[0]['operation_id'],events=events,**fields)['results']
    def test_order_duplicates_gap_and_reconnect(self):
        events=records();v=self.read([events[0],events[0],events[2],events[1],events[2],events[3],events[4]])
        self.assertEqual([True,False,None,True,True,True,True],[x.get('accepted') for x in v]);self.assertEqual('watch_sequence_gap',v[2]['error']);self.assertEqual('1',v[2]['sequence'])
        r=events[1]['payload']['record'];v=self.read(events[2:],sequence='2',digest=r['digest'],worker_epoch=r['state']['binding']['worker_epoch']);self.assertTrue(all(x['accepted'] for x in v));OBS.append(dict(test='sequence and reconnect',results=v))
    def test_snapshot_is_explicit_and_then_requires_continuity(self):
        events=records();snap=copy.deepcopy(events[3]);snap['type']='fake.operation.snapshot'
        self.assertEqual('watch_snapshot_unrequested',self.read([snap])[0]['error'])
        result=self.read([snap,events[4]],snapshot=True);self.assertTrue(all(x['accepted'] for x in result))
    def test_extensions_preserved_but_required_features_unknown(self):
        event=records()[0];event['observation_extension']={'x':[1]};event['payload']['display_extension']='data'
        self.assertEqual(event,self.read([event])[0]['preserved'])
        for target in ('top','payload'):
            bad=copy.deepcopy(event);(bad if target=='top' else bad['payload'])['required_features']=['unknown'];self.assertEqual('unsupported_feature',self.read([bad])[0]['error'])
    def test_identity_digest_and_dimensional_contradictions(self):
        events=records();bad=[]
        for path,value in [(('sequence',),'18446744073709551616'),(('operation_id',),'fake-op:'+'0'*32),(('type',),'future.critical'),(('payload','observer_epoch'),'watch:wrong'),(('payload','record','state','logical_state'),'completed')]:
            v=copy.deepcopy(events[0]);p=v
            for k in path[:-1]:p=p[k]
            p[path[-1]]=value;bad.append(v)
        for event in bad:self.assertNotEqual('',self.probe(op='validate',event=event)['error'])
        changed=copy.deepcopy(events[1]);changed['payload']['observer_epoch']='watch:'+'2'*32
        self.assertEqual('watch_observer_changed',self.read([events[0],changed])[1]['error'])
        changed=copy.deepcopy(events[1]);r=changed['payload']['record'];r['state']['binding']['worker_epoch']='worker:'+'3'*32
        r['digest']=hashlib.sha256(encoded({k:v for k,v in r.items() if k!='digest'})).hexdigest()
        self.assertEqual('watch_event_identity',self.read([events[0],changed])[1]['error'])
        wrong=copy.deepcopy(events[1]);wrong['payload']['record']['previous']='a'*64;r=wrong['payload']['record'];r['digest']=hashlib.sha256(encoded({k:v for k,v in r.items() if k!='digest'})).hexdigest()
        self.assertEqual('watch_cursor_conflict',self.read([events[0],wrong])[1]['error'])
    def test_queue_limit_and_close(self):
        v=self.probe(op='queue',event=records()[0]);self.assertEqual(dict(error='watch_queue_limit',count=64,after_close=False),v);OBS.append(dict(test='native queue bound',result=v))
if __name__=='__main__':
    result=unittest.main(argv=[__file__]+REST,verbosity=2,exit=False)
    if ARGS.evidence:ARGS.evidence.write_text(json.dumps(dict(tests=result.result.testsRun,passed=result.result.wasSuccessful(),observations=OBS),indent=2)+'\n',encoding='utf-8',newline='\n')
    raise SystemExit(not result.result.wasSuccessful())
