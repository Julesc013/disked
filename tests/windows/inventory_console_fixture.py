"""Owned hidden console for injected inventory renderers; no foreground input."""
import json,re,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parents[2];sys.path.insert(0,str(root/'tests/frontend'))
from console_tui_fixture import k,w,c,checked,configure,key,snapshot,active,info,Coord
def current_text():
 handle=active()
 try:
  value=info(handle);count=min(value.size.X*max(value.cursor.Y+1,value.window.Bottom+1),262144)
  buffer=c.create_unicode_buffer(count+1);got=w.DWORD();checked(k.ReadConsoleOutputCharacterW(handle,buffer,count,Coord(0,0),c.byref(got)))
  return '\n'.join(buffer[i:min(i+value.size.X,got.value)].rstrip() for i in range(0,got.value,value.size.X))
 finally:k.CloseHandle(handle)
probe,mode,request,receipt,report_path=sys.argv[1:]
report={};p=None
try:
 configure(k.GetStdHandle(-11),160,25);before=snapshot();report['before']=before;frames=[];report['frames']=frames
 def wait_text(needle):
  end=time.monotonic()+8
  while time.monotonic()<end:
   text=current_text()
   if needle in text:frames.append(dict(contains=needle,text=text));return text
   if p.poll() is not None:raise AssertionError('Exited before '+needle+': '+str(p.returncode)+'\n'+text)
   time.sleep(.02)
  raise AssertionError('Missing '+needle+'\n'+text)
 p=subprocess.Popen([probe,'__disked_nt_inventory_renderer_fixture',mode,request,receipt],close_fds=False)
 wait_text('CACHED OBSERVATIONS');wait_text('OBSERVATION INVENTORY' if mode=='tui' else 'disked>')
 if mode=='tui':
  key(13,'\r');wait_text('observation-only');key(0x74);wait_text('View refreshed')
 else:
  def submit(command,identity,needle):
   for character in command:key(0,character)
   key(0x78);wait_text('F9 submits: '+identity);key(0x78);return wait_text(needle)
  listing=submit('target list','target.list','observation_ids')
  node=re.search(r'observation:[0-9a-f]{64}',listing).group(0)
  submit('target inspect '+node,'target.inspect','shell:2')
  submit('health assess '+node,'health.assess','observation_not_storage_target')
  report['inspected_id']=node
 key(0x79);report['exit']=p.wait(timeout=6);assert report['exit']==0
 after=snapshot();report['after']=after;report['receipt']=json.loads(Path(receipt).read_bytes());assert report['receipt']['retained_after_session_and_renderer']
 for name in ('modes','codepages','cursor_style','attributes'):assert after[name]==before[name],name+' not restored'
 report['status']='pass'
except Exception as error:report['status']='fail';report['error']=str(error)
finally:
 if p is not None and p.poll() is None:p.kill();p.wait(timeout=5)
 Path(report_path).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
raise SystemExit(0 if report.get('status')=='pass' else 1)
