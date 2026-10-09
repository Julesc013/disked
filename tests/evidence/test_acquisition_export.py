"""Joint case/resource/effect qualification using generated owned files.

Pure late-source/effect observations are synthetic and labeled. Native fixture
events coordinate the same process; unfinished dependencies remain on failure.
No physical storage, elevation, customer data, publication or timeout restart.
"""
import argparse,copy,ctypes as C,itertools,json,os,queue,subprocess,sys,threading,time
from ctypes import wintypes as W
from pathlib import Path
from test_case import encode,digest,policy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,source_bytes,map_check,history_check,fixture_directory,owned_process,K

def main():
    p=argparse.ArgumentParser()
    for name in ('probe','fault','product'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--evidence',type=Path);a=p.parse_args()
    root=a.root.resolve();probe=a.probe.resolve();fault=a.fault.resolve();product=a.product.resolve()
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_REPORT_','DISKED_ACQ_','DISKED_TEST_'))}
    sys.path.insert(0,str(root/'spec/tools'));from specctl import Bundle,SpecError
    bundle=Bundle(root/'spec');observations=[];copies=[];exports=[]
    def check(name,value,**extra):assert value,(name,extra);observations.append(dict(name=name,passed=True,**extra))
    def validate(value,kind):bundle.validate('urn:disked:schema:acquisition-case-export-'+kind+':1',value)
    def call(value,refusal=None,exe=probe):
        r=subprocess.run([str(exe)],input=canonical(value),capture_output=True,cwd=root,env=env,timeout=15)
        out=json.loads(r.stdout);assert not r.stderr
        if refusal:assert r.returncode==3 and refusal in out['refusal'],(r.returncode,out)
        else:
            assert r.returncode==0 and 'refusal' not in out,(r.returncode,out)
            validate(out['definition'],'definition');assert out['definition_digest']==digest(encode(out['definition']))
            if 'outcome' in out:validate(out['outcome'],'outcome')
        observations.append(dict(name='joint-refusal' if refusal else 'joint-result',input_kind='synthetic-model' if value['mode']=='model' else 'native-ordinary-files',passed=True,exit_code=r.returncode,output_sha256=digest(r.stdout)))
        return out
    def grant(hash='$prepared',**overrides):return dict(definition_digest=hash,case_read=True,report_write=True,host_effects=True,**overrides)
    def cli(args):
        r=subprocess.run([str(product),'--json',*args],capture_output=True,cwd=root,env=env,timeout=15)
        assert r.returncode in (0,5) and not r.stderr,(r.returncode,r.stdout,r.stderr);return json.loads(r.stdout)
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    K.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,W.LPVOID,W.DWORD,W.DWORD,W.HANDLE];K.CreateFileW.restype=W.HANDLE
    K.GetFileTime.argtypes=[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)]
    K.SetFileTime.argtypes=[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)]
    with fixture_directory(scratch) as owned:
        folder=owned/'owned';folder.mkdir();state_dir=folder/'state';state_dir.mkdir()
        src=folder/'generated-source.img';dst=folder/'generated-copy.img';mapping=folder/'generated-copy.map'
        expected=source_bytes(262145);src.write_bytes(expected)
        prepared=cli(['image','acquire','prepare',str(src),str(dst),'--map',str(mapping),'--state-dir',str(state_dir)])['result']
        first=cli(['image','acquire','execute','--definition-json',canonical(prepared['definition']).decode(),'--definition-digest',prepared['definition_digest'],
            '--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects'])
        end=time.monotonic()+30
        while True:
            state=cli(['operation','inspect',first['operation_id'],'--state-dir',str(state_dir)])['result']['state']
            if state['phase']=='finished':break
            assert time.monotonic()<end,('retain unfinished acquisition',state);time.sleep(.02)
        handle=owned_process(state,str(product))
        if handle:
            try:assert K.WaitForSingleObject(handle,3000)==0
            finally:K.CloseHandle(handle)
        check('actual-generated-acquisition',state['quiescent'] and state['outcome']['status']=='completed' and src.read_bytes()==dst.read_bytes()==expected)
        map_check(mapping,expected);copies.append(dict(bytes=str(len(expected)),sha256=digest(expected),operation_id=first['operation_id']))
        header=json.loads((state_dir/'acquisition.request').read_bytes());raw=(state_dir/'acquisition.records').read_text(encoding='utf-8');history_check(state_dir/'acquisition.records')
        base=dict(mode='prepare',operation_id=first['operation_id'],state_directory=str(state_dir),policy=policy(),destination=str(folder/'support.json'))
        before={f.name:f.read_bytes() for f in state_dir.iterdir() if f.is_file()};review=call(base);definition=review['definition']
        check('prepare-read-only',not Path(base['destination']).exists() and before=={f.name:f.read_bytes() for f in state_dir.iterdir() if f.is_file()})
        check('exact-joint-case-source',definition['case']['revision']==definition['source']['case_revision'] and definition['case']['operation_id']==first['operation_id'])
        digests=set()
        for flags in itertools.product((False,True),repeat=4):
            item=call(dict(base,policy=policy(flags)));digests.add(item['definition_digest'])
            check('native-policy-bound',item['definition']['effect']['artifact']['policy']==policy(flags),flags=flags)
        check('all-policy-definitions-distinct',len(digests)==16)
        model=dict(mode='model',header=header,records=raw,policy=policy(),source=definition['source'],resources=definition['effect']['resources'],grant=grant())
        success=call(model);check('native-model-definition-agrees',success['definition']==definition and success['definition_digest']==review['definition_digest'])
        check('model-selected-output-verifies',success['outcome']['status']=='completed' and success['output_bytes']==success['artifact_bytes'] and digest(success['output_bytes'].encode())==definition['effect']['artifact']['digest'])
        for change,refusal in [
            (lambda x:x['source'].update(case_revision='sha256:'+'0'*64),'case_export_source_binding'),
            (lambda x:x['source']['files'][1].update(digest='sha256:'+'0'*64),'case_export_source_binding'),
            (lambda x:x['source']['files'][1]['metadata'].update(bytes='1'),'case_export_source_binding'),
            (lambda x:x['source']['files'][0]['metadata'].update(attributes='4096'),'case_export_file_profile'),
            (lambda x:x['source'].update(authenticity='established'),'case_export_source_profile'),
            (lambda x:x['source']['ancestors'][-1].update(created='1'),'case_export_ancestors'),
            (lambda x:x['source']['files'][0]['metadata'].update(created='18446744073709551616'),'case_export_integer'),
            (lambda x:x['resources']['destination'].update(location=x['resources']['producer']['location']),'export_alias')]:
            bad=copy.deepcopy(model);change(bad);call(bad,refusal)
        for flags in itertools.product((False,True),repeat=3):
            if all(flags):continue
            selected=grant();selected.update(zip(('case_read','report_write','host_effects'),flags));value=call(dict(model,grant=selected))
            check('denied-grant-no-ports',value['outcome']['status']=='refused' and value['source_observations']=='0' and value['effect_calls']=='0' and not value['created'],flags=flags)
        value=call(dict(model,grant=grant('sha256:'+'0'*64)));check('wrong-joint-digest-no-ports',value['source_observations']=='0' and value['effect_calls']=='0')
        for name in ('source-before','source-before-create','source-after-create','source-after-write','source-after-output','source-unobserved','executor-throws-before','executor-throws-after'):
            value=call(dict(model,fault=name));out=value['outcome'];output=out['output']
            check('modeled-joint-effect-state',out['status']!='completed',fault=name)
            if name in ('source-before','source-before-create','source-unobserved'):
                check('modeled-no-creation',not value['created'] and output['output_state']=='not_created',fault=name)
            if name=='source-after-create':check('modeled-created-file-retained',value['created'] and output['output_state']=='created' and output['uncertain_effect'])
            if name=='source-after-write':check('modeled-written-bytes-retained',value['output_bytes']==value['artifact_bytes'] and output['written_bytes']==str(len(value['output_bytes'].encode())))
            if name=='source-after-output':
                check('late-source-does-not-erase-output',out['status']=='failed' and out['source_state']=='changed' and output['status']=='completed' and not output['uncertain_effect'] and output['verified_bytes']==definition['effect']['artifact']['bytes'])
            if name.startswith('executor-throws'):
                check('unobserved-effect-not-no-effect',out['status']=='unknown' and output['output_state']=='uncertain' and output['written_bytes'] is None and output['uncertain_effect'],fault=name)
        # Schema semantics dispatch automatically; deliberately contradictory
        # records must be rejected without an optional caller selector.
        for kind,change in [('definition',lambda x:x['case'].update(revision='sha256:'+'0'*64)),
            ('definition',lambda x:x['source']['ancestors'][-1].update(created='1')),
            ('definition',lambda x:x['source']['files'][0]['metadata'].update(bytes='18446744073709551616')),
            ('definition',lambda x:x['effect']['artifact'].update(bytes='1048578')),
            ('outcome',lambda x:x.update(source_state='changed')),
            ('outcome',lambda x:x['output'].update(verified_bytes='1')),
            ('outcome',lambda x:x['output'].update(submitted_bytes='0',written_bytes='0',read_bytes='0',verified_bytes='0'))]:
            bad=copy.deepcopy(definition if kind=='definition' else success['outcome']);change(bad)
            try:validate(bad,kind);raise AssertionError('contradictory schema passed')
            except SpecError:check('automatic-schema-relationship-refusal',True,kind=kind)
        # Supplied execute authority is checked before reconstruction. A false
        # grant with a nonexistent selector refuses the grant, not a file open.
        phantom=copy.deepcopy(definition);phantom['source']['store']['path']=str(folder/'absent-source')
        denied=grant(digest(encode(phantom)));denied['case_read']=False
        call(dict(mode='execute',definition=phantom,grant=denied),'case_export_grant')
        # Edited authoritative inputs/different policy cannot silently reuse
        # the old review. Restore bytes; metadata changes still invalidate it.
        altered=copy.deepcopy(definition);altered['effect']['artifact']['policy']['raw_values']=True
        call(dict(mode='execute',definition=altered,grant=grant(digest(encode(altered)))),'case_export_reviewed_definition_changed')
        history_file=state_dir/'acquisition.records';original=history_file.read_bytes();history_file.write_bytes(original+b'{"partial":')
        call(dict(mode='execute',definition=definition,grant=grant(review['definition_digest'])),'case_export_reviewed_definition_changed')
        history_file.write_bytes(original)
        call(dict(mode='execute',definition=definition,grant=grant(review['definition_digest'])),'case_export_reviewed_definition_changed')
        check('changed-history-no-output',not Path(base['destination']).exists())
        refreshed=call(base);completed=call(dict(mode='execute',definition=refreshed['definition'],grant=grant(refreshed['definition_digest']),second_call=True))
        body=Path(base['destination']).read_bytes();desc=refreshed['definition']['effect']['artifact'];out=completed['outcome']
        check('actual-joint-export-completed',out['status']=='completed' and out['source_state']=='matched' and out['output']['status']=='completed')
        check('actual-selected-bytes-hash',body==encode(json.loads(body))+b'\n' and len(body)==int(desc['bytes']) and digest(body)==desc['digest'])
        check('actual-output-receipt-retained',completed['receipt']['output_receipt']['output_created_observed'] and completed['receipt']['output_receipt']['artifact_digest']==desc['digest'])
        check('native-session-one-execution',completed['second_call_refusal']=='case_export_session_used')
        exports.append(dict(bytes=str(len(body)),sha256=digest(body),kind='completed-selected-artifact'))
        call(dict(mode='execute',definition=refreshed['definition'],grant=grant(refreshed['definition_digest'])),'export_output_exists')
        check('existing-output-not-clobbered',Path(base['destination']).read_bytes()==body)
        cancelled=call(dict(base,mode='execute',destination=str(folder/'cancel-before.json'),grant=grant(),cancel_before=True))
        check('native-cancel-before-no-output',cancelled['outcome']['status']=='cancelled' and cancelled['outcome']['output']['output_state']=='not_created' and not (folder/'cancel-before.json').exists())
        # Coordinate actual source generation changes in the same live native
        # fault child before preparation, after CREATE_NEW and after readback.
        events=[]
        for phase in ('prepared','created','read'):
            output=folder/(phase+'.json');release=folder/(phase+'.release')
            request=dict(base,mode='execute',destination=str(output),grant=grant())
            selected=dict(env,DISKED_REPORT_TEST_EVENT=phase,DISKED_REPORT_TEST_PAUSE='1',DISKED_REPORT_TEST_RELEASE_FILE=str(release))
            metadata=K.CreateFileW(str(state_dir/'acquisition.request'),0x100,7,None,3,0x200000,None)
            assert metadata and metadata!=W.HANDLE(-1).value,C.get_last_error()
            original_time=W.FILETIME();assert K.GetFileTime(metadata,C.byref(original_time),None,None)
            stamp_value=(original_time.dwHighDateTime<<32|original_time.dwLowDateTime)+10000000
            stamp=W.FILETIME(stamp_value&0xffffffff,stamp_value>>32)
            child=subprocess.Popen([str(fault)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=selected)
            child.stdin.write(canonical(request));child.stdin.close();child.stdin=None
            messages=queue.Queue();threading.Thread(target=lambda:messages.put(child.stdout.readline()),daemon=True).start()
            event=json.loads(messages.get(timeout=12));assert event==dict(event=phase) and child.poll() is None
            try:
                assert K.SetFileTime(metadata,C.byref(stamp),None,None);actual=W.FILETIME()
                assert K.GetFileTime(metadata,C.byref(actual),None,None) and (actual.dwLowDateTime,actual.dwHighDateTime)==(stamp.dwLowDateTime,stamp.dwHighDateTime)
                release.write_bytes(b'release');stdout,stderr=child.communicate(timeout=15);value=json.loads(stdout);assert not stderr
                if phase=='prepared':check('actual-generation-before-prepare-refusal',child.returncode==3 and value['refusal']=='case_source_changed' and not output.exists())
                else:
                    assert child.returncode==0;validate(value['outcome'],'outcome')
                    check('actual-generation-after-effect-retained',value['outcome']['status']=='failed' and value['outcome']['output']['output_state']=='created' and value['receipt']['output_receipt']['output_created_observed'] and output.exists(),phase=phase)
                    retained=output.read_bytes();check('actual-source-change-output-bytes',retained==(b'' if phase=='created' else body),phase=phase)
                    exports.append(dict(bytes=str(len(retained)),sha256=digest(retained),kind='retained-failed-'+phase))
                events.append(dict(phase=phase,pid=str(child.pid),exit_code=child.returncode,output_created=output.exists()))
            finally:
                assert K.SetFileTime(metadata,C.byref(original_time),None,None);K.CloseHandle(metadata)
        check('original-source-copy-preserved',src.read_bytes()==dst.read_bytes()==expected);map_check(mapping,expected)
        sample=dict(definition=refreshed['definition'],definition_digest=refreshed['definition_digest'],outcome=completed['outcome'],receipt=completed['receipt'],
            artifact_bytes=body.decode(),scope='generated-private-review/receipt; artifact_bytes alone is consent-selected support')
    result=dict(passed=True,checks=len(observations),observations=observations,actual_acquisition_copies=copies,actual_exports=exports,native_events=events,sample=sample,
        limitations=['Owned ordinary files on the recorded Windows host only; pure late-source/executor faults are synthetic.',
            'Synchronous source/effect checks are observations, not atomic resources, authenticated actor/custody or current image validation.',
            'Public worker/store/command/service/cancellation/late-result and all frontend admission remain pending; full DE-W034 and 0.1.0 incomplete.'])
    if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS joint acquisition export:',len(observations),'checks;',len(copies),'actual verified acquisition;',len(exports),'actual completed/retained outputs')
if __name__=='__main__':main()
