from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,queue,subprocess,sys,threading,time
root=Path.cwd();sys.path[:0]=[str(root/'tests/frontend'),str(root/'tests/images')]
from ntfs_membership_fixture import MembershipVolume
from test_ntfs_commands import canonical,write,file_digest,Gate
out=Path('.aide-local/ntfs-membership-late-slot-diagnostic-1');out.mkdir()
exe=(root/'.aide-local/report-phases-build/Release/disked_ntfs_test.exe').resolve();path=(out/'generated.img').resolve()
volume=MembershipVolume(minor=1,offset=173,list_form='nonresident');write(volume,path);before=file_digest(path)
gate=Gate();started=time.monotonic();lock=threading.Lock();events=[];messages=queue.Queue();frames=[]
def event(kind,**values):
 with lock:
  row=dict(seconds=time.monotonic()-started,kind=kind,**values);events.append(row)
  with (out/'trace.jsonl').open('a',encoding='utf-8',newline='\n') as log:log.write(json.dumps(row)+'\n')
def wire(parameters,ident='membership:req'):
 return dict(schema='org.disked.request/1',request_id=ident,command='image.inspect',parameters=parameters,required_features=[])
parameters=dict(path=str(path),view='ntfs-membership',volume_offset=volume.input['offset'],volume_bytes=volume.input['length'])
env={k:v for k,v in os.environ.items() if not k.startswith('DISKED_')};env['DISKED_NTFS_COMMAND_TEST_GATE']=gate.name
process=subprocess.Popen([str(exe),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env)
def receive():
 try:
  for raw in process.stdout:
   frame=out/f'frame-{len(frames)}.json';frame.write_bytes(raw);frames.append(frame.name)
   value=json.loads(raw);event('frame',request_id=value.get('request_id'),status=value.get('status'),diagnostics=value.get('diagnostics'),raw=frame.name)
   messages.put(value)
 except BaseException as error:event('receiver_error',error=repr(error))
thread=threading.Thread(target=receive,daemon=True);thread.start()
def send(value):
 event('send',request_id=value['request_id'],command=value['command']);process.stdin.write(canonical(value)+b'\n');process.stdin.flush()
def get(timeout):
 value=messages.get(timeout=timeout);event('dequeue',request_id=value.get('request_id'),status=value.get('status'),remaining=messages.qsize());return value
status='running';error=None;returncode=None;stderr=None
try:
 send(wire(parameters));gate.entered();event('gate_entered');expired=get(6)
 assert expired['status']=='unknown' and expired['diagnostics'][0]['code']=='request_wait_expired'
 try:
  with path.open('r+b'):raise AssertionError('Source writable before actual completion')
 except PermissionError:event('source_remains_pinned')
 send(wire(parameters,'busy'));assert get(2)['diagnostics'][0]['code']=='request_resource_limit'
 essential=wire({},'essential');essential['command']='command.list';send(essential);assert get(2)['status']=='completed'
 event('gate_release');gate.release();after=None
 for attempt in range(35):
  time.sleep(.1);send(wire(parameters,'fresh'));after=get(3);event('attempt',attempt=attempt,status=after['status'],pending=messages.qsize())
  if after['status']=='completed':break
  assert after['diagnostics'][0]['code']=='request_resource_limit'
 event('final_assertion',has_after=after is not None,after_status=after and after['status'],queue_empty=messages.empty(),pending=messages.qsize())
 assert after and after['status']=='completed' and messages.empty()
 process.stdin.close();returncode=process.wait(timeout=8);stderr=process.stderr.read();assert returncode==6 and not stderr
 status='pass'
except BaseException as failure:status='failed';error=repr(failure);event('failure',error=error)
finally:
 gate.release();gate.close()
 if process.poll() is None:
  if not process.stdin.closed:process.stdin.close()
  try:returncode=process.wait(timeout=15)
  except subprocess.TimeoutExpired:event('parent_still_running',pid=process.pid)
 else:returncode=process.returncode
 thread.join(timeout=1)
 event('teardown_observation',parent_returncode=returncode,receiver_alive=thread.is_alive(),queued=messages.qsize())
 if returncode is not None:
  if stderr is None:stderr=process.stderr.read()
  (out/'stderr.bin').write_bytes(stderr)
 after_hash=file_digest(path)
 summary=dict(recorded_at=datetime.now(timezone.utc).isoformat(),status=status,error=error,command=[str(exe),'protocol','serve','--format=ndjson'],cwd=str(root),binary_sha256='sha256:'+hashlib.sha256(exe.read_bytes()).hexdigest(),source_before=before,source_after=after_hash,source_unchanged=before==after_hash,parent_returncode=returncode,timeout_policy='Original1000ms gate-enter/6s expiry/35x0.1s fresh poll/3s receive/8s normal exit expectations unchanged.15s failure observation is diagnostic teardown, not added admission time.',events=events,frames=frames,original_working_failure_cause_established=False,owner_accepted=False)
 (out/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(status=status,error=error,parent_returncode=returncode,frames=len(frames),source_unchanged=before==after_hash)))
sys.exit(0 if status=='pass' else 1)
