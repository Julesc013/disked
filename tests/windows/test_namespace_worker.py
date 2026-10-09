"""Real owned Windows reader processes; injected volume APIs, no live inventory."""
import argparse,ctypes,json,queue,subprocess,threading,time
from ctypes import wintypes
from pathlib import Path
from test_volume_namespace import fixture,CLAIMS

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pointer-bytes',type=int,choices=(4,8),required=True)
    a=p.parse_args();out=a.output.absolute();out.mkdir();probe=a.probe.absolute();checks=[];executions=[];children=set()
    def save():
        (out/'results.json').write_text(json.dumps(dict(status='pass' if all(x['passed'] for x in checks) else 'fail',checks=checks,executions=executions,
            assertions=len(checks),controller_executions=len(executions),actual_child_launches=len(children),pointer_bytes=a.pointer_bytes,live_namespace_qualified=False,physical_access=False,owner_accepted=False,unit_complete=False),indent=2)+'\n',encoding='utf-8',newline='\n')
    def check(name,value):
        checks.append(dict(name=name,passed=bool(value)));save();assert value,name
    def run(label,scenario='normal',worker_fault='',reply_fault='',**changes):
        request=dict(scenario=scenario,fixture=fixture(worker_fault=worker_fault,reply_fault=reply_fault,**changes));data=json.dumps(request,separators=(',',':')).encode()
        (out/(label+'.request.json')).write_bytes(data);start=time.monotonic();r=subprocess.run([str(probe)],input=data,capture_output=True,timeout=15)
        (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
        executions.append(dict(label=label,command=[str(probe)],exit_code=r.returncode,elapsed_seconds=round(time.monotonic()-start,3)));save();return r,json.loads(r.stdout)
    def admitted(label,value):
        check(label+' architecture',value['pointer_bytes']==str(a.pointer_bytes))
        rows=value['observations'];first=rows[0]
        check(label+' stable attempt',all(x['attempt_id']==first['attempt_id'] and x['worker_epoch']==first['worker_epoch'] and x['observer_epoch']==first['observer_epoch'] and x['capture_epoch']==first['capture_epoch'] for x in rows))
        check(label+' stable process',all(x['worker']['pid']==first['worker']['pid'] and x['worker']['created']==first['worker']['created'] for x in rows))
        children.add((first['worker']['pid'],first['worker']['created']))
        check(label+' no authority',all(x['claims']==dict(live_namespace=False,physical_admission=False,mutation_authority=False,durable_reconnect=False) for x in rows))
        return rows[-1],rows
    r,v=run('normal');check('normal controller exit',r.returncode==0);last,rows=admitted('normal',v)
    check('complete real child exit',last['status']=='completed' and last['worker']['observation']=='exited' and last['worker']['exit_code']=='0' and last['admitted'])
    check('complete injected snapshot',last['result']['status']=='complete' and last['result']['api_binding']=='injected-win32-table' and last['result']['claims']==CLAIMS)
    check('code/request identities',len(last['request_digest'])==64 and len(last['code_sha256'])==64 and int(last['worker']['pid'])>0 and int(last['worker']['created'])>0)
    r,v=run('late','late','delay');check('late controller exit',r.returncode==0);last,rows=admitted('late',v)
    check('timeout is active original reader',rows[1]['status']=='accepted_running' and rows[1]['worker']['observation']=='running' and rows[1]['result'] is None)
    check('late bound result retained',last['status']=='completed' and last['result']['status']=='complete' and not last['retired'] and not last['cancellation_requested'])
    r,v=run('cancel-before','before');check('before controller exit',r.returncode==0);last,rows=admitted('before',v)
    check('checkpoint cancellation before query',last['status']=='completed' and last['result']['status']=='cancelled' and last['result']['records']==[] and last['result']['close']['state']=='not_open' and last['cancellation_requested'])
    r,v=run('cancel-during','during','delay');check('during controller exit',r.returncode==0);last,rows=admitted('during',v)
    check('checkpoint cancellation after query',last['status']=='completed' and last['result']['status']=='cancelled' and len(last['result']['records'])==1 and last['result']['records'][0]['mounts']['state']=='cancelled' and last['result']['close']['state']=='closed')
    r,v=run('retire-hang','retire','hang');check('retire controller exit',r.returncode==0);last,rows=admitted('retire',v)
    check('hung reader remains active until retirement',rows[1]['status']=='accepted_running' and rows[1]['worker']['observation']=='running')
    check('retirement is not cancellation or success',last['status']=='unknown' and last['result'] is None and last['worker']['observation']=='exited' and last['worker']['exit_code']=='31' and last['retired'] and not last['cancellation_requested'])
    r,v=run('crashed','normal','crash');check('crash controller exit',r.returncode==0);last,rows=admitted('crash',v)
    check('crashed reader has unknown capture',last['status']=='unknown' and last['worker']['exit_code']=='23' and last['worker']['observation']=='exited' and last['result'] is None)
    r,v=run('native-binding-refused','normal','native_table');check('native binding controller exit',r.returncode==0);last,rows=admitted('native binding',v)
    check('native table refused before admission/dispatch',last['status']=='unknown' and last['result'] is None and last['worker']['exit_code']=='3' and last['worker']['observation']=='exited' and not last['admitted'])
    for fault in ('capture','worker','digest','shape','status','claims','schema'):
        r,v=run('stale-'+fault,'stale',reply_fault=fault);check(fault+' controller exit',r.returncode==0);last,rows=admitted(fault,v)
        check(fault+' refuses result without replacement',last['status']=='unknown' and last['result'] is None and last['diagnostic'] in ('namespace_reply_binding','namespace_publication_digest','namespace_snapshot_shape','namespace_snapshot_claims') and last['worker']['observation']=='exited')
    r,v=run('published-before-exit','published',reply_fault='hold');check('published controller exit',r.returncode==0);last,rows=admitted('published',v)
    check('snapshot and worker exit are separate',rows[1]['status']=='completed' and rows[1]['worker']['observation']=='running' and rows[1]['result']['status']=='complete' and last['worker']['observation']=='exited')
    r,v=run('invalid-wait','invalid_wait');check('budget controller exit',r.returncode==0);last,rows=admitted('budget',v);check('invalid wait preserves attempt',last['status']=='completed')
    for label,changes in [('zero-capture',dict(capture_epoch='0')),('wide-capture',dict(capture_epoch='18446744073709551616')),('zero-volumes',dict(volume_limit='0')),('too-many-volumes',dict(volume_limit='65'))]:
        r,v=run(label,**changes);check(label+' refused before launch',r.returncode==3 and v['status']=='refused')
    for label,args in [('invalid-role',['__disked_nt_namespace_fixture_worker']),('unavailable-live',['--live'])]:
        command=[str(probe),*args];r=subprocess.run(command,capture_output=True,timeout=5)
        (out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
        executions.append(dict(label=label,command=command,exit_code=r.returncode));check(label+' finite refusal',r.returncode==2 and not r.stdout)
    request=json.dumps(dict(scenario='hold',fixture=fixture(worker_fault='hang',reply_fault='')),separators=(',',':')).encode();(out/'disconnect.request.json').write_bytes(request)
    process=subprocess.Popen([str(probe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);child=None
    k=ctypes.WinDLL('kernel32',use_last_error=True);k.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD);k.OpenProcess.restype=wintypes.HANDLE
    k.WaitForSingleObject.argtypes=(wintypes.HANDLE,wintypes.DWORD);k.WaitForSingleObject.restype=wintypes.DWORD;k.CloseHandle.argtypes=(wintypes.HANDLE,);k.CloseHandle.restype=wintypes.BOOL
    k.GetProcessTimes.argtypes=(wintypes.HANDLE,ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME));k.GetProcessTimes.restype=wintypes.BOOL
    try:
        process.stdin.write(request);process.stdin.close();lines=queue.Queue();reader=threading.Thread(target=lambda:lines.put(process.stdout.readline()),daemon=True);reader.start();line=lines.get(timeout=15)
        (out/'disconnect.stdout').write_bytes(line);observed=json.loads(line);children.add((observed['worker']['pid'],observed['worker']['created']))
        child=k.OpenProcess(0x100000|0x1000,False,int(observed['worker']['pid']));check('disconnect child process handle',bool(child))
        times=[wintypes.FILETIME() for _ in range(4)];check('disconnect exact creation identity',k.GetProcessTimes(child,*[ctypes.byref(x) for x in times]) and str((times[0].dwHighDateTime<<32)|times[0].dwLowDateTime)==observed['worker']['created'])
        check('disconnect actual child running',k.WaitForSingleObject(child,0)==258 and observed['status']=='accepted_running')
        process.terminate();process.wait(timeout=5);executions.append(dict(label='disconnect',command=[str(probe)],exit_code=process.returncode,termination='Owned controller termination'))
        check('disconnect job closes owned reader',k.WaitForSingleObject(child,2000)==0)
        (out/'disconnect.stderr').write_bytes(process.stderr.read())
    finally:
        if child:k.CloseHandle(child)
        if process.poll() is None:process.kill();process.wait(timeout=5)
        if process.stdout:process.stdout.close()
        if process.stderr:process.stderr.close()
    save();print(json.dumps(dict(status='pass',controller_executions=len(executions),actual_child_launches=len(children),assertions=len(checks),pointer_bytes=a.pointer_bytes)))
if __name__=='__main__':main()
