"""Canonical parser/form/protocol semantics and actual native recursive ports."""
import argparse,copy,hashlib,json,subprocess,unittest
from pathlib import Path
import jsonschema
import test_fat_tree_admission as admission
import test_fat_tree_controller as controller
from test_fat_tree_review import canonical

PROBE=RECONNECT=None
RESULTS=[]
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def frame(p):return dict(schema='org.disked.request/1',request_id='tree-command',command='filesystem.tree.extract',parameters=p,required_features=[])
def call(value,exit_code=0):
 run=subprocess.run([str(PROBE)],input=canonical(value),capture_output=True,timeout=25)
 assert run.returncode==exit_code and not run.stderr,(run.returncode,run.stdout,run.stderr)
 out=json.loads(run.stdout);assert 'error' not in out,out
 assert out['response']['status']=={0:'completed',2:'refused',3:'refused',4:'failed',5:'accepted_running',6:'unknown'}[exit_code],out
 RESULTS.append(dict(input_sha256=sha(canonical(value)),exit_code=run.returncode,result=out));return out
def prepare(bits=16,mode='request'):
 root,inputs,expected=admission.fixture(bits)
 p=dict(phase='prepare',source=inputs['source'],destination=inputs['destination'],ledger=inputs['ledger'],state_directory=inputs['store'],
        volume_offset=inputs['offset'],volume_bytes=inputs['length'],fat_copy=inputs['copy'],capture_epoch='17',oem_code_page='437')
 if mode=='request':value=dict(request=frame(p))
 elif mode=='form':value=dict(editor=p)
 else:value=dict(argv=['filesystem','extract-tree','prepare',p['source'],p['destination'],'--ledger',p['ledger'],
  '--state-dir',p['state_directory'],'--volume-offset',p['volume_offset'],'--volume-bytes',p['volume_bytes'],
  '--fat-copy',p['fat_copy'],'--capture-epoch','17','--oem-code-page','437'])
 out=call(value)['response']['result']
 assert not (root/'output').exists() and not (root/'metadata.ndjson').exists() and not list((root/'store').iterdir())
 assert not out['execution_admitted'] and out['definition_digest']==sha(b'disked:fat-tree-extraction-review:1\n'+canonical(out['definition']))
 assert out['preparation']['worker']['worker']['observation']=='exited' and not out['preparation']['worker']['dependencies_retained']
 execution=dict(phase='execute',definition=out['definition'],definition_digest=out['definition_digest'],
  allow_source_read=True,allow_destination_write=True,allow_ledger_write=True,allow_operation_write=True,allow_host_effects=True)
 return root,p,expected,out,execution

class CommandTests(unittest.TestCase):
 def test_real_prepare_execution_across_parser_form_and_protocol(self):
  for bits,mode in [(12,'cli'),(16,'form'),(32,'request')]:
   root,p,expected,prepared,execution=prepare(bits,mode)
   source=(root/'source.img').read_bytes()
   run=subprocess.run([str(PROBE)],input=canonical(dict(request=frame(execution))),capture_output=True,timeout=25)
   self.assertIn(run.returncode,(0,5,6));self.assertFalse(run.stderr)
   out=json.loads(run.stdout);response=out['response'];self.assertIsInstance(response['operation_id'],str)
   RESULTS.append(dict(kind='native_execution',exit_code=run.returncode,result=out))
   final=controller.wait_history(root)
   self.assertEqual('recorded_complete',final['history']['state'],final)
   header=json.loads((root/'store/recursive-request.json').read_bytes())
   self.assertEqual(response['operation_id'],header['operation_id'])
   for name,(data,attributes) in expected.items():self.assertEqual(data,(root/'output'/name).read_bytes())
   self.assertEqual(source,(root/'source.img').read_bytes())
   controller.actual_exit(header['controller'])

 def test_closed_review_schema_matches_native_definition(self):
  root,p,expected,prepared,execution=prepare()
  schema=json.loads((Path(__file__).resolve().parents[2]/'spec/schemas/fat-tree-review-prototype.schema.json').read_bytes())
  validator=jsonschema.Draft202012Validator(schema);validator.validate(prepared['definition'])
  native=subprocess.run([str(PROBE)],input=canonical(dict(validate_review=prepared['definition'])),capture_output=True,timeout=15)
  self.assertEqual(0,native.returncode);self.assertEqual('',json.loads(native.stdout)['error'])
  for field in ('extra','status','acknowledgements'):
   invalid=copy.deepcopy(prepared['definition']);invalid[field]=True
   self.assertTrue(list(validator.iter_errors(invalid)))
  invalid=copy.deepcopy(prepared['definition']);invalid['backend']['resources']['source']['observed']['file']['extra']=1
  self.assertTrue(list(validator.iter_errors(invalid)))

 def test_each_grant_and_digest_refuse_without_provider_calls_or_outputs(self):
  root,p,expected,prepared,execution=prepare()
  for name in [k for k in execution if k.startswith('allow_')]:
   bad=dict(execution);bad[name]=False
   out=call(dict(request=frame(bad),spy=True,prepared=prepared,reply={}),2)
   self.assertEqual('0',out['execute_calls'])
  bad=dict(execution);bad['definition_digest']='sha256:'+'0'*64
  out=call(dict(request=frame(bad),spy=True,prepared=prepared,reply={}),3)
  self.assertEqual('fat_tree_review_grant',out['response']['diagnostics'][0]['code'])
  self.assertEqual('0',out['execute_calls']);self.assertFalse((root/'output').exists());self.assertFalse(list((root/'store').iterdir()))

 def test_bad_parameters_and_policy_fail_before_prepare_port(self):
  root,p,expected,prepared,execution=prepare()
  for change,exit_code in [(dict(unknown=True),2),(dict(volume_offset='18446744073709551616'),2),
   (dict(oem_code_page='1252'),2),(dict(time_interpretation='fixed_offset'),3),
   (dict(utc_offset_minutes='-0'),3),(dict(utc_offset_minutes='841'),3),(dict(utc_offset_minutes='oops'),3)]:
   bad=dict(p,**change);out=call(dict(request=frame(bad),spy=True,prepared=prepared,reply={}),exit_code)
   self.assertEqual('0',out['prepare_calls'])
  bad=dict(p,definition=prepared['definition'])
  out=call(dict(request=frame(bad),spy=True,prepared=prepared,reply={}),2);self.assertEqual('0',out['prepare_calls'])

 def test_preparation_receipt_binding_and_quiescence_are_checked(self):
  root,p,expected,prepared,execution=prepare()
  prepared={k:prepared[k] for k in ('definition','definition_digest','preparation')}
  bad=copy.deepcopy(prepared);bad['definition_digest']='sha256:'+'0'*64
  out=call(dict(request=frame(p),spy=True,prepared=bad,reply={}),3)
  self.assertEqual('1',out['prepare_calls']);self.assertEqual('fat_tree_preparation_digest',out['response']['diagnostics'][0]['code'])
  bad=copy.deepcopy(prepared);bad['preparation']['worker']['worker']['observation']='running';bad['preparation']['worker']['dependencies_retained']=True
  out=call(dict(request=frame(p),spy=True,prepared=bad,reply={}),3)
  self.assertEqual('fat_tree_preparation_exit_unresolved',out['response']['diagnostics'][0]['code'])
  changed=dict(p,capture_epoch='18');out=call(dict(request=frame(changed),spy=True,prepared=prepared,reply={}),3)
  self.assertEqual('fat_tree_preparation_binding',out['response']['diagnostics'][0]['code'])

 def test_running_requires_an_exact_bound_operation_identity(self):
  root,p,expected,prepared,execution=prepare()
  for reply in [dict(status='accepted_running',operation_id=None),dict(status='accepted_running',operation_id='tree-op:'+'a'*32,
      reply=dict(phase='admitted',review_digest='sha256:'+'0'*64,operation_id='tree-op:'+'a'*32))]:
   out=call(dict(request=frame(execution),spy=True,prepared=prepared,reply=reply),6)
   self.assertEqual('1',out['execute_calls']);self.assertFalse((root/'output').exists())
   self.assertEqual(str(root/'store'),out['response']['result']['state_directory'])

 def test_stale_source_rejects_before_outputs_and_repeated_execution_never_replays(self):
  root,p,expected,prepared,execution=prepare()
  source=root/'source.img';data=source.read_bytes();source.write_bytes(data[:-1]+bytes([data[-1]^1]))
  out=call(dict(request=frame(execution)),3)
  self.assertFalse((root/'output').exists());self.assertFalse(list((root/'store').iterdir()))
  root,p,expected,prepared,execution=prepare()
  run=subprocess.run([str(PROBE)],input=canonical(dict(request=frame(execution))),capture_output=True,timeout=25)
  self.assertIn(run.returncode,(0,5,6));controller.wait_history(root)
  header=json.loads((root/'store/recursive-request.json').read_bytes());controller.actual_exit(header['controller'])
  saved={str(f):f.read_bytes() for f in (root/'store').iterdir()}
  out=call(dict(request=frame(execution)),3)
  for name,raw in saved.items():self.assertEqual(raw,Path(name).read_bytes())

def main():
 global PROBE
 parser=argparse.ArgumentParser();parser.add_argument('--probe',type=Path,required=True);parser.add_argument('--reconnect',type=Path,required=True)
 parser.add_argument('--output',type=Path,required=True);args=parser.parse_args();PROBE=args.probe.resolve()
 controller.RECONNECT=args.reconnect.resolve()
 result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(CommandTests))
 args.output.write_text(json.dumps(dict(passed=result.wasSuccessful(),methods=result.testsRun,observations=len(RESULTS),records=RESULTS),indent=2)+'\n',encoding='utf-8',newline='\n')
 return 0 if result.wasSuccessful() else 1
if __name__=='__main__':raise SystemExit(main())
