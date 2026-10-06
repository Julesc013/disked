"""Test-owned prospective hierarchy; does not establish a product memory policy."""
import ctypes as C
from ctypes import wintypes as W
import hashlib,json,subprocess,tempfile,time
from pathlib import Path
K=C.WinDLL('kernel32',use_last_error=True)
K.CreateJobObjectW.argtypes=[C.c_void_p,W.LPCWSTR];K.CreateJobObjectW.restype=W.HANDLE
K.SetInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD]
K.AssignProcessToJobObject.argtypes=[W.HANDLE,W.HANDLE]
K.QueryInformationJobObject.argtypes=[W.HANDLE,C.c_int,C.c_void_p,W.DWORD,C.c_void_p]
K.OpenProcess.argtypes=[W.DWORD,W.BOOL,W.DWORD];K.OpenProcess.restype=W.HANDLE
K.IsProcessInJob.argtypes=[W.HANDLE,W.HANDLE,C.POINTER(W.BOOL)]
K.GetProcessTimes.argtypes=[W.HANDLE]+[C.POINTER(W.FILETIME)]*4
K.WaitForSingleObject.argtypes=[W.HANDLE,W.DWORD];K.CloseHandle.argtypes=[W.HANDLE]
class Basic(C.Structure):
 _fields_=[('times',C.c_int64*2),('flags',W.DWORD),('minimum',C.c_size_t),('maximum',C.c_size_t),('active',W.DWORD),('affinity',C.c_size_t),('priority',W.DWORD),('scheduling',W.DWORD)]
class Limits(C.Structure):
 _fields_=[('basic',Basic),('io',C.c_uint64*6),('process_memory',C.c_size_t),('job_memory',C.c_size_t),('peak_process',C.c_size_t),('peak_job',C.c_size_t)]
def check(value):
 if not value:raise C.WinError(C.get_last_error())
 return value
R=Path.cwd();exe=R/'build/windows-bootstrap/Release/disked.exe'
observations=[];clients=[];workers=[];job=check(K.CreateJobObjectW(None,None))
limits=Limits();limits.basic.flags=0x100;limits.process_memory=256*1024*1024
check(K.SetInformationJobObject(job,9,C.byref(limits),C.sizeof(limits)))
try:
 with tempfile.TemporaryDirectory(prefix='disked-memory-hierarchy-') as directory:
  try:
   states=[]
   for i in range(2):
    state=Path(directory)/str(i);state.mkdir();states.append(state)
    p=subprocess.Popen([str(exe),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE)
    clients.append(p)
    # The process is awaiting its first input; it cannot yet admit any work.
    check(K.AssignProcessToJobObject(job,int(p._handle)))
   for i,(p,state) in enumerate(zip(clients,states)):
    request=dict(schema='org.disked.request/1',request_id=str(i),command='plan.simulate',parameters=dict(fixture_id='fake:cancel-checkpoint',state_directory=str(state)),required_features=[])
    p.stdin.write(json.dumps(request).encode()+b'\n');p.stdin.flush()
    value=json.loads(p.stdout.readline());assert value['status']=='accepted_running',value
    binding=value['result']['state']['binding'];worker=check(K.OpenProcess(0x1000|0x100000,False,int(binding['process_id'])));workers.append(worker)
    times=[W.FILETIME() for _ in range(4)];check(K.GetProcessTimes(worker,*map(C.byref,times)))
    assert (times[0].dwLowDateTime|(times[0].dwHighDateTime<<32))==int(binding['process_created'])
    member=W.BOOL();check(K.IsProcessInJob(worker,job,C.byref(member)));assert member.value
    observations.append(dict(admission=value,worker_in_common_job=bool(member.value)))
   for p in clients:p.stdin.close();assert p.wait(timeout=4)==5
   for worker in workers:assert K.WaitForSingleObject(worker,0)==258,'worker did not remain independent after client exit'
   for worker in workers:assert K.WaitForSingleObject(worker,5000)==0
   for observation,state in zip(observations,states):
    p=subprocess.run([str(exe),'operation','inspect',observation['admission']['operation_id'],'--state-dir',str(state),'--json'],capture_output=True,timeout=5)
    value=json.loads(p.stdout);assert p.returncode==0 and value['result']['state']['outcome']=='succeeded',value
    observation['final']=value
  finally:
   for p in clients:
    if p.poll() is None:p.kill();p.wait(timeout=5)
    for stream in [p.stdin,p.stdout,p.stderr]:
     if not stream.closed:stream.close()
   for worker in workers:K.WaitForSingleObject(worker,5000)
 check(K.QueryInformationJobObject(job,9,C.byref(limits),C.sizeof(limits),None))
 evidence=dict(status='PASS',scope='Test-owned prospective shared memory-job hierarchy, not product enforcement',executable=str(exe),sha256=hashlib.sha256(exe.read_bytes()).hexdigest(),
  test_job_process_memory_limit=limits.process_memory,peak_process_bytes=limits.peak_process,peak_job_bytes=limits.peak_job,observations=observations,
  unverified=['Product startup policy and essential-command compatibility','Actual frontend allocation denial','GUI/TUI/shell workload memory','Inherited restrictive host jobs','Other hosts'])
 path=R/'.aide/evidence/2026-10-07-store-failures/prospective-memory-hierarchy.json'
 path.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n');print(path)
finally:
 for worker in workers:K.CloseHandle(worker)
 K.CloseHandle(job)
