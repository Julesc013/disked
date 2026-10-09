"""Independent bounded historical collection/retention and ordinary-file checks.
Generated images only; native effects and synthetic record alterations differ.
"""
import argparse,copy,ctypes as C,json,os,queue,subprocess,sys,threading,time
from ctypes import wintypes as W
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,digest,source_bytes,map_check,fixture_directory,owned_process,K
from test_case import encode
from test_image_observation import POLICIES,expected_support

CLAIMS=dict(authenticity='not_established',custody_authentication='not_established',latest_image_state='not_established',worker_exit='not_observed',power_loss_persistence='not_established',physical_admission=False,mutation_authority=False)
def main():
    p=argparse.ArgumentParser()
    for name in ('probe','observation-probe','product'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--root',default=Path('.'),type=Path);p.add_argument('--evidence',type=Path);a=p.parse_args()
    root=a.root.resolve();probe=a.probe.resolve();observer=a.observation_probe.resolve();product=a.product.resolve();facts=[];samples=[];exports=[]
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_ACQ_','DISKED_TEST_','DISKED_REPORT_'))}
    def check(name,condition,**data):assert condition,(name,data);facts.append(dict(name=name,passed=True,**data))
    def audit(out,name):
        v=out['collection'];body=encode(v);retained=body+b'\n';history=bytes.fromhex(v['history_hex']);context=digest(encode(dict(collection_id=v['collection_id'],case_revision=v['case_revision'],request_digest=digest(v['request_raw'].encode()),history_digest=digest(history))))
        check(name+'-full-canonical-identity',out['revision']==digest(body) and out['retention_bytes'].encode()==retained and out['copy_guard'])
        check(name+'-context-original',v['context_digest']==context and v['case_revision']==digest(encode(v['original_case'])) and json.loads(v['request_raw'])==v['original_case']['before'] and v['original_case']['history']['raw_digest']==digest(history) and v['claims']==CLAIMS)
        check(name+'-retention-description',out['retention']==dict(bytes=str(len(retained)),digest=digest(retained),policy=None,encoding='private-image-verification-collection-json-utf8-lf/1',scope='recorded-image-verification-collection-private'))
        previous='sha256:'+'0'*64
        private={out['revision'],out['retention']['digest'],context,v['case_revision'],digest(v['request_raw'].encode()),digest(history)}
        for n,row in enumerate(v['records'],1):
            unsigned={k:x for k,x in row.items() if k!='digest'}
            check(name+'-record-'+str(n),row['sequence']==str(n) and row['context_digest']==context and row['previous_digest']==previous and row['digest']==digest(encode(unsigned)) and row['observation_revision']==digest(encode(row['observation'])) and row['observation']['case']['revision']==v['case_revision'])
            previous=row['digest'];private|={row['digest'],row['observation_revision'],row['observation']['definition_digest']}
            for role in ('image','map'):private|=set(row['observation']['definition']['resources'][role][k] for k in ('identity','epoch','recorded_epoch'))
        for n,(policy,selected) in enumerate(zip(POLICIES,out['projections'])):
            rows=[]
            for row in v['records']:
                selected_row=dict(sequence=row['sequence'],observation=expected_support(row['observation'],policy))
                if policy['identifiers']:selected_row['observer']=row['observer']
                rows.append(selected_row)
            expected=dict(schema='org.disked.image-verification-collection-support-prototype/1',scope='recorded-image-verification-collection',policy=policy,records=rows,original_case_claims=v['original_case']['claims'],claims=CLAIMS)
            if policy['identifiers']:expected['collection_id']=v['collection_id']
            selected_bytes=encode(expected)+b'\n'
            check(name+'-exact-support-'+str(n),selected['support']==expected and selected['artifact_bytes'].encode()==selected_bytes and selected['artifact']==dict(bytes=str(len(selected_bytes)),digest=digest(selected_bytes),policy=policy,encoding='private-case-json-utf8-lf/1',scope='recorded-image-verification-collection-support'))
            allowed={x for row in v['records'] for x in row['observation']['verifier'].values()} if policy['identifiers'] else set()
            check(name+'-private-data-omitted-'+str(n),not any(x in selected_bytes.decode() for x in private-allowed) and str(root) not in selected_bytes.decode() and 'private-customer' not in selected_bytes.decode())
        return out
    def call(value,refusal=None,name=None,args=()):
        r=subprocess.run([str(probe),*args],input=canonical(value),capture_output=True,cwd=root,env=env,timeout=35);assert not r.stderr,(r.returncode,r.stderr);out=json.loads(r.stdout)
        if refusal:check('refuse-'+refusal,r.returncode==3 and refusal in out.get('refusal',''),actual_diagnostic=out.get('refusal'),exit_code=r.returncode)
        else:
            assert r.returncode==0 and 'refusal' not in out,(r.returncode,out)
            if name:audit(out,name)
        return out
    def observe(value):
        child=subprocess.Popen([str(observer)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env)
        out,err=child.communicate(canonical(value),timeout=35);assert child.returncode==0 and not err,(child.returncode,out,err);result=json.loads(out)
        binding=result['observer_binding'];created=W.FILETIME();ended=W.FILETIME();kernel=W.FILETIME();user=W.FILETIME()
        K.GetProcessTimes.argtypes=[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)]
        check('actual-observer-process-identity',int(binding['process_id'])==child.pid and bool(K.GetProcessTimes(W.HANDLE(int(child._handle)),C.byref(created),C.byref(ended),C.byref(kernel),C.byref(user))) and int(binding['process_created'])==(created.dwHighDateTime<<32|created.dwLowDateTime))
        return result
    def cli(args):
        r=subprocess.run([str(product),'--json',*args],capture_output=True,cwd=root,env=env,timeout=20);assert r.returncode in (0,5,6) and not r.stderr,(r.returncode,r.stdout,r.stderr);return json.loads(r.stdout)
    def save(value,items,alter=None):
        child=subprocess.Popen([str(probe),'--save'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env)
        child.stdin.write(canonical(dict(value,exports=items))+b'\n');child.stdin.flush();lines=queue.Queue()
        def reader():
            for line in child.stdout:lines.put(line)
        threading.Thread(target=reader,daemon=True).start();reviews=[]
        for item in items:
            review=json.loads(lines.get(timeout=20));assert review['event']=='collection-save-reviewed' and child.poll() is None
            check('actual-reviewed-no-output',not Path(item['destination']).exists() and review['definition_digest']==digest(encode(review['definition'])) and review['public_scope_refused'])
            grant=dict(definition_digest=review['definition_digest'],report_write=True,host_effects=True,private_metadata=item['private'])
            if alter:grant.update(alter(review))
            child.stdin.write(canonical(grant)+b'\n');child.stdin.flush();reviews.append(review)
        child.stdin.close();child.stdin=None;assert child.wait(timeout=35)==0;assert not child.stderr.read();result=json.loads(lines.get(timeout=10));assert len(result['exports'])==len(items)
        return result,reviews
    with fixture_directory(root/'.aide-local/goal-0.1.0') as owned:
        state=owned/'state';state.mkdir();src=owned/'private-customer-source.img';image=owned/'private-customer-copy.img';mapping=owned/'private-customer-map.jsonl';expected=source_bytes(262145);src.write_bytes(expected)
        review=cli(['image','acquire','prepare',str(src),str(image),'--map',str(mapping),'--state-dir',str(state)])['result']
        first=cli(['image','acquire','execute','--definition-json',canonical(review['definition']).decode(),'--definition-digest',review['definition_digest'],'--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects']);assert first['operation_id'],first
        deadline=time.monotonic()+35
        while True:
            end=cli(['operation','inspect',first['operation_id'],'--state-dir',str(state)]);s=end.get('result',{}).get('state',{})
            if s.get('phase')=='finished':assert end['status']=='completed' and s['quiescent'] and s['outcome']['status']=='completed',end;break
            assert time.monotonic()<deadline,('preserve unresolved dependencies',end);time.sleep(.025)
        process=owned_process(s,product)
        if process:
            try:assert K.WaitForSingleObject(process,3000)==0
            finally:K.CloseHandle(process)
        check('actual-original-acquisition',src.read_bytes()==image.read_bytes()==expected);map_check(mapping,expected)
        native=dict(mode='native',operation_id=first['operation_id'],state_directory=str(state),image=str(image),map=str(mapping));first_observation=observe(native)
        check('actual-first-matched',first_observation['observation']['outcome']['status']=='matched')
        damaged=bytearray(expected);damaged[65536]^=1;image.write_bytes(damaged);second_observation=observe(native)
        check('actual-second-mismatch',second_observation['observation']['outcome']['status']=='mismatch' and second_observation['observation']['outcome']['matched_bytes']=='65536');image.write_bytes(expected)
        model=dict(mode='model',collection_id='collection:'+'a'*32,raw_request=first_observation['model_inputs']['raw_request'],raw_history_hex=first_observation['model_inputs']['records_hex'],observations=[dict(observation=x['observation'],observer=x['observer_binding']) for x in (first_observation,second_observation)])
        actual=call(model,name='actual-matched-then-mismatch');samples.append(actual)
        duplicate=call(dict(model,failed_append=model['observations'][0]))
        check('failed-append-preserves-prior-snapshot',duplicate['rejected_append']==dict(diagnostic='image_collection_duplicate',unchanged=True) and duplicate['revision']==actual['revision'])
        check('original-facts-not-rewritten',actual['collection']['original_case']['claims']['current_image_verification']=='not_performed' and len(actual['collection']['records'])==2)
        replay=call(dict(mode='restore',retention_bytes=actual['retention_bytes']),name='pure-reloaded');check('exact-reloaded-snapshot',replay['revision']==actual['revision'] and replay['collection']==actual['collection'])
        items=[dict(destination=str(owned/'private.collection.json'),private=True)]+[dict(destination=str(owned/('support-'+str(n)+'.json')),private=False,policy=p) for n,p in enumerate(POLICIES)]
        result,reviews=save(model,items);exports.extend(result['exports'])
        for item,review,result_row in zip(items,reviews,result['exports']):
            output=Path(item['destination']);body=review['artifact_bytes'].encode();outcome=result_row['outcome'];receipt=result_row['receipt']
            check('actual-selected-retention-or-support',outcome['status']=='completed' and not outcome['uncertain_effect'] and output.read_bytes()==body and receipt['artifact_digest']==digest(body) and int(outcome['verified_bytes'])==len(body) and int(outcome['read_bytes'])==len(body) and receipt['flush_scope']=='per-file-FlushFileBuffers-API-only')
        retained=Path(items[0]['destination']);read=dict(mode='read',path=str(retained),expected_digest=actual['retention']['digest']);loaded=call(read,name='actual-file-reloaded')
        original_bytes=retained.read_bytes();call(dict(model,exports=[items[0]]),refusal='export_output_exists',args=('--save',));check('actual-existing-output-preserved',retained.read_bytes()==original_bytes)
        check('current-retention-binding-separate',loaded['source_state']=='passed' and loaded['binding_before']==loaded['binding_after'] and loaded['revision']==actual['revision'])
        for n,(key,value) in enumerate([('definition_digest','sha256:'+'0'*64),('report_write',False),('host_effects',False),('private_metadata',False),('inner',None)]):
            destination=owned/('refused-'+str(n)+'.json')
            denied,_=save(model,[dict(destination=str(destination),private=True)],alter=lambda r,k=key,v=value:{'definition_digest':digest(encode(r['definition']['effect']))} if k=='inner' else {k:v})
            check('actual-no-private-effect-'+key,denied['exports'][0]['outcome']['status']=='refused' and not destination.exists())
        check('private-disabled-support-still-selected',all(x['outcome']['status']=='completed' for x in result['exports'][1:]))
        call(dict(read,expected_digest='sha256:'+'0'*64),refusal='image_collection_file_digest')
        invalid=owned/'invalid.collection.json';invalid.write_bytes(retained.read_bytes()[:-1]);call(dict(mode='read',path=str(invalid),expected_digest=digest(invalid.read_bytes())),refusal='image_collection_retention_limit')
        invalid.write_bytes(b'0'*1048578);call(dict(mode='read',path=str(invalid),expected_digest=digest(invalid.read_bytes())),refusal='image_collection_file_limit')
        # Hold selected file, change only its actual creation metadata, and retain
        # the frozen historical snapshot separately from current applicability.
        K.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,W.LPVOID,W.DWORD,W.DWORD,W.HANDLE];K.CreateFileW.restype=W.HANDLE
        K.GetFileTime.argtypes=[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)];K.SetFileTime.argtypes=K.GetFileTime.argtypes
        metadata=K.CreateFileW(str(retained),0x100,7,None,3,0x200000,None);assert metadata and metadata!=W.HANDLE(-1).value
        original=W.FILETIME();assert K.GetFileTime(metadata,C.byref(original),None,None);ticks=(original.dwHighDateTime<<32|original.dwLowDateTime)+10000000;changed=W.FILETIME(ticks&0xffffffff,ticks>>32)
        child=subprocess.Popen([str(probe),'--hold'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env)
        child.stdin.write(canonical(read)+b'\n');child.stdin.flush();lines=queue.Queue();threading.Thread(target=lambda:lines.put(child.stdout.readline()),daemon=True).start()
        ready=json.loads(lines.get(timeout=20));assert ready['event']=='collection-file-held' and int(ready['pid'])==child.pid and child.poll() is None
        try:
            check('actual-held-retention-metadata-change',bool(K.SetFileTime(metadata,C.byref(changed),None,None)));child.stdin.write(b'x');child.stdin.flush()
            out,err=child.communicate(timeout=35);assert child.returncode==0 and not err,(child.returncode,out,err);stale=json.loads(out)
            check('immutable-retention-facts-survive-source-change',stale['revision']==actual['revision'] and stale['source_state']=='unavailable' and stale['binding_after'] is None and stale['source_diagnostic']=='image_collection_file_changed')
        finally:
            assert child.poll() is not None,'preserve live dependencies';assert K.SetFileTime(metadata,C.byref(original),None,None);K.CloseHandle(metadata)
        def rejected(name,change,code='image_collection_record_mismatch',rehash=False):
            value=copy.deepcopy(actual['collection']);before=encode(value);change(value);assert before!=encode(value),('mutation must alter input',name)
            if rehash:
                for row in value['records']:row['observation_revision']=digest(encode(row['observation']));row['digest']=digest(encode({k:v for k,v in row.items() if k!='digest'}))
            call(dict(mode='restore',retention_bytes=(encode(value)+b'\n').decode()),refusal=code);facts[-1].update(name=name,input_kind='synthetic-record-alteration')
        for key in ('sequence','context_digest','previous_digest','digest','observation_revision'):
            rejected('wrong-'+key,lambda v,k=key:v['records'][0].update({k:'2' if k=='sequence' else 'sha256:'+('1' if k=='previous_digest' else '0')*64}))
        rejected('extra-top-level',lambda v:v.update(extra=True),'image_collection_shape')
        rejected('extra-record',lambda v:v['records'][0].update(extra=True),'image_collection_shape')
        rejected('unknown-version',lambda v:v.update(schema='org.disked.image-verification-collection-prototype/2'),'image_collection_version')
        rejected('wrong-original-case-claim',lambda v:v['original_case']['claims'].update(current_image_verification='passed'),'image_collection_retained_mismatch')
        rejected('wrong-original-case-revision',lambda v:v.update(case_revision='sha256:'+'0'*64),'image_collection_retained_mismatch')
        rejected('wrong-observation-case',lambda v:v['records'][0]['observation']['case_source_before'].update(case_revision='sha256:'+'0'*64),'image_observation_case',True)
        rejected('edited-observation-claims-rehashed',lambda v:v['records'][0]['observation']['claims'].update(latest_image_state='verified'),'image_observation_retained_mismatch',True)
        rejected('edited-computed-clock-rehashed',lambda v:v['records'][0]['observation']['clock'].update(wall_clock_regressed=True),'image_observation_retained_mismatch',True)
        rejected('contradictory-match-rehashed',lambda v:v['records'][0]['observation']['outcome'].update(sealed=False),'image_observation_match',True)
        rejected('overflow-counter-rehashed',lambda v:v['records'][0]['observation']['outcome'].update(records='18446744073709551616'),'image_observation_integer',True)
        for key,val in [('process_id','0'),('process_id','4294967296'),('process_created','0'),('process_created','18446744073709551616')]:
            rejected('wrong-observer-'+key+val,lambda v,k=key,x=val:v['records'][0]['observer'].update({k:x}),'image_collection_process',True)
        rejected('wrong-observer-worker',lambda v:v['records'][0]['observer'].update(worker_epoch='attempt:'+'a'*32),'image_collection_identity',True)
        rejected('duplicate-capture-epoch',lambda v:v['records'][1]['observer'].update(capture_epoch=v['records'][0]['observer']['capture_epoch']),'image_collection_duplicate',True)
        rejected('duplicate-observation',lambda v:v['records'][1].update(observation=copy.deepcopy(v['records'][0]['observation'])),'image_collection_duplicate',True)
        rejected('attempt-reused-with-other-worker',lambda v:v['records'][1]['observer'].update(attempt_id=v['records'][0]['observer']['attempt_id']),'image_collection_attempt_binding',True)
        rejected('worker-reused-with-other-process',lambda v:v['records'][1]['observer'].update(worker_epoch=v['records'][0]['observer']['worker_epoch']),'image_collection_worker_binding',True)
        continuous=copy.deepcopy(model);continuous['observations'][1]['observer']=dict(continuous['observations'][0]['observer'],capture_epoch='capture:'+'c'*32)
        unchanged_code=call(continuous);check('same-worker-code-and-process-continuity',len(unchanged_code['collection']['records'])==2,input_kind='synthetic-observer-binding')
        changed_code=copy.deepcopy(continuous);changed_code['observations'][1]['observation']['verifier']['image_digest']='sha256:'+'d'*64
        call(changed_code,refusal='image_collection_worker_code_binding');facts[-1]['input_kind']='synthetic-code-declaration'
        call(dict(mode='restore',retention_bytes=actual['retention_bytes']+'\n'),refusal='image_collection_retained_mismatch')
        call(dict(mode='restore',retention_bytes=json.dumps(actual['collection'],indent=2)+'\n'),refusal='image_collection_retained_mismatch')
        for policy in (dict(POLICIES[0],extra=False),dict(POLICIES[0],identifiers='yes')):call(dict(model,policy=policy),refusal='image_collection_')
        # Sixteen synthetic captures exercise the exact record bound. Their new
        # clock/epoch declarations are explicitly not native observer evidence.
        many=copy.deepcopy(model);many['observations']=[]
        for n in range(17):
            row=copy.deepcopy(model['observations'][0]);row['observer']['capture_epoch']='capture:'+format(n,'032x');row['observation']['clock']['elapsed_ms']=str(n+100)
            many['observations'].append(row)
        maximum=call(dict(many,observations=many['observations'][:16]),name='synthetic-max-records');check('exact-sixteen-record-budget',len(maximum['collection']['records'])==16,input_kind='synthetic-clock-capture-declarations')
        call(many,refusal='image_collection_record_limit')
        raw_history=bytes.fromhex(model['raw_history_hex']);call(dict(model,observations=[],raw_history_hex=(raw_history+b'x'*(524188-len(raw_history))).hex()),refusal='output_limit_exceeded')
        for malformed in ('f','FF','0g'):call(dict(model,observations=[],raw_history_hex=malformed),refusal='image_collection_history_encoding')
        # A real torn tail changes the original case revision and remains in the
        # durable bytes; no repaired/terminal acquisition is inferred from it.
        history=state/'acquisition.records';history.write_bytes(history.read_bytes()+b'{"torn":\xff\0');torn_observation=observe(native)
        torn_model=dict(model,collection_id='collection:'+'b'*32,raw_history_hex=torn_observation['model_inputs']['records_hex'],observations=[dict(observation=torn_observation['observation'],observer=torn_observation['observer_binding'])])
        torn=call(torn_model,name='actual-torn-history');check('exact-torn-tail-preserved',bytes.fromhex(torn['collection']['history_hex'])==history.read_bytes() and bytes.fromhex(torn['collection']['history_hex']).endswith(b'{"torn":\xff\0') and torn['collection']['original_case']['collection_state']=='unresolved' and not torn['collection']['original_case']['history']['complete'] and torn_observation['model_inputs']['records'] is None)
        torn_file=owned/'torn.collection.json';saved,_=save(torn_model,[dict(destination=str(torn_file),private=True)]);exports.extend(saved['exports']);check('actual-torn-retention-completed',saved['exports'][0]['outcome']['status']=='completed')
        for path in (image,mapping,state/'acquisition.request',history):path.rename(path.with_name(path.name+'.retained'))
        missing=call(read,name='actual-original-paths-unavailable');check('reader-never-follows-retained-original-paths',missing['revision']==actual['revision'] and missing['source_state']=='passed' and not image.exists() and not history.exists())
        loaded_torn=call(dict(mode='read',path=str(torn_file),expected_digest=torn['retention']['digest']),name='actual-torn-file-reloaded');check('torn-snapshot-exact-after-native-save',loaded_torn['collection']==torn['collection'])
    evidence=dict(passed=True,checks=len(facts),observations=facts,samples=samples,exports=exports,source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root)),probe_sha256=digest(probe.read_bytes()),observation_probe_sha256=digest(observer.read_bytes()),product_sha256=digest(product.read_bytes()),scope='Private historical collection snapshots, exact selected policies, explicit ordinary-file retention/reload and source applicability. Actual generated-file effects and synthetic record alterations are separate. No bounded worker/product availability/authenticated custody/latest-image/all-platform/physical qualification.')
    if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in evidence.items() if k not in ('observations','samples','exports')}))
if __name__=='__main__':main()
