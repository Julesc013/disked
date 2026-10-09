"""Actual ordinary-file product export and native frontend journeys.

Only generated acquisition metadata/reports are selected. Private fault gates
control owned observer processes; producer records and exact bytes are checked
independently. No physical media, elevation, installation or custody claim.
"""
import argparse,copy,ctypes as C,itertools,json,os,queue,subprocess,sys,threading,time,uuid
from pathlib import Path
from gui_fixture import Gui,wait
from report_console_fixture import command
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evidence'))
from test_acquisition_worker import canonical,digest,source_bytes,map_check,fixture_directory,owned_process,K
from test_report_worker import report_process,history_check
from test_verification_case import combined_support
from test_image_observation import POLICIES
from ctypes import wintypes as W

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--product',type=Path,required=True);ap.add_argument('--fault',type=Path,required=True)
    ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path);ap.add_argument('--joined',action='store_true');ap.add_argument('--probe',type=Path);a=ap.parse_args()
    root=a.root.resolve();product=a.product.resolve();fault=a.fault.resolve();checks=[];journeys=[];outputs=[];samples=[]
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_REPORT_','DISKED_ACQ_','DISKED_TEST_'))}
    sys.path.insert(0,str(root/'spec/tools'));from specctl import Bundle,SpecError
    bundle=Bundle(root/'spec')
    probe=(a.probe or product.with_name('export_command_probe.exe')).resolve()
    def check(name,value,**extra):assert value,(name,extra);checks.append(dict(name=name,passed=True,**extra))
    def validate(value):
        bundle.validate('urn:disked:schema:response:1',value)
        result=value.get('result')
        if result is not None and result.get('scope') in ('recorded-acquisition-case-support-export','recorded-acquisition-verification-support-export'):
            version='2' if result['scope']=='recorded-acquisition-verification-support-export' else '1'
            bundle.validate('urn:disked:schema:'+('export-preparation-result:' if result.get('phase')=='prepare' else 'export-operation-result:')+version,result)
    def cli(argv,exits=(0,),exe=product,extra=None):
        p=subprocess.run([str(exe),'--json',*argv],capture_output=True,cwd=root,env=dict(env,**(extra or {})),timeout=15)
        assert p.returncode in exits and not p.stderr,(argv,p.returncode,p.stdout,p.stderr)
        value=json.loads(p.stdout);validate(value);check('native-cli',True,exit_code=p.returncode,output_sha256=digest(p.stdout));return value
    def wire(id,cmd,params,features=None,exits=(0,),exe=product,extra=None):
        request=dict(schema='org.disked.request/1',request_id=id,command=cmd,parameters=params,required_features=features or [])
        data=canonical(request)+b'\n';p=subprocess.run([str(exe),'protocol','serve','--format=ndjson'],input=data,capture_output=True,cwd=root,env=dict(env,**(extra or {})),timeout=15)
        assert p.returncode in exits and not p.stderr,(p.returncode,p.stdout,p.stderr)
        frames=[json.loads(row) for row in p.stdout.splitlines()];value=frames[-1];assert value['request_id']==id;validate(value)
        for event in frames[:-1]:bundle.validate('urn:disked:schema:report-operation-event:1',event)
        check('native-stdio',True,exit_code=p.returncode,input_sha256=digest(data),output_sha256=digest(p.stdout));return value,frames[:-1]
    def no_effects(p):return not Path(p['destination']).exists() and not list(Path(p['state_directory']).iterdir())
    def audit(p,reply=None,expected_grant=None,exits=(2,3)):
        v=dict(mode='audit',request=dict(schema='org.disked.request/1',request_id='synthetic-joined-port',command='evidence.export',parameters=p,required_features=[]),reply=reply or {})
        if expected_grant is not None:v['expected_grant']=expected_grant
        data=canonical(v);run=subprocess.run([str(probe)],input=data,capture_output=True,cwd=root,env=env,timeout=10)
        assert run.returncode in exits and not run.stderr,(run.returncode,run.stdout,run.stderr)
        out=json.loads(run.stdout);validate(out['response']);check('synthetic-joined-port-counts',True,prepare_calls=out['prepare_calls'],execute_calls=out['execute_calls'],input_sha256=digest(data),output_sha256=digest(run.stdout));return out
    def grants(value):
        p=dict(phase='execute',definition=value['definition'],definition_digest=value['definition_digest'],allow_case_read=True,allow_report_write=True,allow_store_write=True,allow_host_effects=True)
        if value['definition']['schema']=='org.disked.report-worker-definition-prototype/2':p['allow_collection_read']=True
        return p
    def gui(p):
        ui=Gui(product,['--gui',*command(p)],render=True)
        try:
            ui.click(109);details=ui.details();check('gui-review-inert',details['parameters']==p and details['reviewed'] and details['expected_revision'] is None and no_effects(selection))
            if a.evidence:ui.screenshot(a.evidence.parent/('gui-export-'+p['phase']+'-review.png'))
            ui.click(110);first=wait(lambda:ui.details() if ui.details().get('schema')=='org.disked.response/1' else None)
            validate(first);journeys.append(dict(frontend='gui',phase=p['phase'],response=first,observation=ui.observation()));return first
        finally:
            ui.close();assert ui.code==0 and not ui.error
    def console(kind,p,folder):
        input=folder/(kind+'-'+p.get('phase','watch')+'-input.json');output=folder/(kind+'-'+p.get('phase','watch')+'-output.json');input.write_bytes(canonical(p))
        startup=subprocess.STARTUPINFO();startup.dwFlags=1;startup.wShowWindow=0
        run=subprocess.run([sys.executable,str(Path(__file__).with_name('report_console_fixture.py')),str(product),str(input),str(output),kind],cwd=root,env=env,timeout=60,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
        value=json.loads(output.read_bytes());assert run.returncode==0 and 'fixture_error' not in value,value
        validate(value['response']);check('native-console-review-restore',value['inert_review'] and all(value['restored'].values()));journeys.append(value);return value['response']
    def exit_worker(state,exe):
        handle=report_process(state,exe)
        if handle:
            try:assert K.WaitForSingleObject(handle,3000)==0,('retain actual worker',state)
            finally:K.CloseHandle(handle)
    def finished(p,first,exe=product,terminal=True):
        end=time.monotonic()+20
        while True:
            value=cli(['operation','inspect',first['operation_id'],'--state-dir',p['state_directory']],(0,6),exe)
            state=value['result'].get('state',{})
            if state and ((terminal and state['phase']=='finished') or (not terminal and value['result']['worker_observation']!='running')):exit_worker(state,exe);return value
            assert time.monotonic()<end,('retain incomplete report',value);time.sleep(.03)
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        case=owned/'case';case.mkdir();src=owned/'source.img';dst=owned/'copy.img';mapping=owned/'copy.map';expected=source_bytes(65537);src.write_bytes(expected)
        review=cli(['image','acquire','prepare',str(src),str(dst),'--map',str(mapping),'--state-dir',str(case)])['result']
        start=cli(['image','acquire','execute','--definition-json',canonical(review['definition']).decode(),'--definition-digest',review['definition_digest'],'--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects'],(0,5));end=time.monotonic()+20
        while True:
            state=cli(['operation','inspect',start['operation_id'],'--state-dir',str(case)])['result']['state']
            if state['phase']=='finished':break
            assert time.monotonic()<end,('retain acquisition',state);time.sleep(.03)
        h=owned_process(state,str(product))
        if h:
            try:assert K.WaitForSingleObject(h,3000)==0
            finally:K.CloseHandle(h)
        check('independent-acquisition-bytes',src.read_bytes()==dst.read_bytes()==expected and state['outcome']['status']=='completed');map_check(mapping,expected)
        case_id=start['operation_id'];original={p.name:p.read_bytes() for p in case.iterdir() if p.is_file()}
        collection=None;collection_bytes=None;selected_support=None
        if a.joined:
            verification=owned/'verification';verification.mkdir()
            v=cli(['image','verify','prepare',case_id,str(dst),'--case-state-dir',str(case),'--map',str(mapping),'--state-dir',str(verification)])['result']
            argv=['image','verify','execute','--definition-json',canonical(v['definition']).decode(),'--definition-digest',v['definition_digest']]
            argv+=['--allow-'+flag for flag in ('case-read','image-read','map-read','store-write','host-effects','private-metadata')]
            launched=cli(argv,(0,5,6));deadline=time.monotonic()+20
            while True:
                verified=cli(['operation','inspect',launched['operation_id'],'--state-dir',str(verification)],(0,6))['result'];s=verified['state']
                if s['phase']=='finished':exit_worker(s,product);break
                assert time.monotonic()<deadline,('retain joined verification',verified);time.sleep(.03)
            collection=verification/'verification.collection';collection_bytes=collection.read_bytes();coll=json.loads(collection_bytes)
            check('actual-retained-matching-verification',s['outcome']['status']=='matched' and s['retention']['state']=='verified' and digest(collection_bytes)==s['retention']['digest'] and len(collection_bytes)==int(s['retention']['bytes']) and digest(canonical(coll))==s['retention']['collection_revision'])
            acq=coll['original_case'];selected_support=canonical(combined_support(acq,coll,POLICIES[0]))+b'\n'
            samples.append(dict(kind='actual-joined-source',acquisition=acq,verification=coll,verification_result=verified,collection_sha256=digest(collection_bytes),collection_hex=collection_bytes.hex(),verification_header=json.loads((verification/'verification.request').read_bytes()),verification_records_hex=(verification/'verification.records').read_bytes().hex()))
            # The admitted report selects retained metadata, not live image paths.
            for path in (src,dst,mapping):path.rename(path.with_name(path.name+'.retained'))
            check('original-image-paths-unavailable',all(not p.exists() for p in (src,dst,mapping)))
        def fixture(name):
            folder=owned/name;folder.mkdir();store=folder/'state';store.mkdir();p=dict(phase='prepare',case_operation_id=case_id,case_directory=str(case),destination=str(folder/'support.json'),state_directory=str(store))
            if a.joined:p.update(collection_path=str(collection),collection_digest=digest(collection_bytes))
            return folder,p
        discovery=cli(['commands'])['result']['commands'];descriptor=next(c for c in discovery if c['id']=='evidence.export')
        check('explicit-static-report-discovery',descriptor['availability']=='available' and descriptor['implementation_status']=='implemented' and descriptor['contract_status']=='planned' and descriptor['reason']=='recorded_acquisition_case_support_export')
        build=cli(['build','inspect'])['result'];check('explicit-report-composition',build['report_provider']=='provider.report.acquisition-case.prototype/1')
        check('explicit-joined-report-composition',build['joined_report_provider']=='provider.report.acquisition-verification.prototype/1')
        for kind in ('cli','stdio','gui','tui','shell'):
            folder,selection=fixture(kind)
            if kind=='cli':prepared=cli(command(selection));execute=lambda p:cli(command(p),(0,5,6))
            elif kind=='stdio':prepared=wire(kind+'-prepare','evidence.export',selection)[0];execute=lambda p:wire(kind+'-execute','evidence.export',p,exits=(0,5,6))[0]
            elif kind=='gui':prepared=gui(selection);execute=gui
            else:prepared=console(kind,selection,folder);execute=lambda p:console(kind,p,folder)
            check(kind+'-prepare-inert',prepared['status']=='completed' and not prepared['result']['execution_admitted'] and no_effects(selection))
            q=grants(prepared['result']);first=execute(q);check(kind+'-actual-operation-id',first['status'] in ('completed','accepted_running','unknown') and first['operation_id'].startswith('report-op:'))
            done=finished(selection,first);body=Path(selection['destination']).read_bytes();artifact=q['definition']['export']['effect']['artifact']
            check(kind+'-independent-complete-effect',done['result']['state']['outcome']['status']=='completed' and digest(body)==artifact['digest'] and len(body)==int(artifact['bytes']))
            if a.joined:check(kind+'-independent-selected-joined-content',body==selected_support and all(done['result'][key]=='not_established' for key in ('authenticity','custody_authentication','current_image_state','power_loss_persistence')))
            if a.joined and kind=='cli':
                # Independently mutate actual producer data; no file or worker
                # changes, and no native qualification inferred from validation.
                for name,change in (
                    ('outer-digest',lambda v:v.update(definition_digest='sha256:'+'0'*64)),
                    ('code-binding',lambda v:v['state']['binding'].update(image_digest='0'*64)),
                    ('host-binding',lambda v:v['state']['binding'].update(host_id='0'*64)),
                    ('store-binding',lambda v:v.update(state_directory=v['state_directory']+'.other')),
                    ('joint-receipt',lambda v:v['state']['receipt'].update(definition_digest='sha256:'+'0'*64)),
                    ('effect-receipt',lambda v:v['state']['receipt']['output_receipt'].update(definition_digest='sha256:'+'0'*64)),
                    ('artifact-receipt',lambda v:v['state']['receipt']['output_receipt'].update(artifact_digest='sha256:'+'0'*64)),
                    ('producer-receipt',lambda v:v['state']['receipt']['output_receipt']['producer'].update(identity='synthetic-other-producer')),
                    ('output-receipt',lambda v:v['state']['receipt']['output_receipt'].update(output_path=v['state_directory']+'\\other'))):
                    changed=copy.deepcopy(done['result']);change(changed)
                    try:bundle.validate('urn:disked:schema:export-operation-result:2',changed)
                    except SpecError:check('synthetic-public-producer-contradiction-refused',True,case=name)
                    else:raise AssertionError(('producer contradiction accepted',name))
            outputs.append(dict(frontend=kind,operation_id=first['operation_id'],bytes=str(len(body)),sha256=digest(body),definition_digest=q['definition_digest']))
            header=json.loads((Path(selection['state_directory'])/'report.request').read_bytes());raw,rows=history_check(Path(selection['state_directory'])/'report.records',header)
            params=dict(operation_id=first['operation_id'],state_directory=selection['state_directory'])
            watched=cli(command(params))['result'];check(kind+'-reconnect-records',[e['payload']['record'] for e in watched['events']]==rows and watched['state']==rows[-1]['state'])
            streamed,events=wire(kind+'-watch','operation.watch',params,['org.disked.report-operation-events/1'])
            check(kind+'-actual-streaming',streamed['result']['events']==[] and [e['payload']['record'] for e in events]==rows)
            resume=dict(params,after_sequence='1',after_digest=rows[0]['digest'],worker_epoch=header['worker_epoch'])
            resumed,_=wire(kind+'-resume','operation.watch',resume);check(kind+'-resume-exact',[e['payload']['record'] for e in resumed['result']['events']]==rows[1:])
            baseline={p.name:p.read_bytes() for p in Path(selection['state_directory']).iterdir()}
            repeated=wire(kind+'-repeat','evidence.export',q)[0];check(kind+'-repeat-no-new-attempt',repeated['operation_id']==first['operation_id'] and baseline=={p.name:p.read_bytes() for p in Path(selection['state_directory']).iterdir()} and body==Path(selection['destination']).read_bytes())
            if kind=='gui':
                ui=Gui(product,['--gui',*command(params)],render=True)
                try:
                    ui.click(109);ui.click(110);watch=wait(lambda:ui.details() if ui.details().get('schema')=='org.disked.response/1' else None);check('gui-watch-actual-render',watch['result']['events']==watched['events'] or [e['payload']['record'] for e in watch['result']['events']]==rows)
                    journeys.append(dict(frontend='gui',phase='watch',response=watch,observation=ui.observation()))
                finally:ui.close();assert ui.code==0 and not ui.error
            elif kind in ('tui','shell'):
                watch=console(kind,params,folder);check(kind+'-watch-actual-render',[e['payload']['record'] for e in watch['result']['events']]==rows)
            samples.append(dict(kind='actual-frontend-report',frontend=kind,definition=q['definition'],header=header,rows=rows,result=done['result'],support=json.loads(body),support_hex=body.hex()))
        # Invalid scope/grants are rejected before the real provider creates files.
        folder,p=fixture('invalid');prepared=cli(command(p))['result'];q=grants(prepared)
        for bad in [dict(q,allow_host_effects=False),dict(q,definition_digest='sha256:'+'0'*64)]:
            value,_=wire('invalid-grant','evidence.export',bad,exits=(2,3));check('invalid-grant-before-effects',value['status']=='refused' and no_effects(p))
        if a.joined:
            flags=('case_read','collection_read','report_write','store_write','host_effects')
            for bits in itertools.product((False,True),repeat=5):
                if all(bits):continue
                bad=dict(q,**{'allow_'+key:bit for key,bit in zip(flags,bits)});value,_=wire('missing-grants','evidence.export',bad,exits=(2,));check('joined-missing-grant-before-effects',value['status']=='refused' and no_effects(p))
                counted=audit(bad,exits=(2,));check('synthetic-joined-false-grants-zero-ports',counted['prepare_calls']==counted['execute_calls']==0)
            for key in ('collection_path','collection_digest'):
                bad=dict(p);bad.pop(key);value,_=wire('incomplete-selection','evidence.export',bad,exits=(2,));check('joined-incomplete-selection-before-effects',value['status']=='refused' and no_effects(p))
                counted=audit(bad,exits=(2,));check('synthetic-joined-incomplete-selection-zero-ports',counted['prepare_calls']==counted['execute_calls']==0)
            inner=q['definition']['export']['effect']['artifact']['digest'];value,_=wire('inner-digest','evidence.export',dict(q,definition_digest=inner),exits=(3,));check('joined-inner-digest-no-authority',value['status']=='refused' and no_effects(p))
            counted=audit(dict(q,definition_digest=inner),exits=(3,));check('synthetic-joined-inner-digest-zero-ports',counted['prepare_calls']==counted['execute_calls']==0)
            granted={key.removeprefix('allow_'):q[key] for key in q if key.startswith('allow_')};granted['definition_digest']=q['definition_digest']
            unknown=dict(schema='org.disked.report-admission-prototype/1',status='unknown',operation_id='report-op:'+'a'*32,value={},diagnostic='synthetic_no_native_effect',platform_code='0')
            counted=audit(q,unknown,granted,exits=(6,));check('synthetic-exact-joined-grant-one-port',counted['prepare_calls']==0 and counted['execute_calls']==1 and counted['response']['result']['state_directory']==p['state_directory'] and counted['response']['operation_id']==unknown['operation_id'] and no_effects(p))
            changed=copy.deepcopy(prepared);changed['definition']['export']['sources']['collection']['digest']='sha256:'+'0'*64;changed['definition_digest']=digest(canonical(changed['definition']))
            counted=audit(p,{key:changed[key] for key in ('definition','definition_digest')},exits=(3,));check('synthetic-preparation-source-mismatch-no-effect-port',counted['prepare_calls']==1 and counted['execute_calls']==0 and counted['response']['status']=='refused' and no_effects(p))
        value,_=wire('bad-policy','evidence.export',dict(p,force=True),exits=(2,));check('closed-request-before-effects',value['status']=='refused' and no_effects(p))
        # Exact named gates give the observer a real occupied channel across
        # timeout; release its actual callback, never replace it or invent exit.
        K.CreateEventW.argtypes=[C.c_void_p,W.BOOL,W.BOOL,W.LPCWSTR];K.CreateEventW.restype=W.HANDLE;K.SetEvent.argtypes=[W.HANDLE];K.SetEvent.restype=W.BOOL
        gate='Local\\DiskEdReportTest-'+uuid.uuid4().hex;entered=K.CreateEventW(None,True,False,gate+'.entered');release=K.CreateEventW(None,True,False,gate+'.release');assert entered and release
        folder,p=fixture('bounded-wait');folder2,p2=fixture('busy');process=None
        q=grants(cli(command(p),exe=fault)['result'])
        try:
            private_env=dict(env,DISKED_REPORT_TEST_GATE=gate)
            process=subprocess.Popen([str(fault),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=private_env)
            inbox=queue.Queue()
            def read():
                for line in process.stdout:inbox.put(line)
                inbox.put(None)
            thread=threading.Thread(target=read,daemon=True);thread.start()
            def exchange(id,cmd,parameters):
                frame=dict(schema='org.disked.request/1',request_id=id,command=cmd,parameters=parameters,required_features=[]);started=time.monotonic();process.stdin.write(canonical(frame)+b'\n');process.stdin.flush();raw=inbox.get(timeout=8);assert raw is not None;value=json.loads(raw);assert value['request_id']==id;validate(value);return value,time.monotonic()-started
            first,elapsed=exchange('expired','evidence.export',q);check('bounded-wait-preserves-routing',first['status']=='unknown' and first['result']['state_directory']==p['state_directory'] and first['result']['definition_digest']==q['definition_digest'] and 3.8<=elapsed<6 and K.WaitForSingleObject(entered,0)==0 and no_effects(p),elapsed_seconds=elapsed)
            cached,elapsed=exchange('cached','command.list',{});check('cached-discovery-during-live-call',cached['status']=='completed' and elapsed<1)
            busy,elapsed=exchange('busy','evidence.export',p2);check('occupied-slot-refuses-second-effect',busy['status']=='refused' and busy['diagnostics'][0]['code']=='request_resource_limit' and elapsed<1 and no_effects(p2))
            assert K.SetEvent(release)
            with __import__('contextlib').suppress(queue.Empty):assert inbox.get(timeout=.5) is None,'unsolicited late response'
            end=time.monotonic()+10
            while True:
                reconciled,_=exchange('after-completion','evidence.export',q)
                if reconciled['status']!='refused' or reconciled['diagnostics'][0]['code']!='request_resource_limit':break
                assert time.monotonic()<end,'retain occupied report request';time.sleep(.02)
            check('late-completion-never-reissued',reconciled['status'] in ('completed','accepted_running','unknown') and reconciled['operation_id'] and no_effects(p2))
            done=finished(p,reconciled,fault);body=Path(p['destination']).read_bytes();artifact=q['definition']['export']['effect']['artifact']
            check('late-callback-single-actual-effect',done['result']['state']['outcome']['status']=='completed' and digest(body)==artifact['digest'] and len(body)==int(artifact['bytes']))
            header=json.loads((Path(p['state_directory'])/'report.request').read_bytes());history_check(Path(p['state_directory'])/'report.records',header)
            baseline={f.name:f.read_bytes() for f in Path(p['state_directory']).iterdir()};again,_=exchange('same-claim','evidence.export',q)
            check('late-effect-never-replayed',again['operation_id']==header['operation_id']==reconciled['operation_id'] and baseline=={f.name:f.read_bytes() for f in Path(p['state_directory']).iterdir()})
            outputs.append(dict(frontend='stdio-private-timeout',operation_id=reconciled['operation_id'],bytes=str(len(body)),sha256=digest(body),definition_digest=q['definition_digest']))
            process.stdin.close();assert process.wait(timeout=5)==6 and not process.stderr.read();thread.join(timeout=1)
            journeys.append(dict(frontend='stdio',phase='occupied-timeout-gate',expired=first,cached=cached,busy=busy,reconciled=reconciled))
        finally:
            K.SetEvent(release)
            if process is not None and process.poll() is None:process.kill();process.wait(timeout=5)
            if process is not None:
                for file in (process.stdin,process.stdout,process.stderr):
                    if not file.closed:file.close()
            K.CloseHandle(entered);K.CloseHandle(release)
        # Product ignores all test gate/worker delay controls.
        started=time.monotonic();normal=cli(command(p2),(0,),extra=dict(DISKED_REPORT_TEST_GATE='missing-event',DISKED_REPORT_WORKER_TEST_ADMISSION_DELAY='1'))
        check('production-does-not-read-test-gates',normal['status']=='completed' and time.monotonic()-started<2 and no_effects(p2))
        check('original-case-metadata-unchanged',original=={p.name:p.read_bytes() for p in case.iterdir() if p.is_file()})
        if a.joined:check('selected-collection-unchanged',collection.read_bytes()==collection_bytes)
    report=dict(passed=True,joined=a.joined,checks=len(checks),observations=checks,native_journeys=journeys,verified_outputs=outputs,samples=samples,scope='Actual native ordinary-file product CLI/stdio/GUI/TUI/shell prepare/execute/watch plus private occupied callback gate; no broader storage/custody qualification',source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)))
    if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('observations','native_journeys','samples')}))
if __name__=='__main__':main()
