"""Shared provisional verification service with actual owned Windows workers.

Expected outcomes are authored in verification-command-prototype.json. Synthetic
port replies test trust boundaries; actual retained samples remain separately
identified. No product admission, physical access or independent owner approval.
"""
import argparse,copy,hashlib,itertools,json,os,subprocess,sys,time
from pathlib import Path
from test_report_worker import report_process
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,digest,source_bytes,map_check,fixture_directory,owned_process,K

FEATURE='org.disked.verification-operation-events/1'
FLAGS=('case_read','image_read','map_read','store_write','host_effects','private_metadata')
NATIVE_KEYS=('definition','definition_digest','state','request_binding','last_digest','history_complete','worker_observation','cancellation_request','admission','collection_validation','attachment_applicability')
def frame(p,command='image.verify',features=()):
    return dict(schema='org.disked.request/1',request_id='verification-test',command=command,parameters=p,required_features=list(features))

def main():
    ap=argparse.ArgumentParser()
    for n in ('probe','fault','product'):ap.add_argument('--'+n,type=Path,required=True)
    ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path);a=ap.parse_args()
    root=a.root.resolve();probe=a.probe.resolve();fault=a.fault.resolve();product=a.product.resolve()
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_REPORT_','DISKED_ACQ_','DISKED_TEST_','DISKED_VERIFICATION_'))}
    sys.path.insert(0,str(root/'spec/tools'));from specctl import Bundle,SpecError
    bundle=Bundle(root/'spec');checks=[];samples=[]
    def check(name,ok,**details):assert ok,(name,details);checks.append(dict(name=name,passed=True,**details))
    def call(name,value,exits=(0,),exe=probe,extra=None):
        p=subprocess.run([str(exe)],input=canonical(value),capture_output=True,cwd=root,env=dict(env,**(extra or {})),timeout=15)
        assert p.returncode in exits and not p.stderr,(name,p.returncode,p.stdout,p.stderr)
        out=json.loads(p.stdout);response=out.get('response',out)
        check(name,response['status']=={0:'completed',2:'refused',3:'refused',4:'failed',5:'accepted_running',6:'unknown'}[p.returncode],exit_code=p.returncode,input_sha256=digest(canonical(value)),output_sha256=digest(p.stdout))
        bundle.validate('urn:disked:schema:response:1',response)
        r=response.get('result')
        if r is not None:
            kind='verification-preparation-result' if r.get('phase')=='prepare' else 'verification-operation-result'
            bundle.validate('urn:disked:schema:'+kind+':1',r)
        for e in out.get('events',[]):bundle.validate('urn:disked:schema:verification-operation-event:1',e)
        return out
    def cli(args):
        p=subprocess.run([str(product),'--json',*args],capture_output=True,cwd=root,env=env,timeout=15)
        assert p.returncode in (0,5) and not p.stderr,(p.returncode,p.stdout,p.stderr);return json.loads(p.stdout)
    def execute(r):return dict(phase='execute',definition=r['definition'],definition_digest=r['definition_digest'],**{'allow_'+f:True for f in FLAGS})
    def wait(id,store,exe=probe,terminal=True):
        end=time.monotonic()+20
        while True:
            out=call('actual-worker-observation',dict(mode='inspect',operation_id=id,state_directory=store),exits=(0,6),exe=exe)
            s=(out['result'] or {}).get('state')
            if s and ((terminal and s['phase']=='finished') or (not terminal and out['result']['worker_observation']!='running')):
                handle=report_process(s,exe)
                if handle:
                    try:assert K.WaitForSingleObject(handle,3000)==0,('retain live fixture',out)
                    finally:K.CloseHandle(handle)
                return out
            assert time.monotonic()<end,('retain unresolved fixture',out);time.sleep(.04)
    def independent(p,end):
        store=Path(p['state_directory']);header=json.loads((store/'verification.request').read_bytes());raw=(store/'verification.records').read_bytes();rows=[];previous='0'*64
        for ordinal,line in enumerate(raw.splitlines(),1):
            row=json.loads(line);unsigned=copy.deepcopy(row);previous_hash=unsigned.pop('digest')
            check('independent-record-chain',canonical(row)==line and len(line)<=65536 and row['previous']==previous and hashlib.sha256(canonical(unsigned)).hexdigest()==previous_hash and row['state']['sequence']==str(ordinal))
            previous=previous_hash;rows.append(row);bundle.validate('urn:disked:schema:verification-worker-record:1',row)
        s=rows[-1]['state'];check('actual-state-agrees',raw.endswith(b'\n') and s==end['result']['state'] and len(rows)<=32 and s['quiescent'])
        if s['retention']['state']=='verified':
            body=(store/'verification.collection').read_bytes();collection=json.loads(body)
            check('independent-collection-bytes',body.endswith(b'\n') and digest(body)==s['retention']['digest'] and len(body)==int(s['retention']['bytes']) and digest(canonical(collection))==s['retention']['collection_revision'])
            check('independent-observer-verdict',collection['records'][0]['observation']['outcome']==s['outcome'] and collection['records'][0]['observer']=={n:s['binding'][n] for n in ('attempt_id','worker_epoch','capture_epoch','process_id','process_created')})
        samples.append(dict(kind='actual-native',header=header,rows=rows,result=end['result'],history_sha256=digest(raw)))
        return header,rows,raw
    def reader(header,events,**cursor):
        p=subprocess.run([str(probe)],input=canonical(dict(mode='watch-reader',header=header,events=events,**cursor)),capture_output=True,cwd=root,env=env,timeout=15)
        assert p.returncode==0 and not p.stderr,(p.returncode,p.stdout,p.stderr);return json.loads(p.stdout)['results']
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        folder=owned/'case';folder.mkdir();case=folder/'state';case.mkdir();src=folder/'generated.img';image=folder/'copy.img';mapping=folder/'copy.map';expected=source_bytes(262145);src.write_bytes(expected)
        r=cli(['image','acquire','prepare',str(src),str(image),'--map',str(mapping),'--state-dir',str(case)])['result']
        start=cli(['image','acquire','execute','--definition-json',canonical(r['definition']).decode(),'--definition-digest',r['definition_digest'],'--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects']);case_id=start['operation_id'];end=time.monotonic()+20
        while True:
            s=cli(['operation','inspect',case_id,'--state-dir',str(case)])['result']['state']
            if s['phase']=='finished':break
            assert time.monotonic()<end,('retain acquisition',s);time.sleep(.04)
        h=owned_process(s,str(product))
        if h:
            try:assert K.WaitForSingleObject(h,3000)==0
            finally:K.CloseHandle(h)
        check('independent-generated-acquisition',src.read_bytes()==image.read_bytes()==expected and s['outcome']['status']=='completed');map_check(mapping,expected)
        original={f.name:f.read_bytes() for f in case.iterdir() if f.is_file()}
        def fixture(name):
            f=owned/name;f.mkdir();store=f/'state';store.mkdir()
            return dict(phase='prepare',case_operation_id=case_id,case_directory=str(case),image=str(image),map=str(mapping),state_directory=str(store))
        def inert(p):return not list(Path(p['state_directory']).iterdir()) and original=={f.name:f.read_bytes() for f in case.iterdir() if f.is_file()}
        p=fixture('normal')
        invalid=[('missing-phase',{}),('bad-phase',dict(p,phase='other')),('wrong-case',dict(p,case_operation_id='verify-op:'+'1'*32)),('unknown-field',dict(p,force=True)),('wrong-type',dict(p,image=3)),('execute-only-field',dict(p,allow_image_read=True))]
        for key in p:
            bad=dict(p);bad.pop(key);invalid.append(('missing-'+key,bad))
        for name,bad in invalid:
            out=call(name,dict(mode='audit',request=frame(bad),reply={}),exits=(2,));check(name+'-zero-ports',out['prepare_calls']==out['execute_calls']==0 and inert(p))
        r=call('prepare-request',dict(mode='request',request=frame(p)))['result'];check('prepare-read-only-no-operation',inert(p) and not r['execution_admitted'] and r['definition_digest']==digest(canonical(r['definition'])))
        argv=['image','verify','prepare',case_id,p['image'],'--map',p['map'],'--case-state-dir',p['case_directory'],'--state-dir',p['state_directory']]
        check('shared-cli-and-form-prepare',call('prepare-cli',dict(mode='cli',argv=argv))['result']==r==call('prepare-form',dict(mode='form',editor=p))['result'] and inert(p))
        q=execute(r);prepared={k:r[k] for k in ('definition','definition_digest')}
        for bits in itertools.product((False,True),repeat=6):
            if all(bits):continue
            bad=dict(q,**{'allow_'+f:b for f,b in zip(FLAGS,bits)})
            out=call('false-grants-'+''.join(str(int(b)) for b in bits),dict(mode='audit',request=frame(bad),reply={}),exits=(2,));check('false-grants-zero-ports',out['prepare_calls']==out['execute_calls']==0 and inert(p))
        for d in ('sha256:'+'0'*64,r['definition']['verification_digest']):
            out=call('wrong-review-digest',dict(mode='audit',request=frame(dict(q,definition_digest=d)),reply={}),exits=(3,));check('wrong-digest-before-effects',out['execute_calls']==0 and inert(p))
        for name,bad,params in [('wrong-preparation-digest',dict(prepared,definition_digest='sha256:'+'0'*64),p),('foreign-selected-image',prepared,dict(p,image=p['image']+'.other'))]:
            out=call(name,dict(mode='audit',request=frame(params),reply=bad),exits=(3,));check('bad-preparation-never-executes',out['prepare_calls']==1 and out['execute_calls']==0 and inert(p))
        call('preparation-port-failure',dict(mode='audit',request=frame(p),reply={},throw=True),exits=(3,))
        out=call('missing-provider',dict(mode='audit',request=frame(q),no_ports=True,reply={}),exits=(3,));check('no-provider-inert',inert(p))
        grant=dict(definition_digest=q['definition_digest'],**{f:True for f in FLAGS})
        out=call('post-dispatch-throw',dict(mode='audit',request=frame(q),reply={},throw=True,expected_grant=grant),exits=(6,));check('unresolved-keeps-reviewed-routing',out['execute_calls']==1 and out['response']['result']['state_directory']==p['state_directory'] and out['response']['result']['definition_digest']==q['definition_digest'] and inert(p))
        start=call('actual-execution',dict(mode='request',request=frame(q)),exits=(0,5,6));id=start['operation_id'];check('allocated-operation-id',id and id.startswith('verify-op:'))
        final=wait(id,p['state_directory']);header,rows,raw=independent(p,final);check('native-terminal-match',final['result']['state']['outcome']['status']=='matched' and final['result']['attachment_applicability']=='applicable')
        before={f.name:f.read_bytes() for f in Path(p['state_directory']).iterdir()}
        repeat=call('repeat-execution-observes',dict(mode='request',request=frame(q)));check('no-second-attempt',repeat['operation_id']==id and before=={f.name:f.read_bytes() for f in Path(p['state_directory']).iterdir()})
        def private(status='completed',state=None):
            value={k:copy.deepcopy(v) for k,v in final['result'].items() if k in NATIVE_KEYS}
            if state is not None:value['state']=copy.deepcopy(state)
            return dict(schema='org.disked.verification-admission-prototype/1',status=status,operation_id=id,value=value,diagnostic='',platform_code='0')
        call('synthetic-valid-completion',dict(mode='audit',request=frame(q),reply=private(),expected_grant=grant))
        mutations=[('missing-id',lambda v:v.update(operation_id=None)),('foreign-id',lambda v:v.update(operation_id='verify-op:'+'0'*32)),('incomplete-history',lambda v:v['value'].update(history_complete=False)),('wrong-digest',lambda v:v['value'].update(definition_digest='sha256:'+'0'*64)),('missing-collection-validation',lambda v:v['value'].pop('collection_validation')),('false-quiescence',lambda v:v['value']['state'].update(quiescent=False)),('bad-counters',lambda v:v['value']['state']['progress'].update(covered_bytes='0')),('u64-overflow',lambda v:v['value']['state'].update(sequence=str(2**64))),('foreign-capture',lambda v:v['value']['state']['binding'].update(capture_epoch='capture:'+'0'*32)),('unknown-reply-field',lambda v:v['value'].update(force=True))]
        for name,mutate in mutations:
            v=private();mutate(v);out=call(name,dict(mode='audit',request=frame(q),reply=v),exits=(6,));check('invalid-dispatched-reply-unresolved',out['execute_calls']==1 and out['response']['result']['definition_digest']==q['definition_digest'])
        active=next(row['state'] for row in rows if row['state']['phase']!='finished');v=private('accepted_running',active);v['value'].pop('collection_validation');v['value'].pop('attachment_applicability');v['value']['worker_observation']='running'
        call('synthetic-running-with-id',dict(mode='audit',request=frame(q),reply=v),exits=(5,));v['operation_id']=None;call('running-requires-id',dict(mode='audit',request=frame(q),reply=v),exits=(6,))
        v=private();v['value']['attachment_applicability']='changed';call('changed-attachment-no-success',dict(mode='audit',request=frame(q),reply=v),exits=(6,));call('changed-attachment-inspection-completes',dict(mode='observe-reply',reply=v))
        v=private();v['value']['state']['disposition']='unknown';v['value']['state']['outcome'].update(status='unknown',resource_revalidation='changed',after={'malformed':True});call('malformed-uncertain-resources-withheld',dict(mode='audit',request=frame(q),reply=v),exits=(6,))
        v=private();v['value']['definition']['request_raw']=' '*1048576;call('post-dispatch-oversized-definition',dict(mode='audit',request=frame(q),reply=v),exits=(6,))
        w=dict(operation_id=id,state_directory=p['state_directory']);watched=call('completed-watch-history',dict(mode='watch',parameters=w));events=watched['result']['events']
        check('watch-independent-records',len(events)==len(rows) and [e['payload']['record'] for e in events]==rows and watched['result']['last_sequence']==str(len(rows)))
        for e in events:bundle.validate('urn:disked:schema:verification-operation-event:1',e)
        read=reader(header,events+[events[-1]]);check('reader-progress-and-duplicate',all(row.get('accepted') for row in read[:-1]) and read[-1]['accepted'] is False and read[-1]['sequence']==str(len(rows)))
        extended=copy.deepcopy(events[0]);extended['future_observation']={'value':'preserve'};check('compatible-reader-preserves-addition',reader(header,[extended])[0]['preserved']==extended)
        try:bundle.validate('urn:disked:schema:verification-operation-event:1',extended)
        except SpecError:check('strict-producer-rejects-addition',True)
        else:raise AssertionError('Producer schema permitted an unknown field')
        for name,alter in [('wrong-operation',lambda e:e.update(operation_id='verify-op:'+'0'*32)),('unknown-required-feature',lambda e:e.update(required_features=['unavailable/1'])),('record-digest',lambda e:e['payload']['record'].update(digest='0'*64)),('request-identity',lambda e:e['payload'].update(request_id='')),('observer-identity',lambda e:e['payload'].update(observer_epoch='watch:bad')),('wrong-envelope-sequence',lambda e:e.update(sequence=str(2**64)))]:
            bad=copy.deepcopy(events[1]);alter(bad);read=reader(header,[events[0],bad,events[1]])
            check('reader-transaction-'+name,read[1].get('error') and read[1]['sequence']=='1' and read[2]['accepted'] and read[2]['sequence']=='2')
        resumed=dict(w,after_sequence=str(len(rows)),after_digest=rows[-1]['digest'],worker_epoch=rows[-1]['state']['binding']['worker_epoch'])
        check('resume-no-duplicate-records',call('watch-resume',dict(mode='watch',parameters=resumed))['result']['events']==[])
        snap=call('watch-snapshot',dict(mode='watch',parameters=dict(w,snapshot=True)))['result']['events'];check('snapshot-explicit-sequence',len(snap)==1 and snap[0]['type']=='verify.operation.snapshot' and reader(header,snap,snapshot=True)[0]['accepted'])
        for name,bad in [('wrong-cursor',dict(resumed,after_digest='f'*64)),('wrong-epoch',dict(resumed,worker_epoch='worker:'+'f'*32)),('follow-limit',dict(w,follow_ms='2001')),('missing-cursor-anchor',dict(w,after_sequence='1'))]:call(name,dict(mode='watch',parameters=bad),exits=(2,))
        negotiated=call('negotiated-event-request',dict(mode='event-request',request=frame(w,'operation.watch',[FEATURE])));check('separate-observer-event-queue',len(negotiated['events'])==len(rows) and negotiated['response']['result']['events']==[])
        call('wrong-feature-domain',dict(mode='audit',request=frame(p,'image.verify',[FEATURE]),reply={}),exits=(3,))
        call('unknown-required-feature',dict(mode='audit',request=frame(p,features=['unavailable/1']),reply={}),exits=(3,))
        call('finished-cancel',dict(mode='cancel',operation_id=id,state_directory=p['state_directory']));check('watch-never-rewrites-records',(Path(p['state_directory'])/'verification.records').read_bytes()==raw)
        with image.open('r+b') as f:f.seek(65536);f.write(bytes([expected[65536]^1]))
        mp=fixture('mismatch');mr=call('mismatch-prepare',dict(mode='request',request=frame(mp)))['result'];mq=execute(mr);ms=call('mismatch-execute',dict(mode='request',request=frame(mq)),exits=(4,5,6));mf=wait(ms['operation_id'],mp['state_directory']);independent(mp,mf)
        check('actual-mismatch-confirmed-prefix',mf['status']=='completed' and mf['result']['state']['outcome']['status']=='mismatch' and mf['result']['state']['outcome']['covered_bytes']=='65536');call('mismatch-repeat-failed',dict(mode='request',request=frame(mq)),exits=(4,));image.write_bytes(expected)
        def fault_fixture(name):
            fp=fixture(name);fr=call(name+'-prepare',dict(mode='request',request=frame(fp)),exe=fault)['result'];return fp,execute(fr)
        fp,fq=fault_fixture('cancel-prefix');start=call('cancel-start',dict(mode='request',request=frame(fq)),exits=(5,),exe=fault,extra=dict(DISKED_VERIFICATION_WORKER_TEST_PROGRESS_DELAY='1'))
        deadline=time.monotonic()+10
        while True:
            observed=call('cancel-wait-prefix',dict(mode='inspect',operation_id=start['operation_id'],state_directory=fp['state_directory']),exe=fault)
            if int(observed['result']['state']['progress']['covered_bytes']):break
            assert time.monotonic()<deadline;time.sleep(.02)
        cancel=call('cancel-request',dict(mode='cancel',operation_id=start['operation_id'],state_directory=fp['state_directory']),exe=fault);check('request-not-worker-observation',cancel['result']['cancellation_request']=='requested' and cancel['result']['state']['cancellation_observation']=='not_observed')
        cf=wait(start['operation_id'],fp['state_directory'],fault);independent(fp,cf);check('actual-cancelled-prefix',cf['result']['state']['outcome']['status']=='cancelled' and cf['result']['state']['outcome']['covered_bytes']=='65536');call('cancelled-repeat-failed',dict(mode='request',request=frame(fq)),exits=(4,),exe=fault)
        fp,fq=fault_fixture('observer-failure');start=call('observer-start',dict(mode='request',request=frame(fq)),exits=(5,),exe=fault,extra=dict(DISKED_VERIFICATION_WORKER_TEST_EFFECT_DELAY='1'))
        ow=dict(operation_id=start['operation_id'],state_directory=fp['state_directory'],follow_ms='2000');watch=call('observer-read-failure',dict(mode='watch',parameters=ow),exits=(6,),exe=fault,extra=dict(DISKED_VERIFICATION_WATCH_TEST_READ_FAILURE='1'))
        check('observer-retains-last-state-cursor',watch['result']['events'] and int(watch['result']['last_sequence'])>0 and watch['result']['state']['phase']!='finished' and watch['result']['worker_observation']=='running')
        closed=call('closed-observer',dict(mode='closed-event-request',request=frame(ow,'operation.watch',[FEATURE])),exe=fault);check('closed-observer-no-events',closed['events']==[])
        of=wait(start['operation_id'],fp['state_directory'],fault);independent(fp,of);check('observer-failure-does-not-cancel',of['result']['state']['outcome']['status']=='matched' and of['result']['state']['cancellation_observation']=='not_observed')
        fp,fq=fault_fixture('retention-failure');start=call('retention-fault-start',dict(mode='request',request=frame(fq)),exits=(5,6),exe=fault,extra=dict(DISKED_TEST_STORE_FAULT='verification_collection.short'));rf=wait(start['operation_id'],fp['state_directory'],fault)
        check('retention-failure-keeps-actual-verdict',rf['status']=='completed' and rf['result']['state']['disposition']=='unknown' and rf['result']['state']['outcome']['status']=='matched' and rf['result']['state']['retention']['state']=='uncertain');independent(fp,rf);call('uncertain-repeat-no-restart',dict(mode='request',request=frame(fq)),exits=(6,),exe=fault)
        fp,fq=fault_fixture('delayed-admission');started=time.monotonic();start=call('admission-timeout-keeps-operation',dict(mode='request',request=frame(fq)),exits=(6,),exe=fault,extra=dict(DISKED_VERIFICATION_WORKER_TEST_ADMISSION_DELAY='1'))
        check('admission-timeout-retains-routing',time.monotonic()-started<5 and start['operation_id'] and start['result']['definition_digest']==fq['definition_digest'] and start['result']['state_directory']==fp['state_directory'])
        call('cancel-during-admission',dict(mode='cancel',operation_id=start['operation_id'],state_directory=fp['state_directory']),exe=fault)
        af=wait(start['operation_id'],fp['state_directory'],fault);independent(fp,af);check('cancel-before-provider-no-verdict',af['result']['state']['outcome'] is None and af['result']['state']['disposition']=='cancelled');call('admission-cancelled-repeat',dict(mode='request',request=frame(fq)),exits=(4,),exe=fault)
        large=copy.deepcopy(prepared);d=large['definition'];d['request_raw']=d['request_raw']+' '*(32768-len(d['request_raw'].encode()))
        d['case_source']['files'][0]['metadata']['bytes']='32768';d['case_source']['files'][0]['digest']=digest(d['request_raw'].encode())
        for selected in (d['store'],d['case_source'],d['image_binding']['image'],d['image_binding']['map']):selected['ancestors']=[copy.deepcopy(selected['ancestors'][-1]) for _ in range(120)]
        for role in ('image','map'):d['verification']['resources'][role]['epoch']=digest(canonical(d['image_binding'][role]))
        d['verification_digest']=digest(canonical(d['verification']));large['definition_digest']=digest(canonical(d))
        bundle.validate('urn:disked:schema:verification-worker-definition:1',d);check('valid-private-definition-exceeds-public-budget',65536<len(canonical(d))<262144)
        out=call('oversized-private-review-not-presented',dict(mode='audit',request=frame(p),reply=large),exits=(3,));check('public-budget-before-execution',out['prepare_calls']==1 and out['execute_calls']==0)
        out=call('oversized-public-request-not-dispatched',dict(mode='audit',request=frame(execute(large)),reply={}),exits=(2,));check('oversized-request-zero-ports',out['prepare_calls']==out['execute_calls']==0)
        check('original-case-and-source-unchanged',original=={f.name:f.read_bytes() for f in case.iterdir() if f.is_file()} and src.read_bytes()==image.read_bytes()==expected)
        p=subprocess.run([str(product),'--json','image','verify','prepare',case_id,str(image),'--map',str(mapping),'--case-state-dir',str(case),'--state-dir',str(owned/'unselected')],capture_output=True,cwd=root,env=env,timeout=15)
        check('product-handler-remains-unavailable',p.returncode==3 and json.loads(p.stdout)['status']=='refused' and not (owned/'unselected').exists())
    report=dict(checks=len(checks),observations=checks,samples=samples,scope='Private command probe/shared provisional service; generated ordinary files and owned Windows workers only.',owner_accepted=False,product_admitted=False,physical_admitted=False)
    if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(checks=len(checks),status='passed',actual_samples=len(samples))))
if __name__=='__main__':main()
