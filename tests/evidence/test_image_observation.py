"""Independent immutable observation, disclosure and actual support-export checks.

Inputs/changes are repository-owned generated files. Synthetic receipt changes
are separate from native acquisition/image/metadata/export observations.
"""
import argparse,copy,ctypes as C,json,os,queue,subprocess,sys,threading,time
from ctypes import wintypes as W
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,digest,source_bytes,map_check,fixture_directory,owned_process,K

FIELDS=('identifiers','raw_values','interpretations','customer_data')
POLICIES=[dict(zip(FIELDS,[bool(n & (1<<i)) for i in range(4)])) for n in range(16)]
CLAIMS=dict(authenticity='not_established',source_preservation='not_established',point_in_time_acquisition='not_established',latest_image_state='not_established',worker_exit='not_observed',physical_admission=False,mutation_authority=False)
COUNTERS=('records','consumed_map_bytes','covered_bytes','read_bytes','matched_bytes','source_bytes','substituted_bytes')

def expected_support(v,p):
    o=v['outcome']
    result=dict(schema='org.disked.image-verification-support-prototype/1',scope='recorded-acquired-image-verification',policy=p,
        verification=dict(recorded_status=o['status'],resource_revalidation=o['resource_revalidation'],sealed=o['sealed'],pending=o['pending']),
        case_revalidation=v['case_revalidation'],image_binding_revalidation=v['image_binding_revalidation'],attachment_applicability=v['attachment_applicability'],claims=CLAIMS)
    if p['raw_values']:result.update(counters={k:o[k] for k in COUNTERS},clock=v['clock'])
    if p['identifiers']:result.update(identifiers={k:v['case'][k] for k in ('id','operation_id','attempt_id','worker_epoch')},verifier=v['verifier'])
    if p['interpretations']:result['interpretation']=dict(kind='inference',basis='recorded-verification-observation',result='matching-observation-bound-to-case' if o['status']=='matched' and v['attachment_applicability']=='applicable' else 'unqualified')
    return result

def main():
    parser=argparse.ArgumentParser()
    for name in ('probe','product'):parser.add_argument('--'+name,required=True,type=Path)
    parser.add_argument('--root',default=Path('.'),type=Path);parser.add_argument('--evidence',type=Path);a=parser.parse_args()
    root=a.root.resolve();probe=a.probe.resolve();product=a.product.resolve();observations=[];samples=[];exports=[]
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_ACQ_','DISKED_TEST_','DISKED_REPORT_'))}
    def check(name,condition,**facts):assert condition,(name,facts);observations.append(dict(name=name,passed=True,**facts))
    def audit(value,kind):
        v=value['observation'];check(kind+'-immutable-revision',value['revision']==digest(canonical(v)) and value['immutable_copy_guard'])
        check(kind+'-original-claims',value['original_case_claims']['current_image_verification']=='not_performed' and v['claims']==CLAIMS)
        check(kind+'-projection-count',len(value['projections'])==16)
        private={v['request_raw_digest'],v['request_semantic_digest'],v['definition_digest'],value['revision'],v['case']['revision']}
        private|={v['definition']['plan_digest'],v['case_source_before']['files'][1]['digest']}
        for role in ('image','map'):private|={v['definition']['resources'][role][k] for k in ('identity','epoch','recorded_epoch')}
        for p,row in zip(POLICIES,value['projections']):
            expected=expected_support(v,p);bytes_=canonical(expected)+b'\n';d=row['artifact'];body=row['artifact_bytes'].encode()
            check(kind+'-exact-policy-'+str(POLICIES.index(p)),row['policy']==p and row['support']==expected and body==bytes_ and d==dict(bytes=str(len(body)),digest=digest(body),policy=p,encoding='private-case-json-utf8-lf/1',scope='recorded-image-verification-support'))
            allowed=set(v['verifier'].values()) if p['identifiers'] else set()
            check(kind+'-privacy-policy-'+str(POLICIES.index(p)),not any(s in body.decode() for s in private-allowed) and str(root) not in body.decode() and 'verification_customer_marker' not in body.decode())
        return value
    def call(value,refusal=None,audit_kind=None):
        r=subprocess.run([str(probe)],input=canonical(value),capture_output=True,cwd=root,env=env,timeout=25)
        assert not r.stderr,(r.returncode,r.stderr);out=json.loads(r.stdout)
        if refusal:check('refuse-'+refusal,r.returncode==3 and refusal in out['refusal'])
        else:
            assert r.returncode==0 and 'refusal' not in out,(r.returncode,out)
            if audit_kind:audit(out,audit_kind)
        return out
    def cli(args):
        r=subprocess.run([str(product),'--json',*args],capture_output=True,cwd=root,env=env,timeout=20)
        assert r.returncode in (0,5,6) and not r.stderr,(r.returncode,r.stdout,r.stderr);return json.loads(r.stdout)
    def acquisition(folder,size):
        folder.mkdir();state=folder/'state';state.mkdir();src=folder/'private-customer-source.img';dst=folder/'private-customer-copy.img';mapping=folder/'private-customer-map.jsonl';expected=source_bytes(size);src.write_bytes(expected)
        review=cli(['image','acquire','prepare',str(src),str(dst),'--map',str(mapping),'--state-dir',str(state)])['result']
        first=cli(['image','acquire','execute','--definition-json',canonical(review['definition']).decode(),'--definition-digest',review['definition_digest'],'--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects'])
        assert first['operation_id'],first;deadline=time.monotonic()+30
        while True:
            end=cli(['operation','inspect',first['operation_id'],'--state-dir',str(state)]);s=end.get('result',{}).get('state',{})
            if s.get('phase')=='finished':
                assert end['status']=='completed' and s['quiescent'] and s['outcome']['status']=='completed',end;break
            assert time.monotonic()<deadline,('preserve unresolved dependencies',end);time.sleep(.025)
        handle=owned_process(s,product)
        if handle:
            try:assert K.WaitForSingleObject(handle,3000)==0
            finally:K.CloseHandle(handle)
        check('actual-acquisition-exact-bytes',src.read_bytes()==dst.read_bytes()==expected,bytes=size);map_check(mapping,expected)
        return dict(mode='native',operation_id=first['operation_id'],state_directory=str(state),image=str(dst),map=str(mapping)),expected
    def held(value,action):
        child=subprocess.Popen([str(probe),'--hold'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env)
        child.stdin.write(canonical(value)+b'\n');child.stdin.flush();lines=queue.Queue();threading.Thread(target=lambda:lines.put(child.stdout.readline()),daemon=True).start()
        ready=json.loads(lines.get(timeout=15));assert ready['event']=='observation-held' and int(ready['pid'])==child.pid and child.poll() is None
        try:action()
        finally:child.stdin.write(b'x');child.stdin.flush()
        out,err=child.communicate(timeout=25);assert child.returncode==0 and not err,(child.returncode,out,err);return json.loads(out)
    def export(value,items,alter=None,grant_change=None):
        child=subprocess.Popen([str(probe),'--exports'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env)
        child.stdin.write(canonical(dict(value,exports=items))+b'\n');child.stdin.flush();lines=queue.Queue()
        def reader():
            for line in child.stdout:lines.put(line)
        threading.Thread(target=reader,daemon=True).start();reviews=[]
        for i,item in enumerate(items):
            review=json.loads(lines.get(timeout=20));assert review['event']=='support-export-reviewed' and review['index']==str(i),review
            check('actual-export-prepare-no-output',not Path(item['destination']).exists())
            check('actual-export-exact-review-digest',review['definition_digest']==digest(canonical(review['definition'])))
            check('existing-product-review-refuses-new-private-scope',review['public_scope_refused'])
            if alter:alter()
            grant=dict(definition_digest=review['definition_digest'],report_write=True,host_effects=True)
            if grant_change:grant.update(grant_change)
            if grant['definition_digest']=='$inner':grant['definition_digest']=digest(canonical(review['definition']['effect']))
            child.stdin.write(canonical(grant)+b'\n');child.stdin.flush();reviews.append(review)
        out=json.loads(lines.get(timeout=25));assert child.wait(timeout=15)==0 and not child.stderr.read(),out;child.stdin.close();child.stdout.close();child.stderr.close()
        return out,reviews
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        native,expected=acquisition(owned/'nonempty',262145)
        before={str(p.relative_to(owned)):digest(p.read_bytes()) for p in owned.rglob('*') if p.is_file()}
        actual=call(native,audit_kind='actual-matched');samples.append(actual)
        check('actual-reader-creates-no-file',before=={str(p.relative_to(owned)):digest(p.read_bytes()) for p in owned.rglob('*') if p.is_file()})
        check('actual-verifier-code-identity',actual['observation']['verifier']['image_digest']==digest(probe.read_bytes()))
        check('actual-clock-observed',actual['observation']['clock']['domain']=='windows-filetime-wall' and int(actual['observation']['clock']['elapsed_ms'])>=0)
        output=owned/'support';output.mkdir();items=[dict(destination=str(output/(str(i)+'.json')),policy=p) for i,p in enumerate(POLICIES)]
        written,reviews=export(native,items);audit(written,'actual-exported');exports.extend(written['exports'])
        for item,receipt,review in zip(items,written['exports'],reviews):
            body=Path(item['destination']).read_bytes();support=expected_support(written['observation'],item['policy']);out=receipt['outcome']
            check('actual-file-exact-support',body==canonical(support)+b'\n' and digest(body)==review['definition']['effect']['artifact']['digest'])
            check('actual-export-binds-private-observation',review['definition']['observation_revision']==written['revision'] and review['definition']['case_revision']==written['observation']['case']['revision'] and receipt['receipt']['definition_digest']==digest(canonical(review['definition']['effect'])))
            check('actual-file-completed-receipt',out['status']=='completed' and out['verified_bytes']==str(len(body)) and not out['uncertain_effect'] and receipt['receipt']['output_created_observed'])
        for i,(key,change) in enumerate([('report_write',False),('host_effects',False),('definition_digest','sha256:'+'0'*64),('definition_digest','$inner')]):
            destination=output/(str(i)+'-refused.json');result,_=export(native,[dict(destination=str(destination),policy=POLICIES[0])],grant_change={key:change})
            check('actual-no-effect-grant-'+key+str(i),result['exports'][0]['outcome']['status']=='refused' and not destination.exists())
        image=Path(native['image']);damaged=bytearray(expected);damaged[65536]^=1;image.write_bytes(damaged)
        mismatch=call(native,audit_kind='actual-mismatch');check('actual-mismatch-recorded',mismatch['observation']['outcome']['status']=='mismatch' and mismatch['observation']['outcome']['matched_bytes']=='65536')
        image.write_bytes(expected)
        K.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,W.LPVOID,W.DWORD,W.DWORD,W.HANDLE];K.CreateFileW.restype=W.HANDLE
        K.GetFileTime.argtypes=[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)];K.SetFileTime.argtypes=K.GetFileTime.argtypes
        request=Path(native['state_directory'])/'acquisition.request'
        metadata=K.CreateFileW(str(request),0x100,7,None,3,0x200000,None);assert metadata and metadata!=W.HANDLE(-1).value
        original=W.FILETIME();assert K.GetFileTime(metadata,C.byref(original),None,None);changed=(original.dwHighDateTime<<32|original.dwLowDateTime)+10000000;stamp=W.FILETIME(changed&0xffffffff,changed>>32)
        try:
            stale=held(native,lambda:check('actual-case-metadata-change',bool(K.SetFileTime(metadata,C.byref(stamp),None,None))))
            audit(stale,'actual-stale-case');check('actual-independent-image-fact-retained',stale['observation']['outcome']['status']=='matched' and stale['observation']['case_revalidation']=='unavailable' and stale['observation']['attachment_applicability']=='unavailable')
        finally:assert K.SetFileTime(metadata,C.byref(original),None,None);K.CloseHandle(metadata)
        metadata=K.CreateFileW(str(request),0x100,7,None,3,0x200000,None);assert metadata and metadata!=W.HANDLE(-1).value
        try:
            destination=output/'stale-case-export.json'
            rejected,_=export(native,[dict(destination=str(destination),policy=POLICIES[0])],alter=lambda:check('actual-case-change-after-export-review',bool(K.SetFileTime(metadata,C.byref(stamp),None,None))))
            check('actual-stale-export-no-output',rejected['exports'][0]['outcome']['status']!='completed' and rejected['exports'][0]['outcome']['output_state']=='not_created' and not destination.exists())
            check('actual-export-does-not-rewrite-historical-observation',rejected['observation']['outcome']['status']=='matched' and rejected['observation']['attachment_applicability']=='applicable')
        finally:assert K.SetFileTime(metadata,C.byref(original),None,None);K.CloseHandle(metadata)
        metadata=K.CreateFileW(str(image),0x100,7,None,3,0x200000,None);assert metadata and metadata!=W.HANDLE(-1).value
        image_created=W.FILETIME();assert K.GetFileTime(metadata,C.byref(image_created),None,None);later=(image_created.dwHighDateTime<<32|image_created.dwLowDateTime)+10000000;image_stamp=W.FILETIME(later&0xffffffff,later>>32)
        try:
            unbound=held(native,lambda:check('actual-image-metadata-change',bool(K.SetFileTime(metadata,C.byref(image_stamp),None,None))))
            audit(unbound,'actual-unbound-image');check('actual-unavailable-image-is-not-success',unbound['observation']['outcome']['status']=='unknown' and unbound['observation']['attachment_applicability']=='unavailable')
        finally:assert K.SetFileTime(metadata,C.byref(image_created),None,None);K.CloseHandle(metadata)
        empty,_=acquisition(owned/'empty',0);zero=call(empty,audit_kind='actual-empty');check('actual-empty-bound-observation',zero['observation']['outcome']['status']=='matched' and zero['observation']['outcome']['matched_bytes']=='0')
        base=copy.deepcopy(actual['model_inputs']);model=call(base,audit_kind='model-replay');check('model-exact-immutable-view',model['revision']==actual['revision'] and model['input_snapshot_guard'])
        def bad(name,change,code):
            value=copy.deepcopy(base);change(value);call(value,refusal=code);observations[-1]['input_kind']='synthetic-record-alteration';observations[-1]['name']=name
        mutations=[
            ('wrong-definition-digest',lambda x:x.update(definition_digest='sha256:'+'0'*64),'image_observation_definition'),
            ('wrong-plan-digest',lambda x:x['definition'].update(plan_digest='sha256:'+'0'*64),'image_observation_definition'),
            ('wrong-case-revision',lambda x:x['context']['case_before'].update(case_revision='sha256:'+'0'*64),'image_observation_case'),
            ('wrong-history-digest',lambda x:x['context']['case_before']['files'][1].update(digest='sha256:'+'0'*64),'image_observation_case'),
            ('wrong-request-digest',lambda x:x['context']['case_before']['files'][0].update(digest='sha256:'+'0'*64),'image_observation_request'),
            ('wrong-request-bytes',lambda x:x.update(raw_request=x['raw_request']+' '),'image_observation_request'),
            ('wrong-image-epoch',lambda x:x['context']['image_before']['image']['metadata'].update(written='1'),'image_observation_binding'),
            ('wrong-image-access',lambda x:x['context']['image_before']['image'].update(access='write'),'image_observation_access'),
            ('false-passed-case',lambda x:x['context'].update(case_after=None),'case_export_shape'),
            ('false-unavailable-case',lambda x:x['context'].update(case_revalidation='unavailable'),'image_observation_revalidation'),
            ('false-changed-case',lambda x:x['context'].update(case_revalidation='changed'),'image_observation_revalidation'),
            ('bad-code-digest',lambda x:x['context']['verifier'].update(image_digest='sha256:wrong'),'image_observation_identity'),
            ('code-target-is-not-arbitrary-customer-text',lambda x:x['context']['verifier'].update(target_profile='private-customer-location'),'image_observation_target'),
            ('bad-source-state',lambda x:x['context']['verifier'].update(source_state='approved'),'image_observation_code_state'),
            ('clock-overflow',lambda x:x['context']['clock'].update(started=str(2**64)),'image_observation_integer'),
            ('zero-clock',lambda x:x['context']['clock'].update(started='0'),'image_observation_clock'),
            ('invalid-clock-domain',lambda x:x['context']['clock'].update(domain='monotonic-guessed'),'image_observation_clock'),
            ('wrong-outcome-claims',lambda x:x['outcome']['claims'].update(authenticity='established'),'observation_probe_outcome_shape'),
            ('matched-without-seal',lambda x:x['outcome'].update(sealed=False),'image_observation_match'),
            ('sealed-pending',lambda x:x['outcome'].update(pending=True),'image_observation_seal'),
            ('wrong-coverage',lambda x:x['outcome'].update(covered_bytes='1'),'image_observation_counters'),
            ('partition-overflow',lambda x:x['outcome'].update(source_bytes=str(2**64-1),substituted_bytes='1'),'image_observation_counters'),
            ('unobserved-read-count',lambda x:x['outcome'].update(read_bytes='0'),'image_observation_counters'),
            ('record-budget',lambda x:x['outcome'].update(records='1048577'),'image_observation_counters'),
            ('map-accounting',lambda x:x['outcome'].update(consumed_map_bytes='1'),'image_observation_counters'),
            ('map-inexact-full-accounting',lambda x:x['outcome'].update(consumed_map_bytes=str(int(x['outcome']['consumed_map_bytes'])-1)),'image_observation_match'),
            ('prefix-without-before',lambda x:x['outcome'].update(status='unknown',before=None,after=None,resource_revalidation='unavailable'),'image_observation_unobserved_prefix'),
            ('false-passed-resources',lambda x:x['outcome'].update(after=None),'image_observation_resources'),
            ('matched-resource-change',lambda x:x['outcome'].update(resource_revalidation='changed'),'image_observation_resources'),
            ('unsafe-diagnostic',lambda x:x['outcome'].update(status='unknown',diagnostic='\x1b[2J'),'image_observation_diagnostic'),
            ('outcome-integer-overflow',lambda x:x['outcome'].update(read_bytes=str(2**64)),'observation_probe_integer'),
            ('outcome-unknown-field',lambda x:x['outcome'].update(unsafe_extension=True),'observation_probe_outcome_shape'),
            ('bad-policy-boolean',lambda x:x.update(policy=dict(POLICIES[0],identifiers='yes')),'image_observation_policy')]
        for args in mutations:bad(*args)
        regressed=copy.deepcopy(base);regressed['context']['clock']['finished']=str(int(regressed['context']['clock']['started'])-1);value=call(regressed)
        check('adjustable-wall-clock-regression-retained',value['observation']['clock']['wall_clock_regressed'] is True and value['observation']['clock']['elapsed_ms']==base['context']['clock']['elapsed_ms'])
        unobserved=copy.deepcopy(base);unobserved['context']['clock']=dict(domain='unobserved',started=None,finished=None,elapsed_ms=None);value=call(unobserved)
        check('missing-clock-retained',value['observation']['clock']['wall_clock_regressed'] is None)
        changed=copy.deepcopy(base);changed['context']['case_after']['files'][0]['metadata']['changed']='1';changed['context']['case_revalidation']='changed';value=call(changed)
        check('changed-case-matching-bytes-separate',value['observation']['outcome']['status']=='matched' and value['observation']['attachment_applicability']=='changed')
        diagnostic=copy.deepcopy(base);diagnostic['outcome'].update(status='unknown',diagnostic='verification_customer_marker');audit(call(diagnostic),'model-private-diagnostic')
        alternate=copy.deepcopy(base);alternate['raw_request']=' '+alternate['raw_request']+'\n'
        f=alternate['context']['case_before']['files'][0];f['metadata']['bytes']=str(len(alternate['raw_request'].encode()));f['digest']=digest(alternate['raw_request'].encode());alternate['context']['case_after']=copy.deepcopy(alternate['context']['case_before']);value=call(alternate)
        check('raw-request-binding-not-confused-with-semantic-case',value['observation']['case']['revision']==actual['observation']['case']['revision'] and value['revision']!=actual['revision'])
        changed=copy.deepcopy(base);changed['context']['image_after']['image']['metadata']['changed']='1';changed['context']['image_binding_revalidation']='changed';value=call(changed)
        check('late-image-binding-does-not-erase-earlier-match',value['observation']['outcome']['status']=='matched' and value['observation']['attachment_applicability']=='changed')
        check('original-source-image-map-retained',Path(native['image']).read_bytes()==expected and Path(native['map']).is_file())
    evidence=dict(passed=True,checks=len(observations),observations=observations,samples=samples,exports=exports,
        source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root)),probe_sha256=digest(probe.read_bytes()),product_sha256=digest(product.read_bytes()),
        scope='Private immutable observations and all 16 typed disclosures; actual generated acquisitions, image/case changes and explicitly granted support exports; separate synthetic contradictions. No product availability, authenticated custody, latest-image authority or full-platform/physical qualification.')
    if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(evidence,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in evidence.items() if k not in ('observations','samples','exports')}))
if __name__=='__main__':main()
