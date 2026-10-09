"""Provisional inward export service, canonical parsing/forms and real files.

This probe is not a product frontend. Generated acquisition metadata and exact
output bytes are independently checked; product journeys are separately qualified.
"""
import argparse,copy,itertools,json,os,subprocess,sys,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,digest,source_bytes,map_check,owned_process,fixture_directory,K
from test_report_worker import report_process,history_check

def frame(p):return dict(schema='org.disked.request/1',request_id='export-test',command='evidence.export',parameters=p,required_features=[])
def main():
    ap=argparse.ArgumentParser()
    for name in ('probe','fault','product'):ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path);a=ap.parse_args()
    root=a.root.resolve();probe=a.probe.resolve();fault=a.fault.resolve();product=a.product.resolve()
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_REPORT_','DISKED_ACQ_','DISKED_TEST_'))}
    sys.path.insert(0,str(root/'spec/tools'));from specctl import Bundle
    bundle=Bundle(root/'spec');checks=[];outputs=[];samples=[]
    def check(name,value,**details):assert value,(name,details);checks.append(dict(name=name,passed=True,**details))
    def call(name,value,exits=(0,),exe=probe,extra=None):
        p=subprocess.run([str(exe)],input=canonical(value),capture_output=True,cwd=root,env=dict(env,**(extra or {})),timeout=15)
        assert p.returncode in exits and not p.stderr,(name,p.returncode,p.stdout,p.stderr)
        out=json.loads(p.stdout);response=out.get('response',out)
        check(name,response['schema']=='org.disked.response/1' and response['status']=={0:'completed',2:'refused',3:'refused',4:'failed',5:'accepted_running',6:'unknown'}[p.returncode],exit_code=p.returncode,input_sha256=digest(canonical(value)),output_sha256=digest(p.stdout))
        bundle.validate('urn:disked:schema:response:1',response)
        result=response.get('result')
        if result is not None:
            id='export-preparation-result:1' if result.get('phase')=='prepare' else 'export-operation-result:1'
            bundle.validate('urn:disked:schema:'+id,result)
        return out
    def product_call(args,exits=(0,5)):
        p=subprocess.run([str(product),'--json',*args],capture_output=True,cwd=root,env=env,timeout=15)
        assert p.returncode in exits and not p.stderr,(p.returncode,p.stdout,p.stderr);return json.loads(p.stdout)
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        folder=owned/'case';folder.mkdir();case=folder/'state';case.mkdir();src=folder/'generated.img';dst=folder/'copy.img';mapping=folder/'copy.map';expected=source_bytes(65537);src.write_bytes(expected)
        prepared=product_call(['image','acquire','prepare',str(src),str(dst),'--map',str(mapping),'--state-dir',str(case)])['result']
        start=product_call(['image','acquire','execute','--definition-json',canonical(prepared['definition']).decode(),'--definition-digest',prepared['definition_digest'],'--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects']);case_id=start['operation_id']
        end=time.monotonic()+20
        while True:
            state=product_call(['operation','inspect',case_id,'--state-dir',str(case)])['result']['state']
            if state['phase']=='finished':break
            assert time.monotonic()<end,('retain acquisition',state);time.sleep(.03)
        handle=owned_process(state,str(product))
        if handle:
            try:assert K.WaitForSingleObject(handle,3000)==0
            finally:K.CloseHandle(handle)
        check('independent-generated-acquisition',src.read_bytes()==dst.read_bytes()==expected and state['outcome']['status']=='completed');map_check(mapping,expected)
        original={p.name:p.read_bytes() for p in case.iterdir() if p.is_file()}
        def fixture(name):
            f=owned/name;f.mkdir();store=f/'state';store.mkdir()
            return dict(phase='prepare',case_operation_id=case_id,case_directory=str(case),destination=str(f/'support.json'),state_directory=str(store))
        def no_effects(p):return not Path(p['destination']).exists() and not list(Path(p['state_directory']).iterdir()) and original=={p.name:p.read_bytes() for p in case.iterdir() if p.is_file()}
        p=fixture('contract');request=frame(p)
        invalid=[('missing-phase',{}),('bad-phase',dict(p,phase='other')),('fake-case',dict(p,case_operation_id='fake-op:'+'1'*32)),('report-case',dict(p,case_operation_id='report-op:'+'1'*32)),('truncated-case',dict(p,case_operation_id=case_id[:-1])),('wrong-case-type',dict(p,case_operation_id=3)),('unknown-parameter',dict(p,force=True)),('wrong-consent-type',dict(p,include_customer_data='true')),('long-destination',dict(p,destination='x'*961)),('wrong-phase-field',dict(p,allow_host_effects=True))]
        for key in ('case_operation_id','case_directory','destination','state_directory'):
            bad=dict(p);del bad[key];invalid.append(('missing-'+key,bad))
        for name,bad in invalid:
            out=call(name,dict(mode='audit',request=frame(bad),reply={}),exits=(2,));check(name+'-zero-ports',out['prepare_calls']==out['execute_calls']==0 and no_effects(p))
        result=call('prepare-typed',dict(mode='request',request=request))['result']
        check('prepare-exact-bound-no-effects',no_effects(p) and not result['execution_admitted'] and result['definition_digest']==digest(canonical(result['definition'])) and result['definition']['export']['case']['operation_id']==case_id)
        argv=['evidence','export','prepare',case_id,p['destination'],'--case-state-dir',p['case_directory'],'--state-dir',p['state_directory']]
        check('canonical-cli-prepare-matches',call('prepare-parser',dict(mode='cli',argv=argv))['result']==result and no_effects(p))
        check('typed-form-prepare-matches',call('prepare-form',dict(mode='form',editor=p))['result']==result and no_effects(p))
        stripped={k:v for k,v in result.items() if k in ('definition','definition_digest')}
        for name,badreply,params in [('wrong-prepared-digest',dict(stripped,definition_digest='sha256:'+'0'*64),p),('wrong-prepared-case',stripped,dict(p,case_operation_id='image-op:'+'1'*32)),('wrong-prepared-policy',stripped,dict(p,include_identifiers=True))]:
            out=call(name,dict(mode='audit',request=frame(params),reply=badreply),exits=(3,));check(name+'-no-execution',out['prepare_calls']==1 and out['execute_calls']==0 and no_effects(p))
        q=dict(phase='execute',definition=result['definition'],definition_digest=result['definition_digest'],allow_case_read=True,allow_report_write=True,allow_store_write=True,allow_host_effects=True)
        for flags in itertools.product((False,True),repeat=4):
            if all(flags):continue
            bad=dict(q,**dict(zip(('allow_case_read','allow_report_write','allow_store_write','allow_host_effects'),flags)))
            out=call('explicit-grants-'+''.join(map(str,map(int,flags))),dict(mode='audit',request=frame(bad),reply={}),exits=(2,));check('false-grants-zero-ports',out['prepare_calls']==out['execute_calls']==0 and no_effects(p))
        bad=dict(q,definition_digest='sha256:'+'0'*64)
        out=call('wrong-review-digest',dict(mode='audit',request=frame(bad),reply={}),exits=(3,));check('digest-before-effects',out['execute_calls']==0 and no_effects(p))
        d=copy.deepcopy(q['definition']);d['store']['generation']['created']=str(2**64);d['store']['ancestors'][-1]['created']=str(2**64)
        out=call('u64-semantic-before-effects',dict(mode='audit',request=frame(dict(q,definition=d,definition_digest=digest(canonical(d)))),reply={}),exits=(3,));check('semantic-zero-ports',out['execute_calls']==0 and no_effects(p))
        d=copy.deepcopy(q['definition']);d['export']['source']['store']['unexpected']=True
        out=call('nested-reference-closed-shape',dict(mode='audit',request=frame(dict(q,definition=d,definition_digest=digest(canonical(d)))),reply={}),exits=(2,));check('nested-shape-zero-ports',out['execute_calls']==0 and no_effects(p))
        for name,change in [('swapped-metadata-slots',lambda d:d['export']['source']['files'].reverse()),('changed-fixed-store-child',lambda d:d['store']['children'].__setitem__(0,'other.request')),('extra-metadata-slot',lambda d:d['export']['source']['files'].append(copy.deepcopy(d['export']['source']['files'][0])))]:
            d=copy.deepcopy(q['definition']);change(d)
            out=call(name,dict(mode='audit',request=frame(dict(q,definition=d,definition_digest=digest(canonical(d)))),reply={}),exits=(2,));check(name+'-zero-ports',out['execute_calls']==0)
        out=call('missing-provider',dict(mode='audit',no_ports=True,request=frame(q),reply={}),exits=(3,));check('missing-provider-no-effects',no_effects(p))
        expected_grant=dict(definition_digest=q['definition_digest'],case_read=True,report_write=True,store_write=True,host_effects=True)
        out=call('post-dispatch-throw',dict(mode='audit',request=frame(q),reply={},throw=True,expected_grant=expected_grant),exits=(6,));check('throw-retains-routing',out['execute_calls']==1 and out['response']['result']['state_directory']==p['state_directory'] and out['response']['result']['definition_digest']==q['definition_digest'] and out['response']['operation_id'] is None and no_effects(p))
        out=call('execute-real-owned-output',dict(mode='request',request=frame(q)),exits=(0,5,6));ident=out['operation_id'];assert ident and ident.startswith('report-op:')
        end=time.monotonic()+20
        while True:
            final=call('inspect-real-report',dict(mode='inspect',operation_id=ident,state_directory=p['state_directory']),exits=(0,6))
            state=(final['result'] or {}).get('state',{})
            if state.get('phase')=='finished':break
            assert time.monotonic()<end,('retain report',final);time.sleep(.03)
        handle=report_process(state,probe)
        if handle:
            try:assert K.WaitForSingleObject(handle,3000)==0
            finally:K.CloseHandle(handle)
        header=json.loads((Path(p['state_directory'])/'report.request').read_bytes());raw,rows=history_check(Path(p['state_directory'])/'report.records',header)
        body=Path(p['destination']).read_bytes();artifact=q['definition']['export']['effect']['artifact'];support=json.loads(body)
        check('independent-report-bytes-and-state',body.endswith(b'\n') and digest(body)==artifact['digest'] and len(body)==int(artifact['bytes']) and state==rows[-1]['state'] and state['outcome']['status']=='completed')
        for forbidden in (str(src),str(dst),str(mapping),str(case),case_id):check('default-support-omits-routing',forbidden.encode() not in body)
        check('report-retains-default-policy',support['policy']==dict(identifiers=False,raw_values=False,interpretations=False,customer_data=False))
        outputs.append(dict(bytes=str(len(body)),sha256=digest(body),operation_id=ident,definition_digest=q['definition_digest']))
        samples.append(dict(definition=q['definition'],header=header,rows=rows,result=final['result'],support=support))
        def private(status='completed',state_override=None):
            value={k:copy.deepcopy(v) for k,v in final['result'].items() if k in ('definition','definition_digest','state','last_digest','history_complete','worker_observation','cancellation_request','admission')}
            if state_override is not None:value['state']=copy.deepcopy(state_override)
            return dict(schema='org.disked.report-admission-prototype/1',status=status,operation_id=ident,value=value,diagnostic='',platform_code='0')
        # These are deliberate port-spy models, never retained as actual work.
        for name,alter in [('no-id',lambda v:v.update(operation_id=None)),('wrong-id',lambda v:v.update(operation_id='report-op:'+'0'*32)),('wrong-history',lambda v:v['value'].update(history_complete=False)),('no-last-digest',lambda v:v['value'].pop('last_digest')),('wrong-code-binding',lambda v:v['value']['state']['binding'].update(image_digest='0'*64)),('foreign-worker',lambda v:v['value']['state']['binding'].update(worker_epoch='worker:'+'0'*31)),('bad-sequence',lambda v:v['value']['state'].update(sequence=str(2**64))),('false-quiescence',lambda v:v['value']['state'].update(quiescent=False)),('counter-beyond-review',lambda v:v['value']['state']['outcome']['output'].update(written_bytes=str(int(artifact['bytes'])+1))),('contradictory-receipt',lambda v:v['value']['state']['receipt']['output_receipt'].update(output_created_observed=False)),('unknown-response-field',lambda v:v['value'].update(unrelated=True))]:
            reply=private();alter(reply);out=call(name,dict(mode='audit',request=frame(q),reply=reply),exits=(6,));check(name+'-unresolved-retains-review',out['execute_calls']==1 and out['response']['result']['definition_digest']==q['definition_digest'])
        out=call('completed-spy-binding',dict(mode='audit',request=frame(q),reply=private(),expected_grant=expected_grant));check('exact-grant-completed',out['execute_calls']==1)
        active=next(row['state'] for row in rows if row['state']['phase']!='finished');reply=private('accepted_running',active);reply['value']['worker_observation']='running'
        out=call('running-spy-typed-id',dict(mode='audit',request=frame(q),reply=reply),exits=(5,));check('accepted-running-has-id',out['response']['operation_id']==ident)
        reply['operation_id']=None;call('running-without-id',dict(mode='audit',request=frame(q),reply=reply),exits=(6,))
        reply=private('completed',active);reply['value']['worker_observation']='running'
        call('active-observation-completes-read',dict(mode='observe-reply',reply=reply));call('active-execution-not-completed',dict(mode='audit',request=frame(q),reply=reply),exits=(6,))
        refusal=dict(schema='org.disked.report-admission-prototype/1',status='refused',operation_id=None,value={},diagnostic='report_worker_definition_changed',platform_code='5')
        call('provider-refusal-has-stable-exit',dict(mode='audit',request=frame(q),reply=refusal),exits=(3,))
        # Repeated matching execution reads the existing result; no second file/attempt.
        before={f.name:f.read_bytes() for f in Path(p['state_directory']).iterdir()}
        repeat=call('repeat-matching-observes',dict(mode='request',request=frame(q)))
        check('repeat-no-new-attempt',repeat['operation_id']==ident and before=={f.name:f.read_bytes() for f in Path(p['state_directory']).iterdir()} and Path(p['destination']).read_bytes()==body)
        cancel=call('finished-cancel-too-late',dict(mode='cancel',operation_id=ident,state_directory=p['state_directory']))
        check('cancel-does-not-rewrite-effect',cancel['result']['cancellation_request']=='too_late' and cancel['result']['state']==state and Path(p['destination']).read_bytes()==body)
        def fault_fixture(name):
            p=fixture(name);r=call(name+'-prepare',dict(mode='request',request=frame(p)),exe=fault)['result']
            check(name+'-prepare-no-effects',no_effects(p))
            q=dict(phase='execute',definition=r['definition'],definition_digest=r['definition_digest'],allow_case_read=True,allow_report_write=True,allow_store_write=True,allow_host_effects=True)
            return p,q
        def wait_report(name,p,id,terminal=True):
            end=time.monotonic()+20
            while True:
                out=call(name+'-inspect',dict(mode='inspect',operation_id=id,state_directory=p['state_directory']),exits=(0,6),exe=fault)
                state=(out['result'] or {}).get('state',{})
                if state and ((terminal and state['phase']=='finished') or (not terminal and out['result'].get('worker_observation')!='running')):
                    handle=report_process(state,fault)
                    if handle:
                        try:assert K.WaitForSingleObject(handle,3000)==0
                        finally:K.CloseHandle(handle)
                    return out
                assert time.monotonic()<end,('retain fault fixture',out);time.sleep(.1)
        fp,fq=fault_fixture('cancel-before-create')
        start=call('cancel-start-active',dict(mode='request',request=frame(fq)),exits=(5,),exe=fault,extra=dict(DISKED_REPORT_WORKER_TEST_EFFECT_DELAY='1'))
        cancelled=call('cancel-request-is-read-result',dict(mode='cancel',operation_id=start['operation_id'],state_directory=fp['state_directory']),exe=fault)
        check('cancel-request-separate-from-observation',cancelled['result']['cancellation_request']=='requested' and cancelled['result']['state']['cancellation_observation']=='not_observed')
        done=wait_report('cancel-before-create',fp,start['operation_id'])
        check('cancelled-effect-observation-completed',done['status']=='completed' and done['result']['state']['outcome']['status']=='cancelled' and done['result']['state']['cancellation_observation']=='observed' and not Path(fp['destination']).exists())
        call('cancelled-execution-is-failed',dict(mode='request',request=frame(fq)),exits=(4,),exe=fault)
        samples.append(dict(name='actual-cancelled',definition=fq['definition'],result=done['result']))
        fp,fq=fault_fixture('lost-terminal')
        start=call('lost-terminal-start',dict(mode='request',request=frame(fq)),exits=(5,6),exe=fault,extra=dict(DISKED_TEST_STORE_FAULT='report_finished.full'))
        done=wait_report('lost-terminal',fp,start['operation_id'],False);state=done['result']['state'];body=Path(fp['destination']).read_bytes();artifact=fq['definition']['export']['effect']['artifact']
        check('output-does-not-promote-unknown-operation',done['status']=='unknown' and state['phase']=='executing' and not state['quiescent'] and digest(body)==artifact['digest'] and len(body)==int(artifact['bytes']))
        before={f.name:f.read_bytes() for f in Path(fp['state_directory']).iterdir()};call('lost-terminal-repeat-is-unknown',dict(mode='request',request=frame(fq)),exits=(6,),exe=fault)
        check('lost-terminal-not-restarted',before=={f.name:f.read_bytes() for f in Path(fp['state_directory']).iterdir()} and body==Path(fp['destination']).read_bytes())
        outputs.append(dict(name='lost-terminal',bytes=str(len(body)),sha256=digest(body),operation_id=start['operation_id'],definition_digest=fq['definition_digest']));samples.append(dict(name='actual-unresolved',definition=fq['definition'],result=done['result']))
        pp=fixture('product-prepare-only');product_argv=['evidence','export','prepare',case_id,pp['destination'],'--case-state-dir',pp['case_directory'],'--state-dir',pp['state_directory']]
        native_prepare=product_call(product_argv,(0,));check('product-prepare-inert-bound',native_prepare['status']=='completed' and no_effects(pp) and 'sha256:'+native_prepare['result']['definition']['image_digest']==digest(product.read_bytes()))
        check('original-case-bytes-unchanged',original=={p.name:p.read_bytes() for p in case.iterdir() if p.is_file()})
    report=dict(checks=len(checks),observations=checks,verified_outputs=outputs,samples=samples,scope='Private shared-service parser/request/form and ordinary native output; actual product frontend export journeys have separate tests',source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)))
    if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
    print(json.dumps({k:v for k,v in report.items() if k not in ('observations','samples')}));return 0
if __name__=='__main__':raise SystemExit(main())
