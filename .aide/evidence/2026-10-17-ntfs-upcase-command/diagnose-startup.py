"""Bounded observations of the failed,unchanged reader binary; generated owned bytes only."""
import argparse
import concurrent.futures
import ctypes as c
from ctypes import wintypes as w
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time

parser=argparse.ArgumentParser()
for key in ('root','binary','failure','output'):parser.add_argument('--'+key,type=Path,required=True)
a=parser.parse_args();a.root=a.root.resolve();a.binary=a.binary.resolve();a.failure=a.failure.resolve();a.output=a.output.resolve();a.output.mkdir()
sys.path[:0]=[str(a.root/'tests/frontend'),str(a.root/'tests/images')]
from test_ntfs_directory_commands import large_volume,CAPS,DIRECTORY
from test_ntfs_commands import canonical,write,file_digest,digest

class Entry(c.Structure):
    _fields_=[('size',w.DWORD),('usage',w.DWORD),('pid',w.DWORD),('heap',c.c_size_t),
              ('module',w.DWORD),('threads',w.DWORD),('parent',w.DWORD),('priority',w.LONG),
              ('flags',w.DWORD),('exe',w.WCHAR*260)]
class Io(c.Structure):
    _fields_=[(key,c.c_ulonglong) for key in ('read_ops','write_ops','other_ops','read_bytes','write_bytes','other_bytes')]
k=c.WinDLL('kernel32',use_last_error=True)
k.CreateToolhelp32Snapshot.argtypes=[w.DWORD,w.DWORD];k.CreateToolhelp32Snapshot.restype=w.HANDLE
k.Process32FirstW.argtypes=[w.HANDLE,c.POINTER(Entry)];k.Process32FirstW.restype=w.BOOL
k.Process32NextW.argtypes=[w.HANDLE,c.POINTER(Entry)];k.Process32NextW.restype=w.BOOL
k.CloseHandle.argtypes=[w.HANDLE];k.CloseHandle.restype=w.BOOL
k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
k.GetProcessTimes.argtypes=[w.HANDLE,*([c.POINTER(w.FILETIME)]*4)];k.GetProcessTimes.restype=w.BOOL
k.GetProcessIoCounters.argtypes=[w.HANDLE,c.POINTER(Io)];k.GetProcessIoCounters.restype=w.BOOL
k.GetExitCodeProcess.argtypes=[w.HANDLE,c.POINTER(w.DWORD)];k.GetExitCodeProcess.restype=w.BOOL
assert c.sizeof(Io)==48 and c.sizeof(Entry)==568
def stamp(t):return (t.dwHighDateTime<<32)|t.dwLowDateTime
def children(parent):
    handle=k.CreateToolhelp32Snapshot(2,0)
    if handle==c.c_void_p(-1).value:return []
    try:
        result=[];entry=Entry();entry.size=c.sizeof(entry);more=k.Process32FirstW(handle,c.byref(entry))
        while more:
            if entry.parent==parent and entry.exe.casefold()==a.binary.name.casefold():result.append(entry.pid)
            more=k.Process32NextW(handle,c.byref(entry))
        return result
    finally:k.CloseHandle(handle)
def observe(handle):
    times=[w.FILETIME() for _ in range(4)];io=Io();exit=w.DWORD()
    value={}
    if k.GetProcessTimes(handle,*(c.byref(t) for t in times)):
        value.update(created=str(stamp(times[0])),kernel_ticks=stamp(times[2]),user_ticks=stamp(times[3]))
    else:value['times_error']=c.get_last_error()
    if k.GetProcessIoCounters(handle,c.byref(io)):value.update({key:getattr(io,key) for key,_ in Io._fields_})
    else:value['io_error']=c.get_last_error()
    if k.GetExitCodeProcess(handle,c.byref(exit)):value['exit_code']=exit.value
    return value

failure=json.loads(a.failure.read_bytes());assert failure['source_revision']==subprocess.check_output(['git','rev-parse','HEAD'],cwd=a.root,text=True).strip()
binary_sha='sha256:'+hashlib.sha256(a.binary.read_bytes()).hexdigest()
assert binary_sha.removeprefix('sha256:')==failure['raw_worker']['before']['code_sha256']
summary=dict(status='running',recorded_at=datetime.now(timezone.utc).isoformat(),source_revision=failure['source_revision'],
             binary_sha256=binary_sha,recipe_sha256='sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
             original_startup_budget_ms=1000,original_retirement_exit_code=31,samples=[],qualification=False,
             original_failure_explained=False,deadlines_changed=False,owner_accepted=False,full_0_1_0_complete=False)
def save():(a.output/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
with tempfile.TemporaryDirectory(prefix='disked-upcase-startup-diagnostic-') as directory:
    owned=Path(directory).resolve();assert owned.parent==Path(tempfile.gettempdir()).resolve()
    volume=large_volume();path=owned/'same-generated-bytes.img';write(volume,path);before=file_digest(path)
    report=json.loads((a.failure.parent/'native-details/ntfs-directory-command-cases.json').read_bytes())
    assert before==report['source_receipts'][-1]['before_sha256']
    request=dict(path=str(path),offset=volume.input['offset'],length=volume.input['length'],capture_epoch='9',limits=CAPS,directory=dict(reference='0',limits=DIRECTORY))
    summary.update(source_sha256=before,source_bytes=path.stat().st_size,input_sha256=digest(request),
        scope='Six bounded launches of exact failed binary and byte-identical generated large-directory content at a new owned path/generation. This is a diagnostic,not qualification or a retry of a storage effect.')
    for index in range(6):
        start=time.monotonic();process=subprocess.Popen([str(a.binary)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=a.root)
        handles={};timeline=[]
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
                task=pool.submit(process.communicate,canonical(request),timeout=35)
                while not task.done():
                    for pid in children(process.pid):
                        if pid not in handles:
                            handle=k.OpenProcess(0x1400|0x100000,False,pid)
                            if handle:handles[pid]=handle
                    timeline.append(dict(seconds=time.monotonic()-start,children={str(pid):observe(h) for pid,h in handles.items()}))
                    time.sleep(.05)
                stdout,stderr=task.result()
            raw=a.output/('sample-'+str(index)+'.json');raw.write_bytes(stdout)
            value=json.loads(stdout);worker=value.get('retirement',{}).get('worker',{})
            final={str(pid):observe(h) for pid,h in handles.items()}
            for pid,metrics in final.items():
                if pid==worker.get('pid'):assert metrics.get('created')==worker['created']
            summary['samples'].append(dict(index=index,parent_pid=process.pid,exit_code=process.returncode,
                seconds=time.monotonic()-start,has_snapshot=value.get('has_snapshot'),before_status=value.get('before',{}).get('status'),
                before_admitted=value.get('before',{}).get('admitted'),retirement=value.get('retirement'),timeline=timeline,final_process_metrics=final,
                raw_output=raw.name,raw_sha256='sha256:'+hashlib.sha256(stdout).hexdigest(),stderr=stderr.decode(errors='replace')))
            save();print('SAMPLE',index,'snapshot',value.get('has_snapshot'),'seconds',round(summary['samples'][-1]['seconds'],3),flush=True)
            assert process.returncode==0 and not stderr
        finally:
            for handle in handles.values():k.CloseHandle(handle)
            if process.poll() is None:process.kill();process.wait(timeout=5)
    assert file_digest(path)==before
    summary['source_preserved']=True
summary['status']='observed';save();print('Diagnostic complete; original failure remains unexplained unless its causal evidence establishes otherwise',flush=True)
