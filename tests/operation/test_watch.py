"""Actual fake-worker observation, negotiated event frames and client loss."""
import argparse,copy,ctypes as C,hashlib,json,subprocess,sys,tempfile,time,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from gui_fixture import Gui,U,WP,wait
P=argparse.ArgumentParser();P.add_argument('--exe',type=Path,required=True);P.add_argument('--delayed',type=Path,required=True);P.add_argument('--root',type=Path,default=Path(__file__).resolve().parents[2]);P.add_argument('--validate-schemas',action='store_true');P.add_argument('--evidence',type=Path);ARGS,REST=P.parse_known_args();ARGS.exe=ARGS.exe.resolve();ARGS.delayed=ARGS.delayed.resolve();OBS=[];BUNDLE=None
if ARGS.validate_schemas:
 sys.path.insert(0,str(ARGS.root/'spec/tools'));import specctl;BUNDLE=specctl.Bundle(ARGS.root/'spec')
def validate(value):
 if BUNDLE:BUNDLE.validate('urn:disked:schema:fake-operation-event:1' if value['schema']=='org.disked.event/1' else 'urn:disked:schema:response:1',value)
def request(ident,command,parameters,features=()):return dict(schema='org.disked.request/1',request_id=ident,command=command,parameters=parameters,required_features=list(features))
FEATURE='org.disked.fake-operation-events/1'
class Watch(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory(prefix='disked-watch-');self.directory=Path(self.temp.name);self.ident=None
 def tearDown(self):
  deadline=time.monotonic()+6
  while True:
   try:self.temp.cleanup();break
   except PermissionError:
    if time.monotonic()>deadline:raise
    time.sleep(.05)
 def invoke(self,*args,code=None):
  p=subprocess.run([str(ARGS.exe),*map(str,args),'--json'],capture_output=True,timeout=8);self.assertEqual(b'',p.stderr);v=json.loads(p.stdout);validate(v)
  if code is not None:self.assertEqual(code,p.returncode,v)
  return p.returncode,v
 def start(self,fixture='fake:complete'):
  _,v=self.invoke('plan','simulate',fixture,'--state-dir',self.directory);self.ident=v['operation_id'];self.assertIsNotNone(self.ident);return v
 def final(self):
  deadline=time.monotonic()+5
  while True:
   _,v=self.invoke('operation','inspect',self.ident,'--state-dir',self.directory)
   if v['result'].get('state',{}).get('phase')=='finished' or v['result'].get('worker_observation')=='exited':return v
   self.assertLess(time.monotonic(),deadline);time.sleep(.025)
 def parameters(self,**extra):return dict(operation_id=self.ident,state_directory=str(self.directory),**extra)
 def test_live_cli_events_precede_completion_and_reconnect_without_replay(self):
  admitted=self.start();started=time.monotonic();p=subprocess.Popen([str(ARGS.exe),'operation','watch',self.ident,'--state-dir',str(self.directory),'--follow-ms','2000','--format=ndjson'],stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  samples=[]
  try:
   for line in p.stdout:
    value=json.loads(line);validate(value);samples.append(dict(elapsed=time.monotonic()-started,value=value))
   self.assertEqual((0,b''),(p.wait(timeout=5),p.stderr.read()))
  finally:
   if p.poll() is None:p.kill();p.wait(timeout=3)
   p.stdout.close();p.stderr.close()
  events=[x['value'] for x in samples[:-1]];self.assertEqual(list(map(str,range(1,6))),[e['sequence'] for e in events]);self.assertLess(samples[0]['elapsed'],.5);self.assertGreater(samples[-1]['elapsed']-samples[0]['elapsed'],.4)
  self.assertEqual([],samples[-1]['value']['result']['events']);self.assertEqual('completed',samples[-1]['value']['status'])
  cursor=events[1]['payload']['record'];_,reconnected=self.invoke('operation','watch',self.ident,'--state-dir',self.directory,'--after-sequence','2','--after-digest',cursor['digest'],'--worker-epoch',cursor['state']['binding']['worker_epoch'],code=0)
  self.assertEqual(['3','4','5'],[x['sequence'] for x in reconnected['result']['events']]);self.assertEqual(admitted['result']['state']['binding'],reconnected['result']['state']['binding'])
  OBS.append(dict(test='live CLI and exact reconnect',samples=samples,reconnected=reconnected))
 def test_negotiation_preserves_one_response_and_correlates_stream(self):
  self.start();self.final();params=self.parameters();frames=[request('ordinary','operation.watch',params),request('events','operation.watch',params,[FEATURE]),request('after','build.inspect',{})]
  p=subprocess.run([str(ARGS.exe),'protocol','serve','--format=ndjson'],input=b''.join(json.dumps(x).encode()+b'\n' for x in frames),capture_output=True,timeout=8);self.assertEqual((0,b''),(p.returncode,p.stderr));values=[json.loads(x) for x in p.stdout.splitlines()]
  for v in values:validate(v)
  self.assertEqual('ordinary',values[0]['request_id']);self.assertEqual(5,len(values[0]['result']['events']))
  self.assertEqual(['org.disked.event/1']*5,[x['schema'] for x in values[1:6]]);self.assertTrue(all(x['payload']['request_id']=='events' for x in values[1:6]));self.assertEqual(['events','after'],[x['request_id'] for x in values[6:]])
  for format_,command,features in [('json','operation.watch',[FEATURE]),('ndjson','build.inspect',[FEATURE]),('ndjson','operation.watch',[FEATURE,FEATURE]),('ndjson','operation.watch',['unknown'])]:
   v=request('invalid',command,params if command=='operation.watch' else {},features);p=subprocess.run([str(ARGS.exe),'protocol','serve','--format='+format_],input=json.dumps(v).encode()+b'\n',capture_output=True,timeout=5)
   self.assertEqual(3,p.returncode);self.assertEqual('unsupported_feature',json.loads(p.stdout)['diagnostics'][0]['code'])
  OBS.append(dict(test='explicit negotiation and request correlation',values=values))
 def test_snapshot_and_cursor_refusals_preserve_store(self):
  self.start();self.final();before={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.directory.iterdir()}
  _,v=self.invoke('operation','watch',self.ident,'--state-dir',self.directory,'--snapshot',code=0);self.assertEqual(1,len(v['result']['events']));event=v['result']['events'][0];self.assertEqual(('fake.operation.snapshot','5'),(event['type'],event['sequence']))
  epoch=event['payload']['record']['state']['binding']['worker_epoch'];digest=event['payload']['record']['digest']
  cases=[(['--after-sequence','1'],'watch_cursor_incomplete'),(['--after-sequence','6','--worker-epoch',epoch,'--after-digest',digest],'watch_cursor_ahead'),(['--after-sequence','5','--worker-epoch','worker:'+'0'*32,'--after-digest',digest],'watch_epoch_mismatch'),(['--after-sequence','5','--worker-epoch',epoch,'--after-digest','0'*64],'watch_cursor_conflict'),(['--snapshot','--after-sequence','5','--worker-epoch',epoch,'--after-digest',digest],'watch_cursor_conflict'),(['--follow-ms','2001'],'invalid_option_value')]
  for args,reason in cases:
   _,v=self.invoke('operation','watch',self.ident,'--state-dir',self.directory,*args,code=2);self.assertEqual(reason,v['diagnostics'][0]['code'])
  self.assertEqual(before,{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in self.directory.iterdir()})
  OBS.append(dict(test='snapshot and cursor refusal without store mutation',snapshot=event))
 def test_follow_boundary_and_unknown_history(self):
  self.start('fake:cancel-checkpoint');started=time.monotonic();_,v=self.invoke('operation','watch',self.ident,'--state-dir',self.directory,'--follow-ms','150',code=5)
  self.assertGreaterEqual(time.monotonic()-started,.14);self.assertLess(time.monotonic()-started,.7);self.assertEqual('not_requested',v['result']['state']['cancellation'])
  self.final();path=self.directory/'operation.records';original=path.read_bytes();path.write_bytes(original[:-1]);_,bad=self.invoke('operation','watch',self.ident,'--state-dir',self.directory,code=6)
  self.assertEqual([],bad['result']['events']);self.assertEqual('operation_history_partial',bad['diagnostics'][0]['code']);self.assertEqual(original[:-1],path.read_bytes());OBS.append(dict(test='bounded follow and partial history',boundary=v,partial=bad))
 def test_worker_outcomes_are_not_observer_success(self):
  for fixture,outcome,code in [('fake:verification-failure','verification_failed',0),('fake:unknown',None,6)]:
   with self.subTest(fixture=fixture),tempfile.TemporaryDirectory(prefix='disked-watch-outcome-') as d:
    _,start=self.invoke('plan','simulate',fixture,'--state-dir',d);ident=start['operation_id'];_,v=self.invoke('operation','watch',ident,'--state-dir',d,'--follow-ms','2000',code=code)
    self.assertEqual(outcome,v['result']['state']['outcome']);self.assertEqual('unknown' if code else 'completed',v['status']);OBS.append(dict(test=fixture,response=v))
 def test_client_disconnect_and_slow_output_do_not_cancel_or_restart(self):
  self.start('fake:cancel-checkpoint');p=subprocess.Popen([str(ARGS.exe),'operation','watch',self.ident,'--state-dir',str(self.directory),'--follow-ms','2000','--format=ndjson'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
  try:
   first=json.loads(p.stdout.readline());validate(first);p.stdout.close();self.assertEqual(4,p.wait(timeout=5));self.assertEqual(b'',p.stderr.read())
  finally:
   if p.poll() is None:p.kill();p.wait(timeout=3)
   p.stderr.close()
  final=self.final();self.assertEqual('succeeded',final['result']['state']['outcome']);self.assertEqual('not_requested',final['result']['state']['cancellation']);self.assertEqual('1',final['result']['state']['synthetic_effect_count'])
  # A completed record stream itself exceeds the anonymous pipe capacity. An
  # undrained observer must stop at the real output deadline with no new claim.
  second=self.directory/'untouched';second.mkdir()
  p=subprocess.Popen([str(ARGS.exe),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,bufsize=0)
  p.stdin.write(json.dumps(request('blocked-output','operation.watch',self.parameters(),[FEATURE])).encode()+b'\n'+json.dumps(request('must-not-start','plan.simulate',dict(fixture_id='fake:complete',state_directory=str(second)))).encode()+b'\n');p.stdin.close();started=time.monotonic()
  try:
   self.assertEqual(4,p.wait(timeout=5));elapsed=time.monotonic()-started;self.assertGreater(elapsed,2.8);self.assertLess(elapsed,4.2);retained=p.stdout.read();self.assertEqual(b'',p.stderr.read())
  finally:
   if p.poll() is None:p.kill();p.wait(timeout=3)
   p.stdout.close();p.stderr.close()
  self.assertEqual([],list(second.iterdir()));self.assertEqual(final['result']['state'],self.final()['result']['state']);OBS.append(dict(test='disconnect and output backpressure',first=first,final=final,elapsed=elapsed,retained_bytes=len(retained)))
 def test_gui_watch_keeps_cached_views_and_reports_late_result(self):
  self.start('fake:cancel-checkpoint');g=Gui(ARGS.exe,['--gui','operation','watch',self.ident,'--state-dir',str(self.directory),'--follow-ms','2000'],render=True)
  try:
   # All seven fields are reachable through native pages; paging is inert.
   self.assertIn('after_digest',g.text(220));g.click(114);self.assertIn('follow_ms',g.text(220))
   g.click(114);self.assertIn('snapshot',g.text(220));g.set(200,'false')
   g.click(114);self.assertIn('worker_epoch',g.text(220));g.click(113)
   g.click(109);review=g.details();self.assertFalse(review['parameters']['snapshot']);self.assertNotIn('after_digest',review['parameters'])
   g.click(110);self.assertIn('pending_request',g.details());samples=[]
   for _ in range(5):
    value=WP();began=time.monotonic();ok=U.SendMessageTimeoutW(g.window,0,0,0,2,250,C.byref(value));samples.append((time.monotonic()-began)*1000);self.assertTrue(ok);self.assertLess(samples[-1],250)
   g.click(104);g.choose(0);g.click(108);current=g.details();self.assertEqual('fake:alpha@1',current['result']['target']['id'])
   wait(lambda:'earlier_request' in g.details(),4);late=g.details();self.assertEqual(current['request_id'],late['request_id']);self.assertGreater(len(late['earlier_request']['result']['events']),0);OBS.append(dict(test='GUI watch and cached navigation',samples=samples,late=late))
  finally:g.close()
  self.assertEqual(0,g.code);self.final()
 def test_checkpoint_cancellation_is_reported_as_observed_truth(self):
  self.start('fake:cancel-checkpoint');self.invoke('operation','cancel',self.ident,'--state-dir',self.directory,code=0)
  _,v=self.invoke('operation','watch',self.ident,'--state-dir',self.directory,'--follow-ms','2000',code=0)
  self.assertEqual('cancelled',v['result']['state']['outcome']);self.assertEqual('0',v['result']['state']['synthetic_effect_count']);self.assertEqual('cancel_acknowledged',v['result']['events'][-1]['payload']['record']['state']['last_event']);OBS.append(dict(test='observed checkpoint cancellation',response=v))
 def test_console_watch_preserves_cached_navigation_and_input(self):
  for frontend in ('tui','shell'):
   with self.subTest(frontend=frontend),tempfile.TemporaryDirectory(prefix='disked-watch-console-') as d:
    report=Path(d)/'report.json';startup=subprocess.STARTUPINFO();startup.dwFlags=subprocess.STARTF_USESHOWWINDOW;startup.wShowWindow=0
    p=subprocess.run([sys.executable,str(Path(__file__).with_name('console_watch_fixture.py')),str(ARGS.exe),str(report),frontend],cwd=d,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=20)
    value=json.loads(report.read_text(encoding='utf-8'));OBS.append(value);self.assertEqual(0,p.returncode,value);self.assertNotIn('fixture_error',value);self.assertLess(value['cached_navigation_ms'],250)
 def test_timed_out_observer_emits_no_late_frames_and_retains_callback_slot(self):
  self.start();self.final();p=subprocess.Popen([str(ARGS.delayed),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
  try:
   def send(ident,command,parameters,features=()):
    p.stdin.write(json.dumps(request(ident,command,parameters,features)).encode()+b'\n');p.stdin.flush();return json.loads(p.stdout.readline())
   began=time.monotonic();expired=send('expired','operation.watch',self.parameters(),[FEATURE]);elapsed=time.monotonic()-began
   self.assertEqual('unknown',expired['status']);self.assertEqual('request_wait_expired',expired['diagnostics'][0]['code']);self.assertGreaterEqual(elapsed,3.9);self.assertLess(elapsed,5)
   self.assertEqual('cached',send('cached','build.inspect',{})['request_id'])
   busy=send('busy','operation.inspect',self.parameters());self.assertEqual('request_resource_limit',busy['diagnostics'][0]['code'])
   time.sleep(2.8);new=send('reconnected','operation.watch',self.parameters());self.assertEqual('reconnected',new['request_id']);self.assertEqual('completed',new['status']);self.assertEqual(5,len(new['result']['events']))
   p.stdin.close();p.stdin=None;out,err=p.communicate(timeout=5);self.assertEqual((6,b'',b''),(p.returncode,out,err));OBS.append(dict(test='late observation sealed after timeout',expired=expired,busy=busy,reconnected=new,elapsed=elapsed))
  finally:
   if p.poll() is None:p.kill();p.wait(timeout=3)
   for stream in (p.stdin,p.stdout,p.stderr):
    if stream:stream.close()
if __name__=='__main__':
 result=unittest.main(argv=[__file__]+REST,verbosity=2,exit=False)
 if ARGS.evidence:ARGS.evidence.write_text(json.dumps(dict(executable=str(ARGS.exe),sha256=hashlib.sha256(ARGS.exe.read_bytes()).hexdigest(),tests=result.result.testsRun,passed=result.result.wasSuccessful(),observations=OBS,failures=[dict(test=str(t),detail=d) for t,d in result.result.failures+result.result.errors]),indent=2)+'\n',encoding='utf-8',newline='\n')
 raise SystemExit(not result.result.wasSuccessful())
