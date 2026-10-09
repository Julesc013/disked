"""Actual ordinary-file product export and native frontend journeys.

Only generated acquisition metadata/reports are selected. Private fault gates
control owned observer processes; producer records and exact bytes are checked
independently. No physical media, elevation, installation or custody claim.
"""
import argparse,copy,ctypes as C,json,os,queue,subprocess,sys,threading,time,uuid
from pathlib import Path
from gui_fixture import Gui,wait
from report_console_fixture import command
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evidence'))
from test_acquisition_worker import canonical,digest,source_bytes,map_check,fixture_directory,owned_process,K
from test_report_worker import report_process,history_check
from ctypes import wintypes as W

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--product',type=Path,required=True);ap.add_argument('--fault',type=Path,required=True)
    ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path);a=ap.parse_args()
    root=a.root.resolve();product=a.product.resolve();fault=a.fault.resolve();checks=[];journeys=[];outputs=[];samples=[]
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_REPORT_','DISKED_ACQ_','DISKED_TEST_'))}
    sys.path.insert(0,str(root/'spec/tools'));from specctl import Bundle
    bundle=Bundle(root/'spec')
    def check(name,value,**extra):assert value,(name,extra);checks.append(dict(name=name,passed=True,**extra))
    def validate(value):
        bundle.validate('urn:disked:schema:response:1',value)
        result=value.get('result')
        if result is not None and result.get('scope')=='recorded-acquisition-case-support-export':
            bundle.validate('urn:disked:schema:'+('export-preparation-result:1' if result.get('phase')=='prepare' else 'export-operation-result:1'),result)
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
    def grants(value):return dict(phase='execute',definition=value['definition'],definition_digest=value['definition_digest'],allow_case_read=True,allow_report_write=True,allow_store_write=True,allow_host_effects=True)
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
        def fixture(name):
            folder=owned/name;folder.mkdir();store=folder/'state';store.mkdir();return folder,dict(phase='prepare',case_operation_id=case_id,case_directory=str(case),destination=str(folder/'support.json'),state_directory=str(store))
        discovery=cli(['commands'])['result']['commands'];descriptor=next(c for c in discovery if c['id']=='evidence.export')
        check('explicit-static-report-discovery',descriptor['availability']=='available' and descriptor['implementation_status']=='implemented' and descriptor['contract_status']=='planned' and descriptor['reason']=='recorded_acquisition_case_support_export')
        build=cli(['build','inspect'])['result'];check('explicit-report-composition',build['report_provider']=='provider.report.acquisition-case.prototype/1')
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
            if kind=='cli':samples.append(dict(definition=q['definition'],header=header,rows=rows,result=done['result'],support=json.loads(body)))
        # Invalid scope/grants are rejected before the real provider creates files.
        folder,p=fixture('invalid');prepared=cli(command(p))['result'];q=grants(prepared)
        for bad in [dict(q,allow_host_effects=False),dict(q,definition_digest='sha256:'+'0'*64)]:
            value,_=wire('invalid-grant','evidence.export',bad,exits=(2,3));check('invalid-grant-before-effects',value['status']=='refused' and no_effects(p))
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
    report=dict(passed=True,checks=len(checks),observations=checks,native_journeys=journeys,verified_outputs=outputs,samples=samples,scope='Actual native ordinary-file product CLI/stdio/GUI/TUI/shell prepare/execute/watch plus private occupied callback gate; no broader storage/custody qualification',source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)))
    if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('observations','native_journeys','samples')}))
if __name__=='__main__':main()
