"""Independent joins/disclosures and actual owned Windows file exports.

Synthetic source/executor faults are identified separately from native effects.
No paths in retained data are followed by the joined report/coordinator.
"""
import argparse,copy,ctypes as C,itertools,json,os,queue,subprocess,sys,threading,time
from pathlib import Path
from ctypes import wintypes as W
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,digest,source_bytes,map_check,history_check,fixture_directory,owned_process,K
from test_report_worker import report_process
from test_image_observation import POLICIES,expected_support
from test_image_collection import CLAIMS as COLLECTION_CLAIMS

CLAIMS=dict(historical_verification='recorded',authenticity='not_established',custody_authentication='not_established',current_image_state='not_established',worker_exit='not_observed',power_loss_persistence='not_established',physical_admission=False,mutation_authority=False)
ACQ_CLAIMS=dict(authenticity='not_established',source_preservation='not_established',current_image_verification='not_performed',worker_exit='not_observed_by_this_case',physical_admission=False,power_loss_persistence='not_established',mutation_authority=False)
FLAGS=('case_read','collection_read','report_write','host_effects')
def grant(hash_='$prepared',bits=(True,)*4):return dict(definition_digest=hash_,**dict(zip(FLAGS,bits)))

def acquisition_support(v,p):
    h=v['before'];d=h['definition'];before=dict(phase='before',kind='recorded-execution-definition');after=None
    if p['raw_values']:before.update({k:d['plan'][k] for k in ('bytes','chunk_bytes','retry_limit','read_policy','substitution')})
    if v['after'] is not None:
        o=v['after']['outcome'];after=dict(phase='after',kind='recorded-worker-outcome',recorded_status=o['status'],consistency=o['consistency'],uncertain_effect=o['uncertain_effect'])
        if p['raw_values']:after.update({k:o[k] for k in ('checkpoint_bytes','source_bytes','substituted_bytes','attempt_read_bytes','attempt_written_bytes','attempt_verified_bytes','records')})
    result=dict(schema='org.disked.acquisition-case-support-prototype/1',scope='recorded-ordinary-file-acquisition',policy=p,collection_state=v['collection_state'],before=before,after=after,accepted_records=str(len(v['records'])),history_complete=v['history']['complete'],original_binding='omitted',claims=ACQ_CLAIMS)
    if p['interpretations']:result['interpretation']=dict(kind='inference',basis='validated-recorded-worker-statements',current_image_success='not_established')
    if p['identifiers']:result.update({k:h[k] for k in ('operation_id','attempt_id','worker_epoch')},code_identity=dict(source_revision=d['source_revision'],input_digest=d['input_digest'],image_digest='sha256:'+d['image_digest'],target_profile=d['target_profile'],configuration_digest=None))
    if p['identifiers'] and p['raw_values'] and p['customer_data']:result['declared_paths']={k:d['request'][k] for k in ('source','destination','map')}
    return result

def combined_support(acq,coll,p):
    rows=[]
    for r in coll['records']:
        row=dict(sequence=r['sequence'],observation=expected_support(r['observation'],p))
        if p['identifiers']:row['observer']=r['observer']
        rows.append(row)
    collection=dict(schema='org.disked.image-verification-collection-support-prototype/1',scope='recorded-image-verification-collection',policy=p,records=rows,original_case_claims=ACQ_CLAIMS,claims=COLLECTION_CLAIMS)
    if p['identifiers']:collection['collection_id']=coll['collection_id']
    return dict(schema='org.disked.acquisition-verification-support-prototype/1',scope='recorded-acquisition-verification',policy=p,acquisition=acquisition_support(acq,p),verification=collection,claims=CLAIMS)

def main():
    ap=argparse.ArgumentParser()
    for n in ('probe','fault','product'):ap.add_argument('--'+n,type=Path,required=True)
    ap.add_argument('--worker',type=Path);ap.add_argument('--worker-fault',type=Path)
    ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path);a=ap.parse_args()
    root=a.root.resolve();probe=a.probe.resolve();fault=a.fault.resolve();product=a.product.resolve();facts=[];exports=[];samples=[]
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_REPORT_','DISKED_TEST_','DISKED_ACQ_','DISKED_VERIFICATION_'))}
    def check(name,ok,**data):assert ok,(name,data);facts.append(dict(name=name,passed=True,**data))
    def call(v,refusal=None,exe=probe,extra=None):
        r=subprocess.run([str(exe)],input=canonical(v),capture_output=True,cwd=root,env=dict(env,**(extra or {})),timeout=30);assert not r.stderr,(r.returncode,r.stderr)
        out=json.loads(r.stdout.splitlines()[-1])
        if refusal:check('refuse-'+refusal,r.returncode==3 and refusal in out.get('refusal',''),actual_diagnostic=out.get('refusal'))
        else:assert r.returncode==0 and 'refusal' not in out,(r.returncode,out)
        return out
    def cli(args):
        r=subprocess.run([str(product),'--json',*args],capture_output=True,cwd=root,env=env,timeout=15);assert r.returncode in (0,5,6) and not r.stderr,(r.returncode,r.stdout[:500],r.stderr);return json.loads(r.stdout)
    def finish(id,store,verification=False):
        deadline=time.monotonic()+25
        while True:
            out=cli(['operation','inspect',id,'--state-dir',str(store)]);s=(out.get('result') or {}).get('state')
            if s and s['phase']=='finished':
                handle=report_process(s,product) if verification else owned_process(s,product)
                if handle:
                    try:assert K.WaitForSingleObject(handle,3000)==0,('retain live fixture',s)
                    finally:K.CloseHandle(handle)
                check('actual-owned-worker-exit',s['quiescent'],kind='verification' if verification else 'acquisition',binding=s['binding']);return out
            assert time.monotonic()<deadline,('retain unresolved dependencies',out);time.sleep(.03)
    def audit(v,acq,coll,request,history):
        expected=dict(schema='org.disked.acquisition-verification-report-prototype/1',acquisition=dict(revision=digest(canonical(acq)),view=acq),verification=dict(revision=digest(canonical(coll)),view=coll),claims=CLAIMS)
        check('exact-independent-full-join',v['report']==expected and v['revision']==digest(canonical(expected)) and v['copy_guard'])
        check('exact-original-inputs',coll['request_raw'].encode()==request and bytes.fromhex(coll['history_hex'])==history and coll['original_case']==acq and acq['claims']==ACQ_CLAIMS and acq['history']['raw_digest']==digest(history))
        private={v['revision'],coll['context_digest'],coll['case_revision'],digest(history),digest(request),digest(canonical(coll)+b'\n')}
        for row in coll['records']:
            private|={row['digest'],row['observation_revision'],row['observation']['definition_digest']}
        for n,(p,row) in enumerate(zip(POLICIES,v['projections'])):
            selected=combined_support(acq,coll,p);body=canonical(selected)+b'\n';desc=dict(bytes=str(len(body)),digest=digest(body),policy=p,encoding='private-case-json-utf8-lf/1',scope='recorded-acquisition-verification-support')
            check('exact-support-policy-'+str(n),row==dict(policy=p,support=selected,artifact=desc,artifact_bytes=body.decode()))
            allowed={x for r in coll['records'] for x in r['observation']['verifier'].values()} if p['identifiers'] else set()
            if p['identifiers']:allowed|=set(acq['code_identity'].values())-{None}
            check('private-bindings-omitted-'+str(n),not any(x in body.decode() for x in private-allowed) and ('private-customer' in body.decode())==(p['identifiers'] and p['raw_values'] and p['customer_data']))
    def saved(v,name):
        path=Path(v['definition']['effect']['resources']['destination']['location']);body=path.read_bytes() if path.exists() else None
        exports.append(dict(name=name,outcome=v['outcome'],receipt=v['receipt'],bytes=None if body is None else len(body),sha256=None if body is None else digest(body)))
        return body
    K.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,W.LPVOID,W.DWORD,W.DWORD,W.HANDLE];K.CreateFileW.restype=W.HANDLE
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        case=owned/'case';case.mkdir();state=owned/'verify';state.mkdir();src=owned/'private-customer-source.img';image=owned/'private-customer-copy.img';mapping=owned/'private-customer-copy.map';data=source_bytes(262145);src.write_bytes(data)
        reviewed=cli(['image','acquire','prepare',str(src),str(image),'--map',str(mapping),'--state-dir',str(case)])['result']
        start=cli(['image','acquire','execute','--definition-json',canonical(reviewed['definition']).decode(),'--definition-digest',reviewed['definition_digest'],'--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects']);finish(start['operation_id'],case)
        check('actual-acquisition-bytes',src.read_bytes()==image.read_bytes()==data);map_check(mapping,data)
        p=cli(['image','verify','prepare',start['operation_id'],str(image),'--map',str(mapping),'--case-state-dir',str(case),'--state-dir',str(state)])['result']
        begun=cli(['image','verify','execute','--definition-json',canonical(p['definition']).decode(),'--definition-digest',p['definition_digest'],*['--allow-'+f for f in ('case-read','image-read','map-read','store-write','host-effects','private-metadata')]])
        end=finish(begun['operation_id'],state,True);s=end['result']['state'];retained=state/'verification.collection';body=retained.read_bytes();coll=json.loads(body);request=(case/'acquisition.request').read_bytes();history=(case/'acquisition.records').read_bytes();acq=coll['original_case']
        history_check(case/'acquisition.records');previous='0'*64;rows=[]
        for n,line in enumerate((state/'verification.records').read_bytes().splitlines(),1):
            row=json.loads(line);unsigned={k:v for k,v in row.items() if k!='digest'};check('independent-verification-history-chain',canonical(row)==line and row['previous']==previous and digest(canonical(unsigned))=='sha256:'+row['digest'] and row['state']['sequence']==str(n));previous=row['digest'];rows.append(row)
        check('independent-verification-terminal',rows[-1]['state']==s and (state/'verification.records').read_bytes().endswith(b'\n'))
        check('actual-selected-retention',s['outcome']['status']=='matched' and s['retention']['state']=='verified' and body==canonical(coll)+b'\n' and digest(body)==s['retention']['digest'] and len(body)==int(s['retention']['bytes']) and coll['records'][0]['observation']['outcome']==s['outcome'] and coll['records'][0]['observer']=={n:s['binding'][n] for n in ('attempt_id','worker_epoch','capture_epoch','process_id','process_created')})
        # Independently retain both native histories before fixture removal.
        samples.append(dict(acquisition_request_hex=request.hex(),acquisition_history_hex=history.hex(),verification_request_hex=(state/'verification.request').read_bytes().hex(),verification_history_hex=(state/'verification.records').read_bytes().hex(),collection_hex=body.hex(),terminal=end))
        base=dict(mode='prepare',case_operation_id=start['operation_id'],case_directory=str(case),collection_path=str(retained),collection_digest=digest(body),policy=POLICIES[0],destination=str(owned/'support.json'))
        reviewed=call(base);audit(reviewed,acq,coll,request,history);check('native-prepare-no-output',not Path(base['destination']).exists() and reviewed['definition_digest']==digest(canonical(reviewed['definition'])))
        model=dict(mode='model',raw_request=request.decode(),raw_history_hex=history.hex(),collection_bytes=body.decode(),policy=base['policy'],sources=reviewed['definition']['sources'],resources=reviewed['definition']['effect']['resources'],grant=grant())
        pure=call(model);audit(pure,acq,coll,request,history);check('model-completed-scope-isolation',pure['outcome']['status']=='completed' and pure['old_scope_refused'] and not pure['file_io'])
        for bits in itertools.product((False,True),repeat=4):
            if all(bits):continue
            v=call(dict(model,grant=grant(bits=bits)));check('synthetic-false-grant-zero-ports',v['observer_calls']==v['effect_calls']=='0' and not v['created'],bits=bits)
        for hash_ in ('sha256:'+'0'*64,digest(canonical(reviewed['definition']['effect']))):
            v=call(dict(model,grant=grant(hash_)));check('synthetic-wrong-or-inner-grant-zero-ports',v['observer_calls']==v['effect_calls']=='0')
        for key in ('no_case_port','no_collection_port','no_effect_port'):
            v=call(dict(model,**{key:True}));check('synthetic-missing-port-zero-ports',v['observer_calls']==v['effect_calls']=='0',key=key)
        for role in ('case','collection'):
            for phase in ('first','late'):
                for kind in ('changed','throws'):
                    v=call(dict(model,fault=role+'-'+phase+'-'+kind));o=v['outcome'];states=o['source_observations'];check('synthetic-source-observation-retained',states[role]['state']==('changed' if kind=='changed' else 'unresolved') and int(states[role]['check_sequence'])>0,role=role,phase=phase)
                    if phase=='first':check('synthetic-initial-no-effect',v['effect_calls']=='0' and not v['created'] and states['collection' if role=='case' else 'case']['state']==('not_observed' if role=='case' else 'matched'))
                    else:check('synthetic-late-keeps-actual-executor-result',o['status']=='failed' and o['output']['status']=='completed' and v['output_bytes']==pure['output_bytes'] and o['output']==pure['outcome']['output'] and states['collection' if role=='case' else 'case']['state']=='matched')
        for kind in ('executor-throws','executor-throws-after','visit-budget'):
            v=call(dict(model,fault=kind));o=v['outcome'];check('synthetic-unobserved-executor-uncertain',o['status']=='unknown' and o['output']['uncertain_effect'] and o['output']['written_bytes'] is None,kind=kind)
            if kind=='visit-budget':check('synthetic-bounded-source-visits',v['observer_calls']==o['source_checks']=='256')
        v=call(dict(model,fault='contradictory-completion'));check('synthetic-contradictory-output-not-completed',v['outcome']['status']=='unknown' and v['outcome']['diagnostic']=='verification_case_output_claim')
        call(dict(model,raw_request=request.decode()+' '),'verification_case_original_mismatch')
        call(dict(model,raw_history_hex=(history+b'{"torn":').hex()),'verification_case_original_mismatch')
        call(dict(model,raw_request=request.decode()+' '*(32769-len(request))),'verification_case_input_limit')
        call(dict(model,raw_history_hex=('ff'*1048577)),'image_collection_history_encoding')
        empty=copy.deepcopy(coll);empty['records']=[];call(dict(model,collection_bytes=(canonical(empty)+b'\n').decode()),'verification_case_empty_collection')
        altered=copy.deepcopy(model);altered['sources']['case']['files'][0]['digest']='sha256:'+'0'*64;call(altered,'verification_case_original_binding')
        altered=copy.deepcopy(model);altered['sources']['collection']['digest']='sha256:'+'0'*64;call(altered,'verification_case_collection_binding')
        altered=copy.deepcopy(reviewed['definition']);altered['sources']['collection']['metadata']['bytes']='18446744073709551616';call(dict(mode='validate',definition=altered),'verification_case_export_integer')
        altered=copy.deepcopy(model);altered['sources']['collection']['metadata'].update({k:altered['sources']['case']['files'][0]['metadata'][k] for k in ('file_id','volume_id')});call(altered,'verification_case_source_alias')
        altered=copy.deepcopy(model);altered['resources']['destination']['location']=str(retained);call(altered,'verification_case_output_alias')
        altered=copy.deepcopy(model);altered['resources']['destination']['location']=reviewed['definition']['sources']['case']['store']['path']+'\\acquisition.cancel';call(altered,'verification_case_output_alias')
        # Both native sources are held through an explicit reviewed session.
        child=subprocess.Popen([str(probe),'--hold'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env);child.stdin.write(canonical(base)+b'\n');child.stdin.flush()
        ready=json.loads(child.stdout.readline());assert ready['event']=='verification-case-reviewed' and child.poll() is None
        try:
            for path in (retained,case/'acquisition.request',case/'acquisition.records'):
                handle=K.CreateFileW(str(path),0x40000000,7,None,3,0x200000,None);check('actual-held-source-denies-writer',handle==W.HANDLE(-1).value and C.get_last_error()==32,path=path.name)
                if handle!=W.HANDLE(-1).value:K.CloseHandle(handle)
            child.stdin.write(canonical(dict(grant=grant(ready['definition_digest']),second_call=True))+b'\n');child.stdin.flush();out,err=child.communicate(timeout=25);assert child.returncode==0 and not err;done=json.loads(out)
        finally:assert child.poll() is not None,'retain live reviewed session and sources'
        selected=saved(done,'held-completed');check('actual-joint-export',done['outcome']['status']=='completed' and done['second_call_refusal']=='verification_case_session_used' and selected==canonical(combined_support(acq,coll,POLICIES[0]))+b'\n' and digest(selected)==ready['definition']['effect']['artifact']['digest'])
        check('actual-separate-final-observations',all(x['state']=='matched' for x in done['outcome']['source_observations'].values()) and int(done['outcome']['source_observations']['case']['check_sequence'])+1==int(done['outcome']['source_checks'])==int(done['outcome']['source_observations']['collection']['check_sequence']))
        call(dict(mode='execute',definition=ready['definition'],grant=grant(ready['definition_digest'])),'export_output_exists');check('actual-existing-output-preserved',Path(base['destination']).read_bytes()==selected)
        for n,(p,row) in enumerate(zip(POLICIES,reviewed['projections'])):
            v=call(dict(base,mode='execute',policy=p,destination=str(owned/('selected-'+str(n)+'.json')),grant=grant()));actual=saved(v,'selected-'+str(n));check('actual-sixteen-selected-artifacts',v['outcome']['status']=='completed' and actual==row['artifact_bytes'].encode(),policy=p)
        for n,bits in enumerate(itertools.product((False,True),repeat=4)):
            if all(bits):continue
            path=owned/('denied-'+str(n)+'.json');v=call(dict(base,mode='execute',destination=str(path),grant=grant(bits=bits)));check('actual-false-grant-no-output',v['outcome']['status']=='refused' and not path.exists() and v['outcome']['source_checks']=='0',bits=bits)
        for phase in ('created','written','flushed','read'):
            destination=owned/('interrupted-'+phase+'.json');v=call(dict(base,mode='execute',destination=str(destination),grant=grant()),exe=fault,extra={'DISKED_REPORT_TEST_EVENT':phase});actual=saved(v,'fault-'+phase);o=v['outcome'];check('actual-injected-output-retained',o['status']=='failed' and actual is not None and v['receipt']['output_receipt']['output_created_observed'],phase=phase)
            check('actual-interrupted-bytes',actual==(b'' if phase=='created' else selected),phase=phase)
            if phase=='created':check('actual-create-ack-uncertain',o['output']['output_state']=='uncertain' and o['output']['uncertain_effect'])
            if phase=='written':check('actual-written-ack-uncertain',o['output']['written_bytes'] is None)
            if phase=='flushed':check('actual-flush-ack-uncertain',o['output']['flush']=='uncertain')
            if phase=='read':check('actual-read-ack-not-counted',o['output']['read_bytes']=='0')
        v=call(dict(base,mode='execute',destination=str(owned/'cancel.json'),grant=grant(),cancel_before=True));check('actual-cancel-before-create',v['outcome']['status']=='cancelled' and v['outcome']['output']['output_state']=='not_created' and not (owned/'cancel.json').exists())
        # Recreate only the explicitly selected collection after review; exact
        # content equality cannot authorize the replacement file generation.
        destination=owned/'replacement.json';review=call(dict(base,destination=str(destination)));retained.rename(state/'old.collection');retained.write_bytes(body)
        call(dict(mode='execute',definition=review['definition'],grant=grant(review['definition_digest'])),'verification_case_reviewed_definition_changed');check('actual-recreated-source-no-output',not destination.exists())
        for destination in (retained,case/'acquisition.cancel',Path(str(retained).upper())):
            original=destination.read_bytes();call(dict(base,destination=str(destination)),'export_output_exists');check('actual-source-alias-preserved',destination.read_bytes()==original)
        # No selected source/image/map paths are reopened from the retained
        # content; the native join still works when these original files vanish.
        for path in (src,image,mapping):path.rename(path.with_name(path.name+'.retained'))
        new=call(dict(base,destination=str(owned/'missing-original.json')));check('actual-original-media-paths-not-followed',new['report']==reviewed['report'] and new['revision']==reviewed['revision'])
        check('actual-retained-metadata-unchanged',request==(case/'acquisition.request').read_bytes() and history==(case/'acquisition.records').read_bytes() and body==retained.read_bytes())
        if a.worker or a.worker_fault:
            assert a.worker and a.worker_fault
            from test_joined_report_worker import exercise
            exercise(root,owned,a.worker.resolve(),a.worker_fault.resolve(),product,env,start['operation_id'],case,retained,body,acq,coll,check,samples,exports)
    result=dict(passed=True,checks=len(facts),observations=facts,actual_exports=exports,samples=samples,limitations=['Private synchronous two-source/export adapter on the recorded Windows host; no public worker/frontend admission or stable API.','Synthetic source/executor faults are separate from actual generated native acquisition, verification, retention and file effects.','Historical claims, source observations, output facts and actual worker exit are separate; no authenticated custody/current-image/physical/power-loss claim.','Full DE-W034, all scoped 0.1.0 platforms/storage, owner and privilege/release gates remain open.'])
    if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS acquisition verification report:',len(facts),'checks;',len(exports),'actual completed/retained exports')
if __name__=='__main__':main()
