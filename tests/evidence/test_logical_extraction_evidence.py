"""Independent logical-case policy, destination verification and retention oracles."""
import argparse,copy,itertools,json,os,subprocess,sys,time
from pathlib import Path
from test_verification_case import acquisition_support as acq_support,combined_support
from test_image_observation import expected_support
from test_report_worker import report_process
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_fat_content import fixture
from test_acquisition_worker import canonical,digest,fixture_directory,owned_process,K
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'frontend'))
from gui_fixture import Gui,wait

POLICIES=[dict(zip(('identifiers','raw_values','interpretations','customer_data'),v)) for v in itertools.product([False,True],repeat=4)]
def logical_support(case,p):
    v=acq_support(case,p);v['schema']='org.disked.acquisition-case-support-prototype/2';v['scope']='recorded-ordinary-fat-file-extraction'
    if p['raw_values']:
        original=case['before']['definition']['plan']['logical_source'];selected={k:original[k] for k in ('kind','volume_offset','volume_bytes','fat_copy','expected_file_bytes')}
        if p['identifiers']:selected.update({k:original[k] for k in ('node_id','metadata_digest')})
        v['before']['logical_content']=selected
    return v
def logical_join(case,collection,p):
    v=combined_support(case,collection,p);v['schema']='org.disked.acquisition-verification-support-prototype/2'
    v['acquisition']=logical_support(case,p);v['verification']['schema']='org.disked.image-verification-collection-support-prototype/2'
    for row in v['verification']['records']:row['observation']['schema']='org.disked.image-verification-support-prototype/2'
    return v

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('exe','case','verify','collection','output'):ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args();exe=str(a.exe.resolve());records=[];verified=[];passed=False
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_ACQ_','DISKED_TEST_','DISKED_FAT_','DISKED_VERIFICATION_','DISKED_REPORT_'))}
    def note(name,**fields):records.append(dict(name=name,**fields));print('PASS '+name,flush=True)
    def cli(args,exits=(0,)):
        r=subprocess.run([exe,'--json',*args],capture_output=True,env=env,timeout=30)
        assert r.returncode in exits and not r.stderr,(args,r.returncode,r.stdout[-1500:],r.stderr)
        note('cli',exit_code=r.returncode,output_sha256=digest(r.stdout));return json.loads(r.stdout)
    def wire(command,params,exits=(0,)):
        raw=canonical(dict(schema='org.disked.request/1',request_id='logical-evidence',command=command,parameters=params,required_features=[]))
        r=subprocess.run([exe,'protocol','serve','--format','json'],input=raw,capture_output=True,env=env,timeout=30)
        assert r.returncode in exits and not r.stderr,(command,r.returncode,r.stdout[-1500:],r.stderr)
        note(command,exit_code=r.returncode,input_sha256=digest(raw),output_sha256=digest(r.stdout));return json.loads(r.stdout)
    def probe(executable,value,exit_code=0):
        raw=canonical(value);r=subprocess.run([str(executable.resolve())],input=raw,capture_output=True,env=env,timeout=30)
        assert r.returncode==exit_code and not r.stderr,(r.returncode,r.stdout[-1500:],r.stderr)
        note('native-probe',exit_code=r.returncode,input_sha256=digest(raw),output_sha256=digest(r.stdout));return json.loads(r.stdout)
    def finish(first,store,kind):
        end=time.monotonic()+30
        while True:
            out=wire('operation.inspect',dict(operation_id=first['operation_id'],state_directory=str(store)))
            state=out['result']['state']
            if state['phase']=='finished':break
            assert time.monotonic()<end;time.sleep(.02)
        h=owned_process(state,exe) if kind=='acquisition' else report_process(state,Path(exe))
        if h:
            try:assert K.WaitForSingleObject(h,2000)==0
            finally:K.CloseHandle(h)
        assert state['quiescent'];note('actual-worker-exit',kind=kind);return out
    def granted(prepared,flags):return dict(phase='execute',definition=prepared['definition'],definition_digest=prepared['definition_digest'],**{'allow_'+k:True for k in flags})
    catalog=json.loads((Path(__file__).resolve().parents[2]/'spec/catalog/commands.json').read_bytes())
    def command_args(command,params):
        descriptor=next(v for v in catalog['commands'] if v['id']==command);args=list(descriptor['words'])
        for b in sorted([b for b in descriptor['argument_bindings'] if 'position' in b],key=lambda b:b['position']):
            if b['parameter'] in params:args.append(str(params[b['parameter']]))
        for b in descriptor['argument_bindings']:
            if 'option' not in b or b['parameter'] not in params:continue
            value=params[b['parameter']]
            if not b['value_arity']:
                if value:args.append(b['option'])
            else:args.extend([b['option'],canonical(value).decode() if isinstance(value,dict) else str(value)])
        return args
    def native(frontend,params,folder):
        args=command_args('image.verify',params)
        if frontend=='gui':
            ui=Gui(Path(exe),['--gui',*args],render=True)
            try:
                ui.click(109);assert ui.details()['reviewed'];ui.click(110)
                response=wait(lambda:ui.details() if ui.details().get('schema')=='org.disked.response/1' else None)
            finally:ui.close()
            assert ui.code==0 and not ui.error
        else:
            source=folder/(frontend+'-'+params['phase']+'-input.json');target=folder/(frontend+'-'+params['phase']+'-output.json')
            source.write_bytes(canonical(dict(parameters=params,command=args)))
            startup=subprocess.STARTUPINFO();startup.dwFlags=1;startup.wShowWindow=0
            helper=Path(__file__).resolve().parents[1]/'frontend/fat_extraction_console_fixture.py'
            result=subprocess.run([sys.executable,str(helper),exe,str(source),str(target),frontend],env=env,timeout=40,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
            observed=json.loads(target.read_bytes());assert result.returncode==0,observed;response=observed['response'];assert all(observed['restored'].values())
        note('native-'+frontend,phase=params['phase'],status=response['status']);return response
    scratch=Path(__file__).resolve().parents[2]/'.aide-local';scratch.mkdir(exist_ok=True)
    try:
        with fixture_directory(scratch) as root:
            serial=0
            def prepare_extract(bits=12,empty=False,large=False):
                nonlocal serial
                serial+=1;folder=root/str(serial);folder.mkdir();state=folder/'acquisition';state.mkdir()
                kw=dict(chain=(),size=0) if empty else dict(unit=4096,per=16,chain=(3,8,5,11,7,15,4,20,9,24,6,28,10,32,12,35,13,39)) if large else {}
                v,data=fixture(bits,**kw);source=folder/'private-customer-源.img';v.write(source)
                inspect=cli(['image','inspect',str(source),'--view','fat','--volume-offset',str(v.offset),'--volume-bytes',str(v.length)])
                selection=next(r['extraction_selector'] for r in inspect['result']['observation']['nodes']['items'] if r['kind']=='file')
                p=dict(phase='prepare',source=str(source),destination=str(folder/'content.bin'),map=str(folder/'content.map'),state_directory=str(state),logical_source=selection,chunk_bytes='1048576' if large else '4096')
                prepared=wire('filesystem.extract',p)['result'];assert not list(state.iterdir())
                first=wire('filesystem.extract',granted(prepared,('source_read','destination_write','map_write','host_effects')),(0,5));finish(first,state,'acquisition')
                assert Path(p['destination']).read_bytes()==data
                return folder,p,data,first['operation_id']
            def prepare_verify(folder,p,operation,suffix):
                store=folder/suffix;store.mkdir()
                q=dict(phase='prepare',case_operation_id=operation,case_directory=p['state_directory'],image=p['destination'],map=p['map'],state_directory=str(store))
                prepared=wire('image.verify',q)['result'];assert not list(store.iterdir())
                d=prepared['definition'];assert d['schema']=='org.disked.verification-worker-definition-prototype/2'
                assert d['verification']['schema']=='org.disked.acquired-image-verification-definition-prototype/2'
                assert d['verification']['plan']['schema']=='org.disked.acquisition-plan-prototype/2'
                return q,prepared,store
            def verification(q,prepared,store):
                first=wire('image.verify',granted(prepared,('case_read','image_read','map_read','store_write','host_effects','private_metadata')),(0,5))
                out=finish(first,store,'verification');collection_path=store/'verification.collection';assert collection_path.is_file()
                body=collection_path.read_bytes();collection=json.loads(body)
                assert collection['schema']=='org.disked.image-verification-collection-prototype/2' and collection['original_case']['schema']=='org.disked.acquisition-case-prototype/2'
                assert collection['records'][0]['observation']['schema']=='org.disked.image-verification-observation-prototype/2'
                return out,collection_path,collection,body
            for bits,empty,large in [(12,False,False),(16,False,False),(32,False,False),(12,True,False),(16,False,True)]:
                folder,p,data,op=prepare_extract(bits,empty,large);request=Path(p['state_directory'],'acquisition.request').read_bytes();history=Path(p['state_directory'],'acquisition.records').read_bytes()
                q,prepared,store=prepare_verify(folder,p,op,'verification')
                flags=('case_read','image_read','map_read','store_write','host_effects','private_metadata')
                for flag in flags:
                    bad=granted(prepared,flags);bad['allow_'+flag]=False;wire('image.verify',bad,(2,3));assert not list(store.iterdir())
                # Current destination verification opens no original FAT/backing source.
                if bits==12 and not empty:
                    with Path(p['source']).open('r+b') as original:original.seek(0);original.write(b'changed-original')
                out,path,collection,body=verification(q,prepared,store)
                outcome=collection['records'][0]['observation']['outcome'];assert outcome['status']=='matched' and outcome['matched_bytes']==str(len(data))
                assert collection['request_raw'].encode()==request and bytes.fromhex(collection['history_hex'])==history
                assert outcome['claims']['source_preservation']=='not_established' and not outcome['claims']['physical_admission']
                verified.append(dict(bits=bits,bytes=len(data),sha256=digest(data),operation_id=op))
                audited=probe(a.collection,dict(mode='read',path=str(path),expected_digest=digest(body)))
                assert audited['collection']==collection and audited['copy_guard']
                case=collection['original_case']
                for policy in POLICIES:
                    result=probe(a.case,dict(operation_id=op,state_directory=p['state_directory'],policy=policy));expected=logical_support(case,policy)
                    assert json.loads(result['artifact_bytes'])==expected and result['artifact']['digest']==digest(result['artifact_bytes'].encode())
                    assert result['case']==case and result['revision_after_view_edit']==result['case_revision']
                    selected=expected['before'].get('logical_content',{})
                    assert ('metadata_digest' in selected)==(policy['raw_values'] and policy['identifiers'])
                    assert ('private-customer' in result['artifact_bytes'])==(policy['identifiers'] and policy['raw_values'] and policy['customer_data'])
                # Backing-resource changes are refused even with a recomputed valid map chain.
                rows=[json.loads(line) for line in Path(p['map']).read_bytes().splitlines()]
                plan=prepared['definition']['verification']['plan'];resources=prepared['definition']['verification']['resources']
                for key in ('epoch','identity'):
                    altered=copy.deepcopy(rows);binding=altered[0]['payload']['resources']['backing'];binding[key]='changed-backing'
                    if key=='identity':binding['aliases'].append('changed-backing')
                    previous='sha256:'+'0'*64;encoded=[]
                    for row in altered:row['previous']=previous;b=canonical(row);encoded.append(b);previous=digest(b)
                    result=probe(a.verify,dict(plan=plan,resources=resources,records=(b'\n'.join(encoded)+b'\n').decode(),image_hex=data.hex()))
                    assert result['outcome']['status']=='refused' and result['outcome']['diagnostic']=='verification_recorded_resources',result
                if bits==12 and not empty:
                    # Explicitly reject logical data relabelled as raw, preserving exact checks.
                    bad=granted(prepared,flags);bad['definition']['schema']='org.disked.verification-worker-definition-prototype/1';bad['definition_digest']=digest(canonical(bad['definition']))
                    fresh=folder/'invalid-verify';fresh.mkdir();bad['definition']['store']['path']=str(fresh)
                    wire('image.verify',bad,(2,3));assert not list(fresh.iterdir())
                    downgraded=copy.deepcopy(collection);downgraded['schema']='org.disked.image-verification-collection-prototype/1'
                    refusal=probe(a.collection,dict(mode='restore',retention_bytes=(canonical(downgraded)+b'\n').decode()),3);assert 'image_collection_version' in refusal['refusal']
                    # Joined public support retains both exact original and historical observation.
                    for index,policy in enumerate(POLICIES):
                        state=folder/('export-'+str(index));state.mkdir();destination=folder/('support-'+str(index)+'.json')
                        params=dict(phase='prepare',case_operation_id=op,case_directory=p['state_directory'],destination=str(destination),state_directory=str(state),collection_path=str(path),collection_digest=digest(body),**{'include_'+k:v for k,v in policy.items()})
                        review=wire('evidence.export',params)['result'];assert not destination.exists() and not list(state.iterdir())
                        first=wire('evidence.export',granted(review,('case_read','collection_read','report_write','store_write','host_effects')),(0,5));finish(first,state,'report')
                        exact=canonical(logical_join(case,collection,policy))+b'\n';assert destination.read_bytes()==exact
                        note('joined-policy',policy=policy,sha256=digest(exact))
                    # Later payload changes cannot turn a historical match into a current match.
                    changed=bytearray(data);changed[0]^=1;Path(p['destination']).write_bytes(changed)
                    q2,prepared2,store2=prepare_verify(folder,p,op,'mismatched-verification');out2,path2,collection2,body2=verification(q2,prepared2,store2)
                    assert collection2['records'][0]['observation']['outcome']['status']=='mismatch'
                    assert path.read_bytes()==body and collection['records'][0]['observation']['outcome']['status']=='matched'
            for frontend in ('gui','tui','shell'):
                folder,p,data,op=prepare_extract();store=folder/'native-verification';store.mkdir()
                q=dict(phase='prepare',case_operation_id=op,case_directory=p['state_directory'],image=p['destination'],map=p['map'],state_directory=str(store))
                review=native(frontend,q,folder);assert review['status']=='completed' and not list(store.iterdir())
                prepared=review['result'];assert prepared['definition']['schema']=='org.disked.verification-worker-definition-prototype/2'
                first=native(frontend,granted(prepared,('case_read','image_read','map_read','store_write','host_effects','private_metadata')),folder)
                out=finish(first,store,'verification');collection=json.loads((store/'verification.collection').read_bytes())
                assert collection['records'][0]['observation']['outcome']['status']=='matched'
                assert collection['records'][0]['observation']['outcome']['matched_bytes']==str(len(data))
                verified.append(dict(frontend=frontend,bytes=len(data),sha256=digest(data),operation_id=op))
            passed=True
    finally:
        a.output.write_text(json.dumps(dict(passed=passed,checks=len(records),records=records,verified_files=verified,scope='Logical FAT recorded cases, independent destination/map verification and exact historical joined support; no original-source authentication'),indent=2)+'\n',encoding='utf-8',newline='\n')
    assert passed

if __name__=='__main__':main()
