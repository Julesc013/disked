"""Actual owned-file case inputs, independent policy/hash checks and source guards.

Synthetic alterations are sent only to the private pure-model probe. Native
fixtures retain their exact worker metadata and dependencies on every failure.
"""
import argparse,copy,ctypes as C,itertools,json,os,queue,subprocess,sys,threading,time
from ctypes import wintypes as W
from pathlib import Path
from test_case import encode,digest,policy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,source_bytes,map_check,history_check,fixture_directory,owned_process,K

def main():
    p=argparse.ArgumentParser()
    for name in ('probe','product','worker-fault'):p.add_argument('--'+name,required=True,type=Path)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--evidence',type=Path);a=p.parse_args()
    root=a.root.resolve();probe=a.probe.resolve();product=a.product.resolve();fault=a.worker_fault.resolve()
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_ACQ_','DISKED_TEST_'))}
    K.CreateFileW.argtypes=[W.LPCWSTR,W.DWORD,W.DWORD,W.LPVOID,W.DWORD,W.DWORD,W.HANDLE];K.CreateFileW.restype=W.HANDLE
    observations=[];copies=[];scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    def check(name,value,**extra):
        assert value,(name,extra);observations.append(dict(name=name,passed=True,**extra))
    def call(value,refusal=None):
        result=subprocess.run([str(probe)],input=canonical(value),capture_output=True,cwd=root,env=env,timeout=15)
        out=json.loads(result.stdout);assert not result.stderr
        if refusal is None:assert result.returncode==0 and 'refusal' not in out,(result.returncode,out)
        else:assert result.returncode==3 and refusal in out['refusal'],out
        kind='synthetic-model-input' if 'header' in value else 'ordinary-file-input'
        observations.append(dict(name='case-refusal' if refusal else 'case-result',input_kind=kind,exit_code=result.returncode,output_sha256=digest(result.stdout),passed=True));return out
    def cli(args):
        result=subprocess.run([str(product),'--json',*args],capture_output=True,cwd=root,env=env,timeout=15)
        assert result.returncode in (0,5) and not result.stderr,(result.returncode,result.stdout,result.stderr)
        return json.loads(result.stdout)
    def finish(first,state_dir,exe):
        end=time.monotonic()+30
        while True:
            value=cli(['operation','inspect',first['operation_id'],'--state-dir',str(state_dir)])
            state=value['result']['state']
            if state['phase']=='finished':break
            assert time.monotonic()<end,('retain unfinished worker dependencies',state);time.sleep(.02)
        handle=owned_process(state,str(exe))
        if handle:
            try:assert K.WaitForSingleObject(handle,3000)==0
            finally:K.CloseHandle(handle)
        assert state['outcome']['status']=='completed' and state['quiescent'];return state
    def model(header,records,selected=None):return dict(header=header,records=records,policy=policy() if selected is None else selected)
    def rebound(h,rows):
        h['definition_digest']=digest(encode(h['definition']));h['grant']['definition_digest']=h['definition_digest']
        previous='0'*64
        for sequence,row in enumerate(rows,1):
            row['state']['sequence']=str(sequence)
            row['state']['binding']['definition_digest']=h['definition_digest'];row['previous']=previous;row.pop('digest',None)
            previous=digest(encode(row))[7:];row['digest']=previous
        return b''.join(encode(row)+b'\n' for row in rows).decode()
    with fixture_directory(scratch) as owned:
        folder=owned/'owned';folder.mkdir();state_dir=folder/'state';state_dir.mkdir()
        src=folder/'OWNED-CUSTOMER-SOURCE.img';dst=folder/'OWNED-CUSTOMER-COPY.img';mapping=folder/'OWNED-CUSTOMER-MAP.map'
        expected=source_bytes(262145);src.write_bytes(expected)
        review=cli(['image','acquire','prepare',str(src),str(dst),'--map',str(mapping),'--state-dir',str(state_dir)])['result']
        first=cli(['image','acquire','execute','--definition-json',canonical(review['definition']).decode(),'--definition-digest',review['definition_digest'],
            '--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects'])
        finish(first,state_dir,product)
        check('actual-source-copy-map',src.read_bytes()==dst.read_bytes()==expected);map_check(mapping,expected)
        copies.append(dict(bytes=str(len(expected)),sha256=digest(expected),operation_id=first['operation_id']))
        header=json.loads((state_dir/'acquisition.request').read_bytes());raw=(state_dir/'acquisition.records').read_text(encoding='utf-8');rows=history_check(state_dir/'acquisition.records')
        native=dict(operation_id=first['operation_id'],state_directory=str(state_dir),policy=policy())
        out=call(native);view=out['case'];revision=out['case_revision']
        check('exact-case-revision',revision==digest(encode(view))==out['revision_after_view_edit'])
        check('exact-before-after',view['before']==header and view['records']==rows and view['after']==rows[-1]['state'])
        check('exact-history-bytes',view['history']['raw_digest']==digest(raw.encode()) and view['history']['bytes']==str(len(raw.encode())))
        check('native-source-binding',out['source_binding']['case_revision']==revision and out['source_binding']['access']=='read')
        check('missing-configuration-not-invented',view['code_identity']['configuration_digest'] is None)
        originals=[revision,header['definition_digest'],header['definition']['plan']['capture_epoch'],digest(raw.encode())]+['sha256:'+r['digest'] for r in rows]
        sentinel='OWNED-SECRET-DO-NOT-EXPORT';altered=copy.deepcopy(rows);altered[-1]['state']['receipt']['untrusted_extra']=sentinel
        altered[-1]['state']['outcome']['diagnostic']=sentinel;altered_header=copy.deepcopy(header);altered_raw=rebound(altered_header,altered)
        for flags in itertools.product((False,True),repeat=4):
            selected=policy(flags);item=call(model(altered_header,altered_raw,selected));body=item['artifact_bytes'].encode();support=json.loads(body)
            check('all-policy-artifact',body==encode(support)+b'\n' and digest(body)==item['artifact']['digest'] and len(body)==int(item['artifact']['bytes']),flags=flags)
            check('no-secret-or-original-bindings',sentinel.encode() not in body and not any(x.encode() in body for x in originals) and item['case_revision'].encode() not in body,flags=flags)
            paths=all(flags[i] for i in (0,1,3))
            check('path-category-and-content-gates',('declared_paths' in support)==paths and (b'OWNED-CUSTOMER-' in body)==paths,flags=flags)
            check('recorded-counters-gate',('checkpoint_bytes' in support['after'])==flags[1] and ('operation_id' in support)==flags[0],flags=flags)
            check('claims-not-promoted',support['claims']==view['claims'] and support['claims']['current_image_verification']=='not_performed' and not support['claims']['physical_admission'])
        full=call(model(header,raw,policy((True,True,True,True))))
        check('recorded-counts-match-actual',json.loads(full['artifact_bytes'])['after']['checkpoint_bytes']==str(len(expected)))
        pure=call(model(header,raw));check('native-and-pure-content-identical',pure['case_revision']==revision and pure['artifact_bytes']==out['artifact_bytes'])
        h=copy.deepcopy(header);h['definition']['request']['source']='Z:\\DECLARED-ONLY\\磁\x1b[31m.txt';changed_rows=copy.deepcopy(rows)
        changed_raw=rebound(h,changed_rows)
        escaped=call(model(h,changed_raw,policy((True,True,True,True))))
        check('declared-paths-are-lossless-data',json.loads(escaped['artifact_bytes'])['declared_paths']['source']==h['definition']['request']['source'] and '\x1b' not in escaped['artifact_bytes'])
        hidden=call(model(h,changed_raw));check('declared-paths-default-omitted','DECLARED-ONLY' not in hidden['artifact_bytes'])
        report_path=folder/'support.json';exported=call(dict(native,destination=str(report_path)))
        check('actual-typed-file-export',exported['export_outcome']['status']=='completed' and exported['source_revalidation']=='passed' and report_path.read_bytes()==out['artifact_bytes'].encode())
        check('report-does-not-promote-source',exported['export_outcome']['physical_backing_qualified'] is False and exported['case']['claims']==view['claims'])
        original_files={f.name:f.read_bytes() for f in state_dir.iterdir() if f.is_file()}
        call(dict(native,operation_id='image-op:'+'0'*32),'case_source_binding')
        check('native-reads-create-nothing',original_files=={f.name:f.read_bytes() for f in state_dir.iterdir() if f.is_file()})
        copied_state=owned/'copied-state';copied_state.mkdir()
        for name in ('acquisition.request','acquisition.records'):(copied_state/name).write_bytes(original_files[name])
        call(dict(native,state_directory=str(copied_state)),'case_source_binding')
        check('copied-bytes-do-not-invent-store-continuity',len(list(copied_state.iterdir()))==2)
        (copied_state/'acquisition.records').write_bytes(b'x'*1048577)
        call(dict(native,state_directory=str(copied_state)),'operation_history_limit')
        # Real pin ownership: byte writes and rename fail while this exact reader
        # process is alive. Release, wait for that same process and verify bytes.
        child=subprocess.Popen([str(probe),'--hold'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env)
        child.stdin.write(canonical(native)+b'\n');child.stdin.flush();messages=queue.Queue()
        threading.Thread(target=lambda:messages.put(child.stdout.readline()),daemon=True).start()
        held=json.loads(messages.get(timeout=12));assert held['event']=='case-held' and int(held['pid'])==child.pid and child.poll() is None
        for target in (state_dir,state_dir/'acquisition.request',state_dir/'acquisition.records'):
            try:target.rename(target.with_name(target.name+'-moved'));raise AssertionError('live case rename succeeded')
            except PermissionError as error:check('live-native-rename-refused',error.winerror in (5,32),target=target.name)
        write=K.CreateFileW(str(state_dir/'acquisition.records'),0x40000000,7,None,3,0x200000,None)
        error=C.get_last_error()
        if write and write!=W.HANDLE(-1).value:K.CloseHandle(write);raise AssertionError('live byte-write access succeeded')
        check('live-native-byte-write-refused',error in (5,32),platform_code=error)
        child.stdin.write(b'x\n');child.stdin.flush();child.stdin.close();child.stdin=None
        stdout,stderr=child.communicate(timeout=15);check('same-reader-terminal',child.returncode==0 and not stderr and json.loads(stdout)['case_revision']==revision)
        check('reader-pins-preserved-bytes',original_files=={f.name:f.read_bytes() for f in state_dir.iterdir() if f.is_file()})

        # Metadata-only access can change a held file's creation time. Perform
        # that real change, require revalidation to refuse before artifact/file
        # output, release the same reader and restore the exact original stamp.
        K.GetFileTime.argtypes=[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)]
        K.SetFileTime.argtypes=[W.HANDLE,C.POINTER(W.FILETIME),C.POINTER(W.FILETIME),C.POINTER(W.FILETIME)]
        for name in ('acquisition.request','acquisition.records'):
            target=state_dir/name;assert target.resolve().is_relative_to(owned)
            metadata=K.CreateFileW(str(target),0x100,7,None,3,0x200000,None);assert metadata and metadata!=W.HANDLE(-1).value,C.get_last_error()
            original=W.FILETIME();assert K.GetFileTime(metadata,C.byref(original),None,None)
            changed=(original.dwHighDateTime<<32 | original.dwLowDateTime)+10000000
            stamp=W.FILETIME(changed&0xffffffff,changed>>32)
            child=subprocess.Popen([str(probe),'--hold'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env)
            child.stdin.write(canonical(dict(native,destination=str(folder/(name+'.must-not-exist'))))+b'\n');child.stdin.flush();messages=queue.Queue()
            threading.Thread(target=lambda:messages.put(child.stdout.readline()),daemon=True).start()
            held=json.loads(messages.get(timeout=12));assert int(held['pid'])==child.pid and child.poll() is None
            try:
                assert K.SetFileTime(metadata,C.byref(stamp),None,None),C.get_last_error()
                actual=W.FILETIME();assert K.GetFileTime(metadata,C.byref(actual),None,None) and (actual.dwLowDateTime,actual.dwHighDateTime)==(stamp.dwLowDateTime,stamp.dwHighDateTime)
                child.stdin.write(b'x\n');child.stdin.flush();child.stdin.close();child.stdin=None
                stdout,stderr=child.communicate(timeout=15);value=json.loads(stdout)
                check('actual-file-generation-change-refused',child.returncode==3 and not stderr and value['refusal']=='case_source_changed' and not (folder/(name+'.must-not-exist')).exists(),target=name)
            finally:
                assert K.SetFileTime(metadata,C.byref(original),None,None);K.CloseHandle(metadata)

        # Synthetic bounded histories retain valid prefixes, but cannot invent
        # an after record when active/torn, even if a complete terminal preceded
        # an unexplained suffix. Suffix bytes enter the private revision only.
        active=encode(rows[0]).decode()+'\n';open_case=call(model(header,active))
        check('open-history-no-after',open_case['case']['collection_state']=='open' and open_case['case']['after'] is None)
        torn=call(model(header,raw+'{"untrusted":"'+sentinel))
        check('torn-terminal-history-unresolved',torn['case']['collection_state']=='unresolved' and torn['case']['after'] is None and torn['case_revision']!=revision and sentinel not in torn['artifact_bytes'])
        for key,value,reason in [('schema','unknown','acquisition_case_version'),('operation_id','image-op:'+'A'*32,'acquisition_case_identity'),('definition_digest','sha256:'+'0'*64,'acquisition_case_definition_digest'),('records_id','x:y','acquisition_case_identity')]:
            h=copy.deepcopy(header);h[key]=value;call(model(h,raw),reason)
        h=copy.deepcopy(header);h['unexpected']=True;call(model(h,raw),'acquisition_case_shape')
        h=copy.deepcopy(header);h['grant']['host_effects']=False;call(model(h,raw),'acquisition_case_grant')
        for key,value in [('chunk_bytes','32768'),('retry_limit','1'),('read_policy','conservative'),('substitution','zero')]:
            h=copy.deepcopy(header);h['definition']['request'][key]=value;call(model(h,raw),'acquisition_case_request_plan')
        corrupt=copy.deepcopy(rows);corrupt[0]['digest']='0'*64;call(model(header,b''.join(encode(r)+b'\n' for r in corrupt).decode()),'history_chain')
        h=copy.deepcopy(header);call(model(h,rebound(h,copy.deepcopy(rows[1:]))),'acquisition_case_missing_start')
        h=copy.deepcopy(header);last=copy.deepcopy(rows[-1]);last['state']['sequence']=str(len(rows)+1);extra=copy.deepcopy(rows)+[last]
        call(model(h,rebound(h,extra)),'history_order')
        call(model(header,'\n'),'invalid_json')
        call(model(header,'x'*1048577),'string_limit_exceeded')
        for selected in ({},{**policy(),'unknown':False},{**policy(),'identifiers':'yes'}):call(model(header,raw,selected),'acquisition_case_shape')

        # A real writer with a controlled admission delay still owns the record
        # handle. Incompatible case reads refuse, then the same worker completes.
        busy=owned/'busy';busy.mkdir();busy_state=busy/'state';busy_state.mkdir();busy_source=busy/'source.img';busy_source.write_bytes(source_bytes(65537))
        def worker(v,injected=False):
            selected=dict(env)
            if injected:selected['DISKED_ACQ_WORKER_TEST_ADMISSION_DELAY']='1'
            r=subprocess.run([str(fault)],input=canonical(v),capture_output=True,cwd=root,env=selected,timeout=15)
            assert r.returncode==0 and not r.stderr,(r.returncode,r.stdout,r.stderr);return json.loads(r.stdout)
        prepared=worker(dict(mode='prepare',source=str(busy_source),destination=str(busy/'copy.img'),map=str(busy/'copy.map'),state_directory=str(busy_state)))
        grant=dict(definition_digest=prepared['definition_digest'],source_read=True,destination_write=True,map_write=True,host_effects=True)
        running=worker(dict(mode='start',definition=prepared['definition'],grant=grant),True)
        state=json.loads((busy_state/'acquisition.records').read_bytes().splitlines()[0])['state'];h=owned_process(state,str(fault));assert h
        try:assert K.WaitForSingleObject(h,0)==258
        finally:K.CloseHandle(h)
        check('live-writer-refusal',call(dict(operation_id=running['operation_id'],state_directory=str(busy_state),policy=policy()),'case_source_history_unavailable')['platform_code']=='32')
        finish(running,busy_state,fault);data=busy_source.read_bytes();assert data==(busy/'copy.img').read_bytes();map_check(busy/'copy.map',data)
        copies.append(dict(bytes=str(len(data)),sha256=digest(data),operation_id=running['operation_id']))
        final=call(dict(operation_id=running['operation_id'],state_directory=str(busy_state),policy=policy()))
        check('same-writer-closed-case',final['case']['collection_state']=='closed' and final['case']['claims']['worker_exit']=='not_observed_by_this_case')
    result=dict(passed=True,checks=len(observations),observations=observations,actual_acquisition_copies=copies,
        sample=dict(case=view,case_revision=revision,source_binding=out['source_binding'],artifact=out['artifact'],
            artifact_bytes=out['artifact_bytes'],export_outcome=exported['export_outcome'],export_receipt=exported['export_receipt'],
            scope='generated-owned-fixture-private-envelope; artifact_bytes alone is selected support content'),
        limits=['Owned ordinary files only; no physical, actor authentication, current-image verification by case or power-loss qualification.',
            'Pure-model alterations are synthetic. The actual live-writer delay is a separate controlled fault seam.',
            'Public evidence.export admission and bounded shared-service/frontend parity remain pending.'])
    if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('PASS acquisition case:',len(observations),'checks;',len(copies),'actual byte/map-verified acquisitions')
if __name__=='__main__':main()
