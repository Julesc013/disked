"""Native private report observations; generated inputs and independent hashes.

Producer frames below come from actual retained report workers. Altered reader
frames are explicitly synthetic contract probes. This is not product frontend
admission, privileged/device qualification or an owner acceptance.
"""
import argparse,copy,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,digest,source_bytes,map_check,owned_process,fixture_directory,K
from test_report_worker import report_process,history_check

FEATURE='org.disked.report-operation-events/1'
ZERO='0'*64
def request(command,parameters,features=None):
    return dict(schema='org.disked.request/1',request_id='report-watch-test',command=command,parameters=parameters,required_features=features or [])

def main():
    ap=argparse.ArgumentParser()
    for name in ('probe','fault','product'):ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path);a=ap.parse_args()
    root=a.root.resolve();probe=a.probe.resolve();fault=a.fault.resolve();product=a.product.resolve()
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_REPORT_','DISKED_ACQ_','DISKED_TEST_'))}
    sys.path.insert(0,str(root/'spec/tools'));from specctl import Bundle,SpecError
    bundle=Bundle(root/'spec');checks=[];outputs=[];samples=[]
    def check(name,value,**details):assert value,(name,details);checks.append(dict(name=name,passed=True,**details))
    def private(name,value,exe=probe,exits=(0,),extra=None,protocol=True):
        p=subprocess.run([str(exe)],input=canonical(value),capture_output=True,cwd=root,env=dict(env,**(extra or {})),timeout=15)
        assert p.returncode in exits and not p.stderr,(name,p.returncode,p.stdout,p.stderr)
        out=json.loads(p.stdout);response=out.get('response',out)
        if protocol:
            bundle.validate('urn:disked:schema:response:1',response)
            check(name,response['status']=={0:'completed',2:'refused',3:'refused',4:'failed',5:'accepted_running',6:'unknown'}[p.returncode],exit_code=p.returncode,input_sha256=digest(canonical(value)),output_sha256=digest(p.stdout))
            result=response.get('result')
            if result is not None:bundle.validate('urn:disked:schema:'+('export-preparation-result:1' if result.get('phase')=='prepare' else 'export-operation-result:1'),result)
            for event in (result or {}).get('events',[])+out.get('events',[]):bundle.validate('urn:disked:schema:report-operation-event:1',event)
        else:check(name,True,input_sha256=digest(canonical(value)),output_sha256=digest(p.stdout))
        return out
    def prod(args,exits=(0,5),machine=None):
        p=subprocess.run([str(product),*(['--json',*args] if machine is None else ['protocol','serve','--format=ndjson'])],input=machine,capture_output=True,cwd=root,env=env,timeout=15)
        assert p.returncode in exits and not p.stderr,(p.returncode,p.stdout,p.stderr);return json.loads(p.stdout)
    def exited(state,exe):
        handle=report_process(state,exe)
        if handle:
            try:assert K.WaitForSingleObject(handle,3000)==0,('retain live worker',state)
            finally:K.CloseHandle(handle)
    def reader(name,header,events,**kwargs):return private(name,dict(mode='watch-reader',header=header,events=events,**kwargs),protocol=False)['results']
    def rejected(name,header,prefix,bad,**kwargs):
        rows=reader(name,header,[*prefix,bad],**kwargs);last=rows[-1]
        sequence=prefix[-1]['sequence'] if prefix else '0';sha=prefix[-1]['payload']['record']['digest'] if prefix else ZERO
        check(name+'-cursor-retained',bool(last['error']) and last['sequence']==sequence and last['digest']==sha,error=last['error'])
    def rehash(event):
        row=event['payload']['record'];unsigned={k:v for k,v in row.items() if k!='digest'};row['digest']=digest(canonical(unsigned));return event
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        folder=owned/'case';folder.mkdir();case=folder/'state';case.mkdir();src=folder/'generated.img';dst=folder/'copy.img';mapping=folder/'copy.map';expected=source_bytes(65537);src.write_bytes(expected)
        prepared=prod(['image','acquire','prepare',str(src),str(dst),'--map',str(mapping),'--state-dir',str(case)])['result']
        start=prod(['image','acquire','execute','--definition-json',canonical(prepared['definition']).decode(),'--definition-digest',prepared['definition_digest'],'--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects']);case_id=start['operation_id']
        end=time.monotonic()+20
        while True:
            state=prod(['operation','inspect',case_id,'--state-dir',str(case)])['result']['state']
            if state['phase']=='finished':break
            assert time.monotonic()<end,('retain acquisition',state);time.sleep(.03)
        handle=owned_process(state,str(product))
        if handle:
            try:assert K.WaitForSingleObject(handle,3000)==0
            finally:K.CloseHandle(handle)
        check('independent-generated-acquisition',src.read_bytes()==dst.read_bytes()==expected and state['outcome']['status']=='completed');map_check(mapping,expected)
        original={p.name:p.read_bytes() for p in case.iterdir() if p.is_file()}
        def fixture(name,exe=probe):
            f=owned/name;f.mkdir();store=f/'state';store.mkdir()
            p=dict(phase='prepare',case_operation_id=case_id,case_directory=str(case),destination=str(f/'support.json'),state_directory=str(store))
            out=private(name+'-prepare',dict(mode='request',request=request('evidence.export',p)),exe=exe)['result']
            check(name+'-prepare-no-effects',not Path(p['destination']).exists() and not list(store.iterdir()))
            q=dict(phase='execute',definition=out['definition'],definition_digest=out['definition_digest'],allow_case_read=True,allow_report_write=True,allow_store_write=True,allow_host_effects=True)
            return p,q
        def watch(name,p,id,exe=probe,exits=(0,5,6),**kwargs):return private(name,dict(mode='watch',parameters=dict(operation_id=id,state_directory=p['state_directory'],**kwargs)),exe=exe,exits=exits)
        def wait(name,p,id,exe=probe,terminal=True):
            end=time.monotonic()+20
            while True:
                out=watch(name+'-poll',p,id,exe=exe);value=out['result'];state=value.get('state',{})
                if state and ((terminal and state['phase']=='finished') or (not terminal and value.get('worker_observation')!='running')):
                    exited(state,exe);return out
                assert time.monotonic()<end,('retain report',out);time.sleep(.05)
        def independent(name,p,q,id):
            body=Path(p['destination']).read_bytes();artifact=q['definition']['export']['effect']['artifact']
            check(name+'-independent-output',digest(body)==artifact['digest'] and len(body)==int(artifact['bytes']))
            outputs.append(dict(name=name,operation_id=id,definition_digest=q['definition_digest'],bytes=str(len(body)),sha256=digest(body)))
            return body
        p,q=fixture('complete');start=private('complete-start',dict(mode='request',request=request('evidence.export',q)),exits=(0,5));id=start['operation_id']
        done=wait('complete',p,id);body=independent('complete',p,q,id)
        store=Path(p['state_directory']);header=json.loads((store/'report.request').read_bytes());raw,records=history_check(store/'report.records',header)
        all_events=watch('complete-reconnect-all',p,id,exits=(0,))['result']['events']
        check('events-exact-retained-records',[e['payload']['record'] for e in all_events]==records and all(e['operation_id']==id and e['type']=='report.operation.record' for e in all_events))
        result=watch('cursor-resume',p,id,exits=(0,),after_sequence='1',after_digest=records[0]['digest'],worker_epoch=header['worker_epoch'])['result']
        check('resume-does-not-reemit',[e['payload']['record'] for e in result['events']]==records[1:] and result['last_sequence']==str(len(records)) and result['last_digest']==records[-1]['digest'])
        result=watch('cursor-at-end',p,id,exits=(0,),after_sequence=str(len(records)),after_digest=records[-1]['digest'],worker_epoch=header['worker_epoch'])['result'];check('end-no-new-events',result['events']==[])
        snapshot=watch('explicit-snapshot',p,id,exits=(0,),snapshot=True)['result']['events'];check('snapshot-is-exact-last-record',len(snapshot)==1 and snapshot[0]['type']=='report.operation.snapshot' and snapshot[0]['payload']['record']==records[-1])
        invalid=[('missing-cursor-binding',dict(after_sequence='1')),('wrong-epoch',dict(worker_epoch='worker:'+'0'*32)),('wrong-digest',dict(after_sequence='1',after_digest=ZERO,worker_epoch=header['worker_epoch'])),('ahead',dict(after_sequence='16',after_digest=ZERO,worker_epoch=header['worker_epoch'])),('overflow',dict(after_sequence=str(2**64))),('conflicting-snapshot',dict(after_sequence='1',after_digest=records[0]['digest'],worker_epoch=header['worker_epoch'],snapshot=True)),('follow-out-of-range',dict(follow_ms='2001')),('unknown-key',dict(force=True)),('missing-drive',dict(state_directory='relative'))]
        baseline={f.name:f.read_bytes() for f in store.iterdir()}
        for name,bad in invalid:
            params=dict(operation_id=id,state_directory=p['state_directory']);params.update(bad)
            private(name,dict(mode='watch',parameters=params),exits=(2,));check(name+'-no-effects',baseline=={f.name:f.read_bytes() for f in store.iterdir()} and body==Path(p['destination']).read_bytes())
        params=dict(operation_id=id,state_directory=p['state_directory'])
        inspect=private('canonical-inspect',dict(mode='request',request=request('operation.inspect',params)))
        check('inspect-exact-state',inspect['result']['state']==records[-1]['state'])
        parsed=private('canonical-cli-watch',dict(mode='cli',argv=['operation','watch',id,'--state-dir',p['state_directory']]))
        check('parser-routes-report-not-fake',[e['payload']['record'] for e in parsed['result']['events']]==records)
        stream=private('required-feature-events',dict(mode='event-request',request=request('operation.watch',params,[FEATURE])))
        check('queue-and-response-separated',stream['response']['result']['events']==[] and [e['payload']['record'] for e in stream['events']]==records)
        ordinary=private('no-feature-collected-watch',dict(mode='event-request',request=request('operation.watch',params)))
        check('feature-opt-in-only',ordinary['events']==[] and [e['payload']['record'] for e in ordinary['response']['result']['events']]==records)
        for features in (['org.disked.acquisition-operation-events/1'],['org.disked.unknown/1']):
            private('unsupported-stream-feature',dict(mode='event-request',request=request('operation.watch',params,features)),exits=(3,))
        accepted=reader('reader-valid-chain',header,all_events);check('reader-accepts-chain',all(r.get('accepted') is True and not r['error'] for r in accepted))
        duplicate=reader('reader-exact-duplicate',header,[all_events[0],all_events[0]]);check('duplicate-idempotent',duplicate[-1].get('accepted') is False and duplicate[-1]['sequence']=='1' and not duplicate[-1]['error'])
        rejected('gap',header,[],all_events[-1]);rejected('unrequested-snapshot',header,[],snapshot[0])
        check('explicit-reader-snapshot',reader('requested-reader-snapshot',header,snapshot,snapshot=True)[0].get('accepted') is True)
        for name,alter,prefix,base in [
            ('sequence-overflow',lambda e:e.update(sequence=str(2**64)),[],all_events[0]),
            ('foreign-operation',lambda e:e.update(operation_id='report-op:'+'0'*32),[],all_events[0]),
            ('foreign-observer',lambda e:e['payload'].update(observer_epoch='watch:'+'0'*32),all_events[:1],all_events[1]),
            ('foreign-request',lambda e:e['payload'].update(request_id='other'),all_events[:1],all_events[1]),
            ('corrupt-digest',lambda e:e['payload']['record'].update(digest=ZERO),[],all_events[0]),
            ('unknown-required-feature',lambda e:e.update(required_features=['org.disked.unknown/1']),[],all_events[0]),
            ('byte-limit',lambda e:e.update(extra_a='a'*40000,extra_b='b'*40000),[],all_events[0]),
            ('value-limit',lambda e:e.update(extra=[False]*8256),[],all_events[0])]:
            event=copy.deepcopy(base);alter(event);rejected(name,header,prefix,event)
        changed=copy.deepcopy(all_events[1]);changed['payload']['record']['state']['binding']['process_id']='1';rejected('changed-process-binding',header,all_events[:1],rehash(changed))
        old=copy.deepcopy(all_events[1]);old['payload']['record']['state']['binding']['worker_epoch']='worker:'+'0'*32;rejected('old-worker-epoch',header,all_events[:1],rehash(old))
        terminal=copy.deepcopy(all_events[-1]);terminal['sequence']=str(len(records)+1);terminal['payload']['record']['state']['sequence']=terminal['sequence'];terminal['payload']['record']['previous']=records[-1]['digest'];rejected('post-terminal',header,all_events,rehash(terminal))
        skipped=copy.deepcopy(all_events[-1]);skipped['sequence']='2';skipped['payload']['record']['state']['sequence']='2';skipped['payload']['record']['previous']=records[0]['digest'];rejected('effect-without-dispatch',header,all_events[:1],rehash(skipped))
        regressed=copy.deepcopy(all_events[0]);regressed['sequence']='3';regressed['payload']['record']['state']['sequence']='3';regressed['payload']['record']['previous']=records[1]['digest'];rejected('phase-regression',header,all_events[:2],rehash(regressed))
        conflict=copy.deepcopy(all_events[0]);conflict['payload']['record']['state']['observed_filetime']=str(int(conflict['payload']['record']['state']['observed_filetime'])+1);rejected('conflicting-duplicate',header,all_events[:1],rehash(conflict))
        additive=copy.deepcopy(all_events[0]);additive['optional_background']='a'*18000
        check('compatible-reader-larger-report-profile',len(canonical(additive))>16384 and reader('additive-reader-field',header,[additive])[0]['preserved']==additive)
        try:bundle.validate('urn:disked:schema:report-operation-event:1',additive)
        except SpecError:check('producer-remains-strict',True)
        else:raise AssertionError('producer unexpectedly permits extension')
        for pop in (False,True):
            value=dict(mode='watch-queue',events=[all_events[0]],repeat=65)
            if pop:value['pop_each']=True
            queued=private('queue-count-budget',value,protocol=False);check('queue-count-cumulative',queued['accepted']==64 and 'watch_queue_limit' in queued['error'])
        value=dict(mode='watch-queue',events=[additive],repeat=128,pop_each=True)
        queued=private('queue-byte-budget',value,protocol=False);check('queue-bytes-cumulative',queued['accepted']==min(64,1048576//len(canonical(additive))) and 'watch_queue_limit' in queued['error'])
        # Corrupt only a completed, actually exited owned worker history. Restore
        # the fixture bytes after observation; this is not product recovery.
        (store/'report.records').write_bytes(raw+b'{')
        torn=watch('torn-suffix',p,id,exits=(6,))
        check('torn-keeps-validated-records',not torn['result']['history_complete'] and [e['payload']['record'] for e in torn['result']['events']]==records and torn['result']['state']==records[-1]['state'])
        (store/'report.records').write_bytes(raw+b'{}\n');bad=watch('invalid-complete-row',p,id,exits=(6,));check('bad-row-no-speculation',bad['result']['events']==[] and 'state' not in bad['result'])
        (store/'report.records').write_bytes(raw)
        # Production composition refuses report IDs before metadata selection.
        for command in (['operation','inspect'],['operation','cancel'],['operation','watch']):
            out=prod([*command,id,'--state-dir',p['state_directory']],(3,));check('product-report-unavailable',out['status']=='refused' and any(d['code']=='operation_unavailable' for d in out['diagnostics']))
        out=prod([], (3,),canonical(request('operation.watch',params,[FEATURE]))+b'\n');check('product-stream-report-unavailable',out['status']=='refused' and any(d['code']=='operation_unavailable' for d in out['diagnostics']))
        check('production-refusal-before-effects',baseline=={f.name:f.read_bytes() for f in store.iterdir()} and body==Path(p['destination']).read_bytes())
        samples.append(dict(name='actual-completed',definition=q['definition'],header=header,result=done['result'],rows=records,support=json.loads(body),events=all_events))
        # Parent admission timeout leaves the one actual worker running. A later
        # observer uses its retained operation/attempt/epoch without restarting.
        fp,fq=fixture('delayed-admission',fault)
        start=private('delayed-admission-unknown',dict(mode='request',request=request('evidence.export',fq)),exe=fault,exits=(6,),extra=dict(DISKED_REPORT_WORKER_TEST_ADMISSION_DELAY='1'));fid=start['operation_id']
        active=watch('delayed-watch-active',fp,fid,exe=fault,exits=(5,),follow_ms='0');saved=active['result']['state']['binding']
        repeat=private('delayed-repeat-observes',dict(mode='request',request=request('evidence.export',fq)),exe=fault,exits=(0,5));check('delayed-repeat-same-attempt',repeat['operation_id']==fid and repeat['result']['state']['binding']==saved)
        finish=wait('delayed',fp,fid,fault);check('late-result-same-worker',finish['result']['state']['binding']==saved);independent('delayed-admission',fp,fq,fid)
        samples.append(dict(name='actual-delayed-admission',initial=start,active=active,finished=finish))
        fp,fq=fixture('observer-failure',fault)
        start=private('observer-failure-start',dict(mode='request',request=request('evidence.export',fq)),exe=fault,exits=(5,),extra=dict(DISKED_REPORT_WORKER_TEST_EFFECT_DELAY='1'));fid=start['operation_id'];params=dict(operation_id=fid,state_directory=fp['state_directory'],follow_ms='2000')
        failure=private('observer-read-failure-after-event',dict(mode='event-request',request=request('operation.watch',params,[FEATURE])),exe=fault,exits=(6,),extra=dict(DISKED_REPORT_WATCH_TEST_READ_FAILURE='1'))
        check('read-failure-retains-accepted-cursor-state',len(failure['events'])==1 and failure['response']['result']['last_sequence']=='1' and failure['response']['result']['state']==failure['events'][0]['payload']['record']['state'])
        collected=private('collected-read-failure-after-event',dict(mode='watch',parameters=params),exe=fault,exits=(6,),extra=dict(DISKED_REPORT_WATCH_TEST_READ_FAILURE='1'))
        check('collected-failure-keeps-events-and-cursor',len(collected['result']['events'])==1 and collected['result']['last_sequence']=='1' and collected['result']['state']==collected['result']['events'][0]['payload']['record']['state'])
        closed=private('closed-queue-observation',dict(mode='closed-event-request',request=request('operation.watch',params,[FEATURE])),exe=fault)
        check('closed-queue-does-not-kill-worker',closed['events']==[] and closed['response']['result']['worker_observation']=='running')
        finish=wait('observer-survives',fp,fid,fault);check('observer-failure-does-not-restart',finish['result']['state']['binding']==failure['response']['result']['state']['binding']);independent('observer-survives',fp,fq,fid)
        samples.append(dict(name='actual-observer-fault',fault_injection='Compiled private later-read failure; worker dependencies unchanged',failed_watch=failure,finished=finish))
        fp,fq=fixture('cancel-before-create',fault)
        start=private('cancel-start',dict(mode='request',request=request('evidence.export',fq)),exe=fault,exits=(5,),extra=dict(DISKED_REPORT_WORKER_TEST_EFFECT_DELAY='1'));fid=start['operation_id'];params=dict(operation_id=fid,state_directory=fp['state_directory'])
        cancel=private('canonical-cancel',dict(mode='request',request=request('operation.cancel.request',params)),exe=fault)
        check('cancel-request-not-observation',cancel['result']['cancellation_request']=='requested' and cancel['result']['state']['cancellation_observation']=='not_observed')
        finish=wait('cancelled',fp,fid,fault)
        check('cancelled-watch-completes-observation',finish['status']=='completed' and finish['result']['state']['outcome']['status']=='cancelled' and finish['result']['state']['cancellation_observation']=='observed' and not Path(fp['destination']).exists())
        cancel_header=json.loads((Path(fp['state_directory'])/'report.request').read_bytes());cancel_events=finish['result']['events']
        check('cancel-reader-valid-chain',all(r.get('accepted') is True for r in reader('cancel-reader-chain',cancel_header,cancel_events)))
        lost_cancel=copy.deepcopy(cancel_events[-1]);lost_cancel['payload']['record']['state']['cancellation_observation']='not_observed';rejected('cancellation-observation-regression',cancel_header,cancel_events[:-1],rehash(lost_cancel))
        private('cancelled-repeat-not-restarted',dict(mode='request',request=request('evidence.export',fq)),exe=fault,exits=(4,))
        samples.append(dict(name='actual-cancelled',result=finish))
        fp,fq=fixture('lost-terminal',fault)
        start=private('lost-terminal-start',dict(mode='request',request=request('evidence.export',fq)),exe=fault,exits=(5,6),extra=dict(DISKED_TEST_STORE_FAULT='report_finished.full'));fid=start['operation_id']
        finish=wait('lost-terminal',fp,fid,fault,False);body=independent('lost-terminal',fp,fq,fid)
        check('lost-terminal-remains-unknown',finish['status']=='unknown' and finish['result']['state']['phase']=='executing' and not finish['result']['state']['quiescent'] and all(e['payload']['record']['state']['phase']!='finished' for e in finish['result']['events']))
        before={f.name:f.read_bytes() for f in Path(fp['state_directory']).iterdir()};private('lost-terminal-repeat',dict(mode='request',request=request('evidence.export',fq)),exe=fault,exits=(6,))
        check('lost-terminal-no-new-attempt',before=={f.name:f.read_bytes() for f in Path(fp['state_directory']).iterdir()} and body==Path(fp['destination']).read_bytes())
        samples.append(dict(name='actual-unresolved',result=finish))
        check('original-case-bytes-unchanged',original=={p.name:p.read_bytes() for p in case.iterdir() if p.is_file()})
    report=dict(checks=len(checks),observations=checks,verified_outputs=outputs,samples=samples,scope='Private native report watch/request/parser and pure altered reader/queue contracts; production report backend unavailable',source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)))
    if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('observations','samples')}));return 0
if __name__=='__main__':raise SystemExit(main())
