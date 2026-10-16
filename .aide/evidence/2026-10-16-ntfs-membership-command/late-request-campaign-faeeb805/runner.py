from pathlib import Path
from datetime import datetime,timezone
import hashlib,json,os,queue,subprocess,sys,tempfile,time
root=Path.cwd();sys.path[:0]=[str(root/'tests/frontend'),str(root/'tests/images')]
from protocol_trace import ProtocolTrace
from test_ntfs_commands import canonical,write,file_digest,Gate
from ntfs_directory_fixture import DirectoryVolume
from ntfs_membership_fixture import MembershipVolume
out=root/'.aide-local/ntfs-late-request-campaign-faeeb805';out.mkdir()
exe=(root/'.aide-local/ntfs-membership-command-qualification-faeeb805/build/Release/disked_ntfs_test.exe').resolve()
sources={};summaries=[];status='running'
for view,volume,prefix in [('ntfs-directory',DirectoryVolume(minor=1,offset=173),'disked-ntfs-directory-command-'),('ntfs-membership',MembershipVolume(minor=1,offset=173,list_form='nonresident'),'disked-membership-command-')]:
 directory=Path(tempfile.mkdtemp(prefix=prefix));path=directory/'generated-1.img';write(volume,path)
 sources[view]=dict(path=path,volume=volume,before=file_digest(path))
env={k:v for k,v in os.environ.items() if not k.startswith('DISKED_')}
def save():
 value=dict(recorded_at=datetime.now(timezone.utc).isoformat(),status=status,planned_cases=24,completed_cases=len(summaries),binary_source_revision='faeeb805cdf81b1f8ab83af04a1b330d8680b375',binary_sha256='sha256:'+hashlib.sha256(exe.read_bytes()).hexdigest(),harness_sha256='sha256:'+hashlib.sha256((root/'tests/frontend/protocol_trace.py').read_bytes()).hexdigest(),scope='Fixed24-case source-free-control diagnostic using two generated ordinary sources,12 directory and12 membership cases. No fresh qualification or repeated-until-pass stopping rule. Original admission deadlines/assertions unchanged; observation after a failed assertion never changes that case to pass.',cases=summaries,source_receipts={k:dict(path=str(v['path']),before=v['before'],after=file_digest(v['path'])) for k,v in sources.items()},original_failure_causes_established=False,owner_accepted=False)
 (out/'summary.json').write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
for number in range(24):
 view=('ntfs-directory','ntfs-membership')[number%2];entry=sources[view];path=entry['path'];volume=entry['volume'];case=out/f'case-{number:02d}';case.mkdir()
 gate=Gate();process=subprocess.Popen([str(exe),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root/'.aide-local/ntfs-member-source',env=dict(env,DISKED_NTFS_COMMAND_TEST_GATE=gate.name))
 trace=ProtocolTrace(process,case/'protocol.json',canonical);parameters=dict(path=str(path),view=view,volume_offset=volume.input['offset'],volume_bytes=volume.input['length']);code=None;error=None;passed=False
 def request(parameters,ident='ntfs-directory:req'):
  return dict(schema='org.disked.request/1',request_id=ident,command='image.inspect',parameters=parameters,required_features=[])
 try:
  trace.send(request(parameters));gate.entered();trace.event('gate_entered');expired=trace.get(6)
  assert expired['status']=='unknown' and expired['diagnostics'][0]['code']=='request_wait_expired'
  try:
   with path.open('r+b'):raise AssertionError('Source writable before actual completion')
  except PermissionError:trace.event('source_remains_pinned')
  trace.send(request(parameters,'busy'));assert trace.get(2)['diagnostics'][0]['code']=='request_resource_limit'
  essential=request({},'essential');essential['command']='command.list';trace.send(essential);assert trace.get(2)['status']=='completed'
  trace.event('gate_release');gate.release();after=None
  for attempt in range(35):
   time.sleep(.1);trace.send(request(parameters,'fresh'));after=trace.get(3)
   if after['status']=='completed':break
   assert after['diagnostics'][0]['code']=='request_resource_limit'
  trace.event('original_final_assertion',after_status=after and after['status'],queue_empty=trace.messages.empty())
  assert after and after['status']=='completed' and trace.messages.empty()
  process.stdin.close();code=process.wait(timeout=8);stderr=process.stderr.read();(case/'stderr.bin').write_bytes(stderr);assert code==6 and not stderr
  passed=True
 except BaseException as failure:
  error=repr(failure);trace.event('admission_failed',error=error);trace.snapshot('failure_state')
  # This interval only records a late frame after the case has already failed.
  # It does not increase a test or runtime admission deadline.
  finish=time.monotonic()+10
  while time.monotonic()<finish and process.poll() is None:
   time.sleep(.1)
   if trace.messages.qsize():trace.snapshot('post_failure_late_frame');break
 finally:
  gate.release();gate.close()
  if process.poll() is None:
   if not process.stdin.closed:process.stdin.close()
   try:code=process.wait(timeout=15)
   except subprocess.TimeoutExpired:trace.event('parent_still_running',pid=process.pid)
  else:code=process.returncode
  trace.thread.join(timeout=1);trace.snapshot('final_observation')
  unchanged=file_digest(path)==entry['before'];assert unchanged
  summaries.append(dict(number=number,view=view,passed_original_expectations=passed,error=error,parent_returncode=code,frames=len(trace.frames),source_unchanged=unchanged,trace=str(trace.log)))
  save();print(number,view,passed,error,code,len(trace.frames),flush=True)
  if code is None:status='stopped-parent-still-running';save();break
else:status='completed';save()
print('Diagnostic completed:',len(summaries),'original-expectation failures:',sum(not r['passed_original_expectations'] for r in summaries),flush=True)
