"""Watch observation parity in hidden test-owned TUI/shell consoles."""
import json,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from console_tui_fixture import k,configure,key,current_text,snapshot

def run(exe,frontend,report):
 configure(k.GetStdHandle(-11),100,35);before=snapshot();state=Path.cwd()/'state';state.mkdir();p=None;frames=[]
 admitted=subprocess.run([exe,'plan','simulate','fake:cancel-checkpoint','--state-dir',str(state),'--json'],capture_output=True,timeout=8);ident=json.loads(admitted.stdout)['operation_id'];report.update(frontend=frontend,operation_id=ident,before=before,frames=frames)
 def wait(needle,seconds=5,after=None):
  started=time.monotonic()
  while time.monotonic()-started<seconds:
   text=current_text();tail=text.rsplit(after,1)[-1] if after and after in text else '' if after else text
   if needle in tail:frames.append(dict(contains=needle,text=text,elapsed_ms=(time.monotonic()-started)*1000));return
   if p.poll() is not None:raise AssertionError('frontend exited before '+needle)
   time.sleep(.005)
  raise AssertionError('missing '+needle+'\n'+text)
 def type_text(text):
  for char in text:key(0,char)
 try:
  args=['shell','--terminal=linear'] if frontend=='shell' else ['--tui','operation','watch',ident,'--state-dir',str(state),'--follow-ms','2000','--snapshot','--terminal=linear']
  p=subprocess.Popen([exe,*args],close_fds=False);wait('disked>' if frontend=='shell' else 'TYPED FORM')
  if frontend=='shell':type_text('operation watch '+ident+' --state-dir "'+str(state)+'" --follow-ms 2000 --snapshot')
  key(0x78);wait('F9 submits:' if frontend=='shell' else 'REQUEST REVIEW');key(0x78);wait('pending request' if frontend=='shell' else 'Pending request:')
  key(0x72);wait('targets (cached)' if frontend=='shell' else 'TARGET INVENTORY',.25);report['cached_navigation_ms']=frames[-1]['elapsed_ms']
  if frontend=='shell':
   key(0x1b);wait('disked>');type_text('inert watch draft');wait('inert watch draft');wait('earlier request outcome');wait('inert watch draft',after='earlier request outcome')
  else:wait('EARLIER REQUEST RESULT')
  wait('org.disked.fake-operation-event/1');wait('fake.operation.snapshot')
  key(0x79);report['exit']=p.wait(timeout=5);assert report['exit']==0;report['after']=after=snapshot()
  for field in ['modes','codepages','buffer','cursor_style']:
   if before[field]!=after[field]:raise AssertionError('caller console changed '+field)
  deadline=time.monotonic()+5
  while True:
   result=subprocess.run([exe,'operation','inspect',ident,'--state-dir',str(state),'--json'],capture_output=True,timeout=8);value=json.loads(result.stdout)
   if value['result'].get('state',{}).get('phase')=='finished':break
   if time.monotonic()>deadline:raise AssertionError('worker not finished')
   time.sleep(.025)
  report['final']=value;assert value['result']['state']['outcome']=='succeeded';assert value['result']['state']['cancellation']=='not_requested'
 finally:
  if p is not None and p.poll() is None:p.kill();p.wait(timeout=3)
if __name__=='__main__':
 report={};code=0
 try:run(sys.argv[1],sys.argv[3],report)
 except Exception as error:report['fixture_error']=str(error);code=1
 Path(sys.argv[2]).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');raise SystemExit(code)
