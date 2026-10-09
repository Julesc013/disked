"""Owned native report workers and independent bounded-history checks.

Delays and store failures are compiled only into the separate fault executable.
Generated acquisition metadata is selected; source/copy/map paths are not opened
by the report worker. No physical media, elevation, restart or assumed exit.
"""
import argparse,copy,ctypes as C,hashlib,itertools,json,os,subprocess,sys,time
from ctypes import wintypes as W
from pathlib import Path
from test_case import policy
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,digest,source_bytes,map_check,fixture_directory,owned_process,JobLimits,K

def report_process(state,executable):
    # A failed final record leaves phase executing even when the same process
    # exits. Verify its actual creation identity; never edit the recorded phase.
    binding=state['binding'];handle=K.OpenProcess(0x1000|0x100000,False,int(binding['process_id']))
    if not handle:assert C.get_last_error()==87,C.get_last_error();return None
    try:
        stamps=[W.FILETIME() for _ in range(4)];assert K.GetProcessTimes(handle,*map(C.byref,stamps))
        assert stamps[0].dwHighDateTime*2**32+stamps[0].dwLowDateTime==int(binding['process_created'])
        path=C.create_unicode_buffer(1024);length=W.DWORD(1024)
        if K.QueryFullProcessImageNameW(handle,0,path,C.byref(length)):assert Path(path.value).resolve()==executable.resolve()
        else:assert K.WaitForSingleObject(handle,0)==0,('unavailable live process identity',binding)
        return handle
    except BaseException:K.CloseHandle(handle);raise

def history_check(path,header):
    raw=path.read_bytes();assert raw.endswith(b'\n') and len(raw)<=1048576
    previous='0'*64;binding=None;rows=[]
    for sequence,body in enumerate(raw.splitlines(),1):
        assert len(body)<=65536 and sequence<=16;row=json.loads(body);assert canonical(row)==body
        assert row['schema']=='org.disked.report-worker-record-prototype/1' and row['previous']==previous
        unsigned=copy.deepcopy(row);previous=unsigned.pop('digest');assert hashlib.sha256(canonical(unsigned)).hexdigest()==previous
        state=row['state'];assert state['sequence']==str(sequence) and int(state['observed_filetime'])>0
        b=state['binding'];assert b['definition_digest']==header['definition_digest']
        for name in ('operation_id','attempt_id','worker_epoch'):assert b[name]==header[name]
        assert b['image_digest']==header['definition']['image_digest'] and b['host_id']==header['definition']['host_id']
        assert 0<int(b['process_id'])<2**32 and 0<int(b['process_created'])<2**64
        if binding is None:binding=b
        assert binding==b
        if rows:assert rows[-1]['state']['phase']!='finished'
        rows.append(row)
    assert rows and rows[0]['state']['phase']=='prepared';return raw,rows

def main():
    p=argparse.ArgumentParser()
    for name in ('probe','fault','product'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--root',type=Path,default=Path('.'));p.add_argument('--evidence',type=Path);a=p.parse_args()
    root=a.root.resolve();probe=a.probe.resolve();fault=a.fault.resolve();product=a.product.resolve()
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_REPORT_','DISKED_ACQ_','DISKED_TEST_'))}
    observations=[];samples=[];outputs=[]
    sys.path.insert(0,str(root/'spec/tools'));from specctl import Bundle,SpecError
    bundle=Bundle(root/'spec')
    def check(name,value,**extra):assert value,(name,extra);observations.append(dict(name=name,passed=True,**extra))
    def call(value,exe=probe,extra=None,refusal=None,retain=True):
        result=subprocess.run([str(exe)],input=canonical(value),capture_output=True,cwd=root,env=dict(env,**(extra or {})),timeout=12)
        assert result.returncode==(3 if refusal else 0) and not result.stderr,(result.returncode,result.stdout,result.stderr)
        out=json.loads(result.stdout)
        if refusal:assert refusal in out['refusal'],out
        if 'definition' in out:
            bundle.validate('urn:disked:schema:report-worker-definition:1',out['definition'])
            assert out['definition_digest']==digest(canonical(out['definition']))
        if retain:observations.append(dict(name='native-refusal' if refusal else 'native-result',mode=value['mode'],exe_sha256=digest(exe.read_bytes()),output_sha256=digest(result.stdout),passed=True))
        return out
    def cli(args):
        result=subprocess.run([str(product),'--json',*args],capture_output=True,cwd=root,env=env,timeout=15)
        assert result.returncode in (0,5) and not result.stderr,(result.returncode,result.stdout,result.stderr);return json.loads(result.stdout)
    def grant(d,**changes):
        value=dict(definition_digest=d['definition_digest'],case_read=True,report_write=True,store_write=True,host_effects=True);value.update(changes);return value
    def request(d,g=None):return dict(mode='start',definition=d['definition'],grant=g or grant(d))
    def wait(id,store,exe,terminal=True):
        end=time.monotonic()+20;last=None
        while time.monotonic()<end:
            last=call(dict(mode='inspect',operation_id=id,state_directory=str(store)),exe,retain=False)
            state=last.get('value',{}).get('state')
            if state and ((terminal and state['phase']=='finished') or (not terminal and last['value'].get('worker_observation')!='running')):
                handle=report_process(state,exe)
                if handle:
                    try:assert K.WaitForSingleObject(handle,3000)==0,('retain unfinished report worker',state)
                    finally:K.CloseHandle(handle)
                return last
            time.sleep(.025)
        raise AssertionError(('retain incomplete worker/store',last))
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        source_dir=owned/'case';source_dir.mkdir();case_store=source_dir/'state';case_store.mkdir()
        src=source_dir/'generated.img';dst=source_dir/'copy.img';mapping=source_dir/'copy.map';expected=source_bytes(262145);src.write_bytes(expected)
        d=cli(['image','acquire','prepare',str(src),str(dst),'--map',str(mapping),'--state-dir',str(case_store)])['result']
        start=cli(['image','acquire','execute','--definition-json',canonical(d['definition']).decode(),'--definition-digest',d['definition_digest'],
            '--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects']);case_id=start['operation_id']
        end=time.monotonic()+20
        while True:
            state=cli(['operation','inspect',case_id,'--state-dir',str(case_store)])['result']['state']
            if state['phase']=='finished':break
            assert time.monotonic()<end,('retain incomplete acquisition',state);time.sleep(.025)
        handle=owned_process(state,str(product))
        if handle:
            try:assert K.WaitForSingleObject(handle,3000)==0
            finally:K.CloseHandle(handle)
        map_check(mapping,expected);check('independent-generated-acquisition',state['quiescent'] and state['outcome']['status']=='completed' and src.read_bytes()==dst.read_bytes()==expected)
        original={f.name:f.read_bytes() for f in case_store.iterdir() if f.is_file()}
        def prepare(name,exe=probe):
            folder=owned/name;folder.mkdir();store=folder/'state';store.mkdir();out=folder/'support.json'
            result=call(dict(mode='prepare',operation_id=case_id,case_directory=str(case_store),policy=policy(),destination=str(out),state_directory=str(store)),exe)
            check('prepare-has-no-effects',not out.exists() and not list(store.iterdir()) and original=={f.name:f.read_bytes() for f in case_store.iterdir() if f.is_file()},case=name)
            check('worker-code-and-store-bound',result['definition']['image_digest']==digest(exe.read_bytes())[7:] and result['definition']['store']['ancestors'][-1]==result['definition']['store']['generation'],case=name)
            return result,store,out
        def finished(d,store,out,exe,result):
            observed=wait(result['operation_id'],store,exe);h=json.loads((store/'report.request').read_bytes());raw,rows=history_check(store/'report.records',h)
            decoded=call(dict(mode='history',header=h,records=raw.decode()),exe)
            check('native-independent-history-agrees',decoded['state']==rows[-1]['state']==observed['value']['state'] and decoded['complete'])
            state=observed['value']['state'];bundle.validate('urn:disked:schema:acquisition-case-export-outcome:1',state['outcome'])
            check('terminal-releases-provider-handles',state['quiescent'] and state['phase']=='finished')
            if out.exists():
                data=out.read_bytes();outputs.append(dict(bytes=str(len(data)),sha256=digest(data),status=state['outcome']['status']))
                if state['outcome']['output']['status']=='completed':
                    selected=d['definition']['export']['effect']['artifact'];check('independent-selected-output',len(data)==int(selected['bytes']) and digest(data)==selected['digest'])
            return observed,h,raw,rows
        d,store,out=prepare('normal')
        for change in (
            lambda x:x.update(image_digest='f'*64),
            lambda x:x['store']['ancestors'][-1].update(created='1'),
            lambda x:x['store']['generation'].update(created='18446744073709551616'),
            lambda x:x['store'].update(failure_domain='unbound'),
            lambda x:x['store'].update(generation=copy.deepcopy(x['export']['source']['store']['generation']),ancestors=copy.deepcopy(x['export']['source']['ancestors']),failure_domain=x['export']['source']['store']['failure_domain']),
            lambda x:x['export']['case'].update(revision='sha256:'+'f'*64),
            lambda x:x['export']['effect']['artifact'].update(bytes='1048578')):
            changed=copy.deepcopy(d['definition']);change(changed)
            try:bundle.validate('urn:disked:schema:report-worker-definition:1',changed);raise AssertionError('contradictory worker schema passed')
            except SpecError:check('automatic-worker-schema-relationship-refusal',True)
        changed=copy.deepcopy(d);changed['definition']['unexpected']='value';changed['definition_digest']=digest(canonical(changed['definition']))
        value=call(request(changed));check('closed-worker-shape-before-effects',value['status']=='refused' and not list(store.iterdir()))
        for flags in itertools.product((False,True),repeat=4):
            if all(flags):continue
            denied=grant(d);denied.update(zip(('case_read','report_write','store_write','host_effects'),flags));value=call(request(d,denied))
            check('denied-authority-before-effects',value['status']=='refused' and value['operation_id'] is None and value['diagnostic']=='report_worker_grant' and not out.exists() and not list(store.iterdir()),flags=flags)
        phantom=copy.deepcopy(d);phantom['definition']['store']['path']=str(owned/'missing');phantom['definition_digest']=digest(canonical(phantom['definition']))
        value=call(request(phantom,grant(phantom,store_write=False)));check('denied-before-path-resolution',value['diagnostic']=='report_worker_grant' and value['operation_id'] is None)
        for field,value in [('host_id','f'*64),('source_revision','f'*40),('input_digest','sha256:'+'f'*64)]:
            changed=copy.deepcopy(d);changed['definition'][field]=value;changed['definition_digest']=digest(canonical(changed['definition']));refused=call(request(changed))
            check('changed-execution-binding-no-effects',refused['status']=='refused' and refused['diagnostic']=='report_worker_definition_changed' and not list(store.iterdir()),field=field)
        changed=copy.deepcopy(d);changed['definition']['export']['effect']['artifact']['policy']['raw_values']=True;changed['definition_digest']=digest(canonical(changed['definition']))
        value=call(request(changed));check('typed-selected-content-reconstructed',value['status']=='refused' and value['diagnostic']=='case_export_reviewed_definition_changed' and not out.exists() and not list(store.iterdir()))
        value=call(request(d),fault);check('different-code-cannot-reuse-writer-admission',value['status']=='refused' and value['diagnostic']=='report_worker_definition_changed' and not out.exists() and not list(store.iterdir()))
        result=call(request(d));check('actual-durable-operation-id',result['operation_id'].startswith('report-op:') and result['status'] in ('completed','accepted_running'))
        observed,h,raw,rows=finished(d,store,out,probe,result);check('actual-output-completion',observed['status']=='completed' and observed['value']['state']['outcome']['status']=='completed')
        historical=call(dict(mode='inspect',operation_id=result['operation_id'],state_directory=str(store)),fault)
        check('compatible-reader-retains-old-code-evidence',historical['status']=='completed' and historical['value']['state']==observed['value']['state'] and historical['value']['definition']==d['definition'])
        again=call(request(d));check('duplicate-observes-without-restart',again['operation_id']==result['operation_id'] and (store/'report.records').read_bytes()==raw and out.read_bytes())
        late=call(dict(mode='cancel',operation_id=result['operation_id'],state_directory=str(store)));check('finished-cancellation-too-late',late['value']['cancellation_request']=='too_late' and (store/'report.cancel').read_bytes()==b'0')
        samples.append(dict(kind='actual-completed-report',definition=d,header=h,records=rows,observation=observed,artifact_bytes=out.read_bytes().decode('utf-8')))
        # Rehash altered records to distinguish semantic checks from hash checks.
        def forge(records):
            previous='0'*64;parts=[]
            for row in records:
                row=copy.deepcopy(row);row['previous']=previous;row.pop('digest',None);previous=hashlib.sha256(canonical(row)).hexdigest();row['digest']=previous;parts.append(canonical(row))
            return b'\n'.join(parts)+b'\n'
        for name,change in [
            ('u64-sequence',lambda x:x[0]['state'].update(sequence='18446744073709551616')),
            ('foreign-worker',lambda x:x[-1]['state']['binding'].update(worker_epoch='worker:'+'f'*32)),
            ('late-process',lambda x:x[-1]['state']['binding'].update(process_created='1')),
            ('missing-quiescence',lambda x:x[-1]['state'].update(quiescent=False)),
            ('false-effect-certainty',lambda x:x[-1]['state'].update(effect_certainty='uncertain')),
            ('zero-completion',lambda x:x[-1]['state']['outcome']['output'].update(submitted_bytes='0',written_bytes='0',read_bytes='0',verified_bytes='0')),
            ('changed-source-completion',lambda x:x[-1]['state']['outcome'].update(source_state='changed')),
            ('wrong-artifact-receipt',lambda x:x[-1]['state']['receipt']['output_receipt'].update(artifact_digest='sha256:'+'f'*64)),
            ('impossible-output-metadata',lambda x:x[-1]['state']['receipt']['output_receipt']['output_metadata'].update(bytes='0')),
            ('effects-before-dispatch',lambda x:x.__delitem__(1)),
            ('observed-cancel-reverted',lambda x:x[1]['state'].update(cancellation='observed')),
            ('post-terminal-record',lambda x:x.append(copy.deepcopy(x[-1])))]:
            altered=copy.deepcopy(rows);change(altered)
            if name=='effects-before-dispatch':altered[-1]['state']['sequence']='2'
            if name=='post-terminal-record':altered[-1]['state']['sequence']=str(len(altered))
            call(dict(mode='history',header=h,records=forge(altered).decode()),refusal='report_worker_');check('semantic-forged-history-refused',True,case=name)
        torn=call(dict(mode='history',header=h,records=raw.decode()+'{"partial":'))
        check('torn-suffix-retains-last-valid-state',not torn['complete'] and torn['state']==rows[-1]['state'])
        (store/'report.records').write_bytes(raw+b'{"partial":');unknown=call(dict(mode='inspect',operation_id=result['operation_id'],state_directory=str(store)))
        check('native-torn-history-not-completion',unknown['status']=='unknown' and unknown['value']['state']==rows[-1]['state'] and not unknown['value']['history_complete']);(store/'report.records').write_bytes(raw)
        # Fixed metadata names may not alias the output, and the case directory
        # may not be used as a new report execution store.
        alias=owned/'alias';alias.mkdir()
        call(dict(mode='prepare',operation_id=case_id,case_directory=str(case_store),policy=policy(),destination=str(alias/'REPORT.REQUEST'),state_directory=str(alias)),refusal='report_worker_output_store_alias')
        check('reserved-output-refused-without-files',not list(alias.iterdir()))
        # A delayed admission is a real still-owned process. Inspect and repeat
        # observe the same epochs; never dispatch a replacement.
        d,store,out=prepare('delayed-admission',fault);start=time.monotonic();result=call(request(d),fault,dict(DISKED_REPORT_WORKER_TEST_ADMISSION_DELAY='1'))
        check('bounded-admission-uncertainty',result['status']=='unknown' and result['operation_id'] and 2.8<time.monotonic()-start<8 and not out.exists())
        interim=call(dict(mode='inspect',operation_id=result['operation_id'],state_directory=str(store)),fault);before=(store/'report.records').read_bytes();again=call(request(d),fault)
        check('late-admission-no-replacement',interim['value']['worker_observation']=='running' and again['operation_id']==result['operation_id'] and before==(store/'report.records').read_bytes())
        process=report_process(interim['value']['state'],fault);assert process
        job=K.OpenJobObjectW(4,False,'Local\\DiskEd.Fake.Workers.v1.'+d['definition']['host_id']);assert job
        try:
            member=W.BOOL();limits=JobLimits();assert K.IsProcessInJob(process,job,C.byref(member)) and member.value
            assert K.QueryInformationJobObject(job,9,C.byref(limits),C.sizeof(limits),None)
            check('independent-aggregate-process-memory-bound',limits.basic.flags==0x308 and limits.basic.process_limit==4 and limits.process_memory==128*1024*1024 and limits.job_memory==512*1024*1024)
        finally:K.CloseHandle(job);K.CloseHandle(process)
        observed,h,raw,rows=finished(d,store,out,fault,result);check('late-worker-result-retained',observed['value']['state']['outcome']['status']=='completed')
        samples.append(dict(kind='actual-delayed-admission',definition=d,header=h,records=rows,observation=observed))
        d,store,out=prepare('cancel-before-output',fault);result=call(request(d),fault,dict(DISKED_REPORT_WORKER_TEST_EFFECT_DELAY='1'))
        cancelled=call(dict(mode='cancel',operation_id=result['operation_id'],state_directory=str(store)),fault);check('cancellation-request-distinct',cancelled['value']['cancellation_request']=='requested' and not out.exists())
        observed,h,raw,rows=finished(d,store,out,fault,result);state=observed['value']['state']
        check('worker-observed-cancellation-before-output',state['cancellation']=='observed' and state['outcome']['status']=='cancelled' and state['outcome']['output']['output_state']=='not_created' and not out.exists())
        samples.append(dict(kind='actual-cancellation-before-output',definition=d,header=h,records=rows,observation=observed))
        d,store,out=prepare('cancel-created-output',fault);release=store.parent/'release'
        result=call(request(d),fault,dict(DISKED_REPORT_TEST_EVENT='created',DISKED_REPORT_TEST_PAUSE='1',DISKED_REPORT_TEST_RELEASE_FILE=str(release)))
        end=time.monotonic()+5
        while not out.exists():assert time.monotonic()<end;time.sleep(.01)
        interim=call(dict(mode='inspect',operation_id=result['operation_id'],state_directory=str(store)),fault)
        check('actual-created-output-worker-still-running',interim['value']['worker_observation']=='running' and interim['value']['state']['phase']=='executing')
        cancel=call(dict(mode='cancel',operation_id=result['operation_id'],state_directory=str(store)),fault);check('created-output-cancel-requested',cancel['value']['cancellation_request']=='requested')
        release.write_bytes(b'1');observed,h,raw,rows=finished(d,store,out,fault,result);state=observed['value']['state']
        check('cancellation-retains-created-file',state['cancellation']=='observed' and state['outcome']['status']=='cancelled' and state['outcome']['output']['output_state']=='created' and state['receipt']['output_receipt']['output_created_observed'] and out.read_bytes()==b'')
        samples.append(dict(kind='actual-cancellation-after-creation',definition=d,header=h,records=rows,observation=observed))
        d,store,out=prepare('late-receipt',fault);result=call(request(d),fault,dict(DISKED_REPORT_WORKER_TEST_RECEIPT_DELAY='1'))
        end=time.monotonic()+5
        while True:
            try:data=out.read_bytes();break
            except (FileNotFoundError,PermissionError):assert time.monotonic()<end;time.sleep(.01)
        check('actual-output-before-terminal-receipt',digest(data)==d['definition']['export']['effect']['artifact']['digest'])
        cancelled=call(dict(mode='cancel',operation_id=result['operation_id'],state_directory=str(store)),fault);check('late-cancel-requested-not-effect-proof',cancelled['value']['cancellation_request']=='requested')
        observed,h,raw,rows=finished(d,store,out,fault,result);state=observed['value']['state']
        check('completed-effect-survives-late-cancellation',state['outcome']['status']=='completed' and state['cancellation']=='not_requested' and out.read_bytes()==data)
        samples.append(dict(kind='actual-late-receipt-and-cancel',definition=d,header=h,records=rows,observation=observed))
        d,store,out=prepare('lost-terminal-receipt',fault);result=call(request(d),fault,dict(DISKED_TEST_STORE_FAULT='report_finished.full'))
        observed=wait(result['operation_id'],store,fault,False);h=json.loads((store/'report.request').read_bytes());raw,rows=history_check(store/'report.records',h)
        check('failed-store-keeps-effect-uncertain',observed['status']=='unknown' and rows[-1]['state']['phase']=='executing' and rows[-1]['state']['outcome'] is None and out.exists())
        check('independent-output-not-invented-receipt',digest(out.read_bytes())==d['definition']['export']['effect']['artifact']['digest'])
        before=raw;again=call(request(d),fault);check('lost-receipt-no-automatic-retry',again['status']=='unknown' and again['operation_id']==result['operation_id'] and (store/'report.records').read_bytes()==before)
        samples.append(dict(kind='actual-output-with-injected-terminal-store-failure',definition=d,header=h,records=rows,observation=observed,independently_observed_output_sha256=digest(out.read_bytes())))
        for failure in ('created_validation','report_cancel_create.full','report_request.short'):
            d,store,out=prepare('partial-'+failure.replace('.','-'),fault);result=call(request(d),fault,dict(DISKED_TEST_STORE_FAULT=failure))
            check('partial-admission-retained',result['status']=='unknown' and result['operation_id'] and list(store.iterdir()) and not out.exists(),injection=failure)
            before={f.name:f.read_bytes() for f in store.iterdir() if f.is_file()};again=call(request(d),fault)
            check('partial-store-prevents-restart',again['status'] in ('unknown','refused') and before=={f.name:f.read_bytes() for f in store.iterdir() if f.is_file()} and not out.exists(),injection=failure)
        check('case-and-image-bytes-preserved',original=={f.name:f.read_bytes() for f in case_store.iterdir() if f.is_file()} and src.read_bytes()==dst.read_bytes()==expected);map_check(mapping,expected)
    result=dict(status='PASS',scope='Private native report admission/owned durable state and independent generated-file checks; not public service/frontend or physical/power-loss qualification',checks=len(observations),observations=observations,samples=samples,outputs=outputs)
    if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in result.items() if k not in ('observations','samples')},indent=2))
if __name__=='__main__':main()
