"""Actual development executable recursive command and native frontend journeys."""
import argparse,copy,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from gui_fixture import Gui,wait
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
import test_fat_tree_admission as admission
from test_fat_tree_review import canonical
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'spec/tools'))
import specctl as sc

def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def arguments(p):
 out=['filesystem','extract-tree',p['phase']]
 if p['phase']=='prepare':
  out += [p['source'],p['destination']]
  for key,flag in [('ledger','--ledger'),('state_directory','--state-dir'),('volume_offset','--volume-offset'),
   ('volume_bytes','--volume-bytes'),('fat_copy','--fat-copy'),('capture_epoch','--capture-epoch'),('oem_code_page','--oem-code-page')]:out += [flag,p[key]]
 else:
  out += ['--definition',canonical(p['definition']).decode(),'--definition-digest',p['definition_digest']]
  for key in ('source_read','destination_write','ledger_write','operation_write','host_effects'):
   if p.get('allow_'+key):out.append('--allow-'+key.replace('_','-'))
 return out
def grants(p):return dict(phase='execute',definition=p['definition'],definition_digest=p['definition_digest'],
 allow_source_read=True,allow_destination_write=True,allow_ledger_write=True,allow_operation_write=True,allow_host_effects=True)

def main():
 ap=argparse.ArgumentParser()
 for name in ('exe','disabled','output'):ap.add_argument('--'+name,type=Path,required=True)
 a=ap.parse_args();exe=str(a.exe.resolve());disabled=str(a.disabled.resolve());records=[];cases=[];passed=False
 bundle=sc.Bundle(Path(__file__).resolve().parents[2]/'spec')
 env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_TEST_','DISKED_ACQ_','DISKED_FAT_'))}
 def record(name,**data):records.append(dict(name=name,**data));print('PASS '+name,flush=True)
 def cli(words,exits=(0,),binary=exe):
  r=subprocess.run([binary,'--json',*words],capture_output=True,env=env,timeout=30)
  assert r.returncode in exits and not r.stderr,(words[:3],r.returncode,r.stdout,r.stderr)
  out=json.loads(r.stdout)
  if '--help' not in words and words[:2] in (['filesystem','extract-tree'],['operation','inspect'],['operation','watch']):
   bundle.validate('urn:disked:schema:fat-recursive-response-prototype:1',out)
  record('cli',words=words[:3],exit_code=r.returncode,output_sha256=sha(r.stdout));return out
 def wire(command,p,features=None):
  frame=dict(schema='org.disked.request/1',request_id='recursive:req',command=command,parameters=p,required_features=features or [])
  r=subprocess.run([exe,'protocol','serve','--format','ndjson' if features else 'json'],input=canonical(frame)+(b'\n' if features else b''),capture_output=True,env=env,timeout=30)
  assert r.returncode in (0,2,3,4,5,6) and not r.stderr,(command,r.returncode,r.stdout,r.stderr)
  out=[json.loads(line) for line in r.stdout.splitlines()]
  for row in out:
   if row['schema']=='org.disked.response/1':bundle.validate('urn:disked:schema:fat-recursive-response-prototype:1',row)
  record('protocol',command=command,exit_code=r.returncode,frames=len(out));return out
 def setup(bits=16,count=3):
  root,inp,expected=admission.fixture(bits,count)
  p=dict(phase='prepare',source=inp['source'],destination=inp['destination'],ledger=inp['ledger'],state_directory=inp['store'],
   volume_offset=inp['offset'],volume_bytes=inp['length'],fat_copy=inp['copy'],capture_epoch='17',oem_code_page='437')
  cases.append(dict(root=str(root),parameters=p,source_sha256=sha((root/'source.img').read_bytes())))
  return root,p,expected
 def untouched(root):assert not (root/'output').exists() and not (root/'metadata.ndjson').exists() and not list((root/'store').iterdir())
 def contradiction(response,path,value):
  bad=copy.deepcopy(response);target=bad;parts=path.split('.')
  for key in parts[:-1]:target=target[key]
  target[parts[-1]]=value
  try:bundle.validate('urn:disked:schema:fat-recursive-response-prototype:1',bad)
  except sc.SpecError:return
  raise AssertionError(('producer admitted contradiction',path))
 def finish(root,p,response,expected):
  assert response['status'] in ('accepted_running','completed','unknown'),response
  operation=response['operation_id'];assert isinstance(operation,str) and operation.startswith('tree-op:')
  end=time.monotonic()+90
  while True:
   out=cli(['operation','inspect',operation,'--state-dir',p['state_directory']],(0,6))
   value=out.get('result') or {};history=value.get('history') or {}
   if history.get('state')=='recorded_complete':break
   assert time.monotonic()<end,('same operation remains unresolved',out)
   time.sleep(.04)
  for name,(data,attr) in expected.items():assert (root/'output'/name).read_bytes()==data,name
  assert sha((root/'source.img').read_bytes())==next(c['source_sha256'] for c in cases if c['root']==str(root))
  header=json.loads((root/'store/recursive-request.json').read_bytes());assert header['operation_id']==operation
  record('verified-native-output',operation_id=operation,files=len(expected));return operation
 try:
  listing=cli(['command','list'])['result']['commands'];assert next(c for c in listing if c['id']=='filesystem.tree.extract')['availability']=='available'
  disabled_list=cli(['command','list'],binary=disabled)['result']['commands'];assert next(c for c in disabled_list if c['id']=='filesystem.tree.extract')['availability']=='unavailable'
  cli(['filesystem','extract-tree','--help'])
  for bits in (12,16,32):
   root,p,expected=setup(bits)
   prepared=cli(arguments(p));review=prepared['result'];untouched(root)
   contradiction(prepared,'result.definition_digest','sha256:'+'0'*64)
   contradiction(prepared,'result.execution_admitted',True)
   contradiction(prepared,'result.preparation.worker.dependencies_retained',True)
   assert not review['execution_admitted'] and review['definition_digest']==sha(b'disked:fat-tree-extraction-review:1\n'+canonical(review['definition']))
   g=grants(review)
   if bits==16:
    for name in [k for k in g if k.startswith('allow_')]:
     bad=dict(g);bad[name]=False;assert wire('filesystem.tree.extract',bad)[0]['status']=='refused';untouched(root)
   response=cli(arguments(g),(0,5,6))
   if response['status'] in ('accepted_running','completed'):
    contradiction(response,'result.reply.operation_id','tree-op:'+'0'*32)
    contradiction(response,'result.reply.admission.store_effects_possible',False)
   operation=finish(root,p,response,expected)
   op=dict(operation_id=operation,state_directory=p['state_directory'])
   observed=wire('operation.inspect',op)[0];assert observed['result']['history']['state']=='recorded_complete'
   contradiction(observed,'result.history.operation_id','tree-op:'+'0'*32)
   contradiction(observed,'result.history.records','65')
   watch=wire('operation.watch',op,features=['org.disked.fat-tree-operation-events/1'])
   events=[v for v in watch if v['schema']=='org.disked.event/1'];assert events
   for i,event in enumerate(events):
    bundle.validate('urn:disked:schema:fat-tree-operation-event-prototype:1',event)
    assert event['sequence']==str(i+1)
    assert event['payload']['record_digest']==sha(canonical(event['payload']['record'])+b'\n')
   assert watch[-1]['status']=='completed' and not watch[-1]['result']['events']
   contradiction(watch[-1],'result.status','following_boundary')
   contradiction(watch[-1],'result.cursor.sequence','65')
   late=wire('operation.cancel.request',op)[0];assert late['result']['cancellation_request']=='too_late_recorded'
   assert wire('operation.watch',op,features=['org.disked.acquisition-operation-events/1'])[0]['status']=='refused'
  for frontend in ('gui','tui','shell'):
   root,p,expected=setup();review=None
   for phase in ('prepare','execute'):
    params=p if phase=='prepare' else grants(review)
    if frontend=='gui':
     ui=Gui(Path(exe),['--gui',*arguments(params)],render=True)
     try:
      untouched(root);ui.click(109);details=ui.details();assert details.get('reviewed'),details;untouched(root)
      ui.click(110);response=wait(lambda:ui.details() if ui.details().get('schema')=='org.disked.response/1' else None,10)
     finally:ui.close()
     assert ui.code==0 and not ui.error
    else:
     inp=root/(phase+'-input.json');out=root/(phase+'-console.json')
     inp.write_bytes(canonical(dict(parameters=params,command=arguments(params))))
     startup=subprocess.STARTUPINFO();startup.dwFlags=1;startup.wShowWindow=0
     run=subprocess.run([sys.executable,str(Path(__file__).with_name('fat_extraction_console_fixture.py')),exe,str(inp),str(out),frontend],
      env=env,timeout=45,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
     console=json.loads(out.read_bytes());assert run.returncode==0,console
     response=console['response'];assert all(console['restored'].values())
    bundle.validate('urn:disked:schema:fat-recursive-response-prototype:1',response)
    record('actual-'+frontend,phase=phase,status=response['status'])
    if phase=='prepare':review=response['result'];untouched(root)
    else:operation=finish(root,p,response,expected)
   op=dict(operation_id=operation,state_directory=p['state_directory'])
   command=['operation','watch',operation,'--state-dir',p['state_directory']]
   if frontend=='gui':
    ui=Gui(Path(exe),['--gui',*command],render=True)
    try:
     ui.click(109);assert ui.details().get('reviewed'),ui.details();ui.click(110)
     observed=wait(lambda:ui.details() if ui.details().get('schema')=='org.disked.response/1' else None,10)
    finally:ui.close()
    assert ui.code==0 and not ui.error
   else:
    inp=root/'watch-input.json';out=root/'watch-console.json';inp.write_bytes(canonical(dict(parameters=op,command=command)))
    startup=subprocess.STARTUPINFO();startup.dwFlags=1;startup.wShowWindow=0
    run=subprocess.run([sys.executable,str(Path(__file__).with_name('fat_extraction_console_fixture.py')),exe,str(inp),str(out),frontend],
     env=env,timeout=45,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
    console=json.loads(out.read_bytes());assert run.returncode==0,console;assert all(console['restored'].values());observed=console['response']
   bundle.validate('urn:disked:schema:fat-recursive-response-prototype:1',observed)
   assert observed['status']=='completed' and observed['result']['status']=='recorded_terminal',observed
   assert observed['result']['events'] and observed['operation_id']==operation
   record('actual-'+frontend+'-watch',status=observed['status'],events=len(observed['result']['events']))
  passed=True
 finally:
  a.output.write_text(json.dumps(dict(passed=passed,checks=len(records),records=records,cases=cases,
   scope='Actual normal Windows ordinary-file prototype composition; no physical, other-host or release qualification'),indent=2)+'\n',encoding='utf-8',newline='\n')
 assert passed
if __name__=='__main__':main()
