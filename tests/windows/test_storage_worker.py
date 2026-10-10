"""Actual owned readers and independent frame/graph expectations; generated replies only."""
import argparse,copy,ctypes,hashlib,json,queue,subprocess,threading,time
from ctypes import wintypes
from pathlib import Path
from test_storage_queries import disk,volume,packet,canonical,digest
from test_volume_namespace import fixture as namespace_fixture

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--probe',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--pointer-bytes',type=int,choices=(4,8),required=True);a=p.parse_args()
    out=a.output.absolute();out.mkdir();probe=a.probe.absolute();checks=[];executions=[];children=set()
    def check(label,ok):checks.append(dict(label=label,passed=bool(ok)));assert ok,label
    def run(label,value,expected=0):
        raw=json.dumps(value,separators=(',',':')).encode();(out/(label+'.request.json')).write_bytes(raw);start=time.monotonic()
        r=subprocess.run([str(probe)],input=raw,capture_output=True,timeout=15);(out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr)
        executions.append(dict(label=label,exit_code=r.returncode,expected_exit=expected,elapsed_seconds=round(time.monotonic()-start,3)))
        check(label+' exact exit',r.returncode==expected and not r.stderr);v=json.loads(r.stdout);check(label+' actual architecture',v['pointer_bytes']==str(a.pointer_bytes))
        for row in v.get('samples',[]):
            w=row['worker'];g=row['capture']['graph'];source=row['capture']['sources'][0]
            if int(w['worker']['pid']):children.add((w['worker']['pid'],w['worker']['created']))
            check(label+' no worker authority',w['claims']==dict(live_namespace=False,physical_admission=False,mutation_authority=False,durable_reconnect=False))
            unbound=copy.deepcopy(g);revision=unbound.pop('revision');check(label+' independent graph hash',revision==digest(unbound))
            check(label+' unaffected peer',sum(n['id']=='fake:peer' for n in g['nodes'])==1)
            for n in g['nodes']:
                if n['id']=='fake:peer':continue
                q=n['properties'];b=q['observation_binding'];payload=q['observation'];context=payload['worker_context']
                check(label+' unknown media and no authority',q['identity'] is None and q['media_generation'] is None and q['capacity_bytes'] is None and q['aliases']==[] and q['physical_identity']=='unknown' and not q['mutation_authority'] and not q['physical_admission'])
                check(label+' actual owned context bound',b['context_digest']==digest(context) and payload.get('binding_scope','owned-reader-context')=='owned-reader-context' and int(context['pid'])>0 and int(context['created'])>0)
                check(label+' observation ID independently derived',n['id']=='observation:'+digest(dict(binding=b,kind=n['kind'],label=q['label'],payload=payload))[7:])
            if w['worker']['observation']=='running':check(label+' live reader remains outstanding',source['outstanding'])
            elif w['worker']['observation'] in ('exited','not_started'):check(label+' reconciled attempt not outstanding',not source['outstanding'])
        return v
    def f(*subjects,**kw):return dict(subjects=list(subjects or (disk(),volume())),**kw)
    def execute(label,mode='sequence',**kw):return run(label,dict(mode=mode,stages=[f(**kw)]))
    def last(v):return v['samples'][-1]
    healthy=execute('healthy');w=last(healthy)['worker'];check('healthy exact child exit',w['status']=='completed' and w['worker']['observation']=='exited' and w['worker']['exit_code']=='0' and w['admitted'])
    check('healthy source and frame complete',last(healthy)['capture']['sources'][0]['state']=='complete' and w['result']['status']=='selected_queries_complete' and len(last(healthy)['capture']['graph']['nodes'])==4)
    context=last(healthy)['capture']['graph']['nodes'][1]['properties']['observation']['worker_context']
    check('owned context matches real session',context['pid']==w['worker']['pid'] and context['created']==w['worker']['created'] and context['code_sha256']==w['code_sha256'] and context['request_digest']==w['request_digest'])
    v=execute('late','late',worker_fault='delay');check('late same process/attempt',len({(x['worker']['attempt_id'],x['worker']['worker']['pid'],x['worker']['worker']['created']) for x in v['samples']})==1)
    check('timeout retains running reader',v['samples'][1]['worker']['status']=='accepted_running' and v['samples'][1]['capture']['sources'][0]['state']=='timed_out' and last(v)['worker']['status']=='completed')
    for label,mode,kw in [('cancel-before','cancel-before',{}),('cancel-during','cancel-during',dict(worker_fault='delay'))]:
        v=execute(label,mode,**kw);check(label+' checkpoint acknowledgement',last(v)['worker']['result']['status']=='cancelled' and last(v)['worker']['cancellation_requested'] and last(v)['worker']['worker']['exit_code']=='0' and last(v)['capture']['sources'][0]['state']=='partial')
    v=execute('held-publication','held',reply_fault='hold');check('publication separate from exit',v['samples'][1]['worker']['status']=='completed' and v['samples'][1]['worker']['worker']['observation']=='running' and v['samples'][1]['capture']['sources'][0]['outstanding'] and last(v)['worker']['worker']['observation']=='exited')
    v=execute('superseded','superseded',worker_fault='delay');check('old capture result discarded',last(v)['worker']['status']=='completed' and last(v)['capture']['capture']=='2' and last(v)['capture']['sources'][0]['state']=='not_started' and len(last(v)['capture']['graph']['nodes'])==1)
    v=execute('reader-retirement','retire',worker_fault='hang');check('retirement not cancellation/success',last(v)['worker']['status']=='unknown' and last(v)['worker']['result'] is None and last(v)['worker']['worker']['exit_code']=='31' and last(v)['worker']['retired'] and not last(v)['worker']['cancellation_requested'])
    v=execute('reader-crash',worker_fault='crash');check('crash stays unknown',last(v)['worker']['result'] is None and last(v)['worker']['worker']['exit_code']=='23' and last(v)['capture']['sources'][0]['state']=='unavailable')
    for fault in ('native_table','native_error'):
        v=execute('refuse-'+fault,worker_fault=fault);check(fault+' not admitted',not last(v)['worker']['admitted'] and last(v)['worker']['worker']['exit_code']=='3' and last(v)['worker']['result'] is None)
    for fault in ('capture','worker','digest','shape','status','claims','schema','capacity'):
        v=execute('bad-reply-'+fault,reply_fault=fault);check(fault+' typed unknown reply',last(v)['worker']['status']=='unknown' and last(v)['worker']['result'] is None and last(v)['worker']['diagnostic'] is not None and len(last(v)['capture']['graph']['nodes'])==1)
    for returned in (0,9):
        d=disk();d['replies']['descriptor']=[packet(ok=False,error=997,returned=returned)];v=run('pending-'+str(returned),dict(mode='held',stages=[f(d,volume(),reply_fault='hold')]))
        check('pending preserved until actual reader exit',v['samples'][1]['worker']['result']['status']=='unresolved' and v['samples'][1]['capture']['sources'][0]['outstanding'] and last(v)['capture']['sources'][0]['state']=='partial')
    d=disk();d['replies']['descriptor']=[dict(packet(),throw=True)];v=run('callback-exception',dict(mode='sequence',stages=[f(d,volume())]));check('callback exception is unknown observation',last(v)['worker']['result']['status']=='unresolved' and last(v)['worker']['result']['resources'][0]['components']['descriptor']['state']=='adapter_exception')
    d=disk();d['replies']['descriptor']=[packet(ok=False,error=5)];v=run('partial-cache',dict(mode='sequence',stages=[f(),f(d,volume()),f(d,volume())]))
    for snapshot in v['retained'][1:]:check('only last complete cache preserved',sum(n['properties']['state']=='stale' for n in snapshot['nodes'] if n['id']!='fake:peer')==3 and len(snapshot['nodes'])==7)
    for mode in ('startup','namespace-startup'):
        for fault in ('before_spawn','after_spawn','after_spawn_alloc'):
            fixture=f(startup_fault=fault) if mode=='startup' else namespace_fixture(startup_fault=fault)
            v=run(mode+'-'+fault,dict(mode=mode,stages=[fixture]));first=v['samples'][0];check(fault+' startup outcome retained',len(v['start_errors'])==1 and first['capture']['sources'][0]['state']=='unavailable')
            check(fault+' accurate launch state',first['worker']['worker']['observation']=='not_started' if fault=='before_spawn' else first['worker']['worker']['observation']=='running')
            check(fault+' eligible new attempt after reconciliation',last(v)['capture']['capture']=='2' and last(v)['capture']['sources'][0]['attempt_worker']=='2' and last(v)['worker']['worker']['exit_code']=='0')
            if fault!='before_spawn':check('post-spawn exact owned retirement',v['samples'][1]['worker']['worker']['pid']==first['worker']['worker']['pid'] and v['samples'][1]['worker']['worker']['created']==first['worker']['worker']['created'] and v['samples'][1]['worker']['worker']['exit_code']=='31')
    snapshot=w['result'];fixture=f(worker_fault='hang');v=run('pure-receipt-reader',dict(mode='read',snapshot=snapshot,fixture=fixture));check('pure reconstruction does not run fixture callback',v['snapshot']==snapshot)
    mutations={
        'authority':lambda v:v['claims'].__setitem__('mutation_authority',True),
        'status':lambda v:v.__setitem__('status','invented'),
        'capacity':lambda v:v['resources'][0]['components']['length']['data'].__setitem__('length_bytes','1'),
        'policy':lambda v:v['policy'].__setitem__('descriptor_bytes','40'),
        'subject':lambda v:v['resources'][0].__setitem__('key','unbound'),
        'receipt-hash':lambda v:v['resources'][0]['components']['length']['receipts'][0].__setitem__('returned_sha256','sha256:'+'0'*64),
        'receipt-control':lambda v:v['resources'][0]['components']['length']['receipts'][0].__setitem__('control','0'),
        'extra-field':lambda v:v.__setitem__('authority_grant',True),
    }
    for label,mutate in mutations.items():
        value=copy.deepcopy(snapshot);mutate(value);run('reject-frame-'+label,dict(mode='read',snapshot=value,fixture=fixture),3)
    for label,fixture in [('empty-subjects',dict(subjects=[])),('duplicate-key',f(disk(),disk())),('invalid-kind',f(dict(disk(),kind='writer')))]:
        run(label,dict(mode='sequence',stages=[fixture]),3)
    for label,args in [('invalid-role',['__disked_nt_storage_fixture_worker']),('unavailable-live',['--live'])]:
        r=subprocess.run([str(probe),*args],capture_output=True,timeout=5);(out/(label+'.stdout')).write_bytes(r.stdout);(out/(label+'.stderr')).write_bytes(r.stderr);executions.append(dict(label=label,exit_code=r.returncode,expected_exit=2));check(label+' finite refusal',r.returncode==2 and not r.stdout and not r.stderr)
    request=json.dumps(dict(mode='disconnect',stages=[f(worker_fault='hang')]),separators=(',',':')).encode();(out/'disconnect.request.json').write_bytes(request)
    process=subprocess.Popen([str(probe)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE);child=None;k=ctypes.WinDLL('kernel32',use_last_error=True)
    k.OpenProcess.argtypes=(wintypes.DWORD,wintypes.BOOL,wintypes.DWORD);k.OpenProcess.restype=wintypes.HANDLE;k.WaitForSingleObject.argtypes=(wintypes.HANDLE,wintypes.DWORD);k.WaitForSingleObject.restype=wintypes.DWORD;k.CloseHandle.argtypes=(wintypes.HANDLE,)
    k.GetProcessTimes.argtypes=(wintypes.HANDLE,ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME),ctypes.POINTER(wintypes.FILETIME));k.GetProcessTimes.restype=wintypes.BOOL
    try:
        process.stdin.write(request);process.stdin.close();lines=queue.Queue();threading.Thread(target=lambda:lines.put(process.stdout.readline()),daemon=True).start();line=lines.get(timeout=15);(out/'disconnect.stdout').write_bytes(line);v=json.loads(line)['worker'];children.add((v['worker']['pid'],v['worker']['created']))
        child=k.OpenProcess(0x100000|0x1000,False,int(v['worker']['pid']));check('disconnect actual process handle',bool(child));times=[wintypes.FILETIME() for _ in range(4)]
        check('disconnect exact creation identity',k.GetProcessTimes(child,*[ctypes.byref(x) for x in times]) and str((times[0].dwHighDateTime<<32)|times[0].dwLowDateTime)==v['worker']['created'])
        check('disconnect reader live now',k.WaitForSingleObject(child,0)==258);process.terminate();process.wait(timeout=5);executions.append(dict(label='disconnect',exit_code=process.returncode,termination='Owned controller only'))
        check('disconnect closes owned reader job',k.WaitForSingleObject(child,2000)==0);(out/'disconnect.stderr').write_bytes(process.stderr.read())
    finally:
        if child:k.CloseHandle(child)
        if process.poll() is None:process.kill();process.wait(timeout=5)
        if process.stdout:process.stdout.close()
        if process.stderr:process.stderr.close()
    result=dict(status='pass',pointer_bytes=a.pointer_bytes,controller_executions=len(executions),actual_child_launches=len(children),assertions=len(checks),checks=checks,executions=executions,artifact_sha256='sha256:'+hashlib.sha256(probe.read_bytes()).hexdigest(),owned_injected_reader_qualified=True,live_storage_qualified=False,physical_access=False,provider_admitted=False,historical_windows_qualified=False,owner_accepted=False,unit_complete=False)
    (out/'results.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps({k:v for k,v in result.items() if k not in ('checks','executions')}))
if __name__=='__main__':main()
