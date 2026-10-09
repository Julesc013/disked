"""Actual native verification journeys and owned asynchronous request faults.

Expected behaviour is defined in product-verification-prototype.json before
evaluation. Only generated ordinary-file acquisition/image/map metadata is used.
"""
import argparse,copy,ctypes as C,hashlib,itertools,json,os,queue,subprocess,sys,threading,time,uuid
from pathlib import Path
from ctypes import wintypes as W
from unittest.mock import patch
from gui_fixture import Gui,wait
from verification_console_fixture import command,FLAGS
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'evidence'))
from test_acquisition_worker import canonical,digest,source_bytes,map_check,fixture_directory,owned_process,K
from test_report_worker import report_process
FEATURE='org.disked.verification-operation-events/1'

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--product',type=Path,required=True);ap.add_argument('--fault',type=Path,required=True)
    ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path);a=ap.parse_args()
    root=a.root.resolve();product=a.product.resolve();fault=a.fault.resolve();checks=[];journeys=[];samples=[]
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_REPORT_','DISKED_ACQ_','DISKED_TEST_','DISKED_VERIFICATION_'))}
    sys.path.insert(0,str(root/'spec/tools'));from specctl import Bundle
    bundle=Bundle(root/'spec')
    def check(name,ok,**extra):assert ok,(name,extra);checks.append(dict(name=name,passed=True,**extra))
    def validate(value):
        bundle.validate('urn:disked:schema:response:1',value);r=value.get('result')
        if r and r.get('scope')=='recorded-acquired-image-verification':bundle.validate('urn:disked:schema:'+('verification-preparation-result:1' if r.get('phase')=='prepare' else 'verification-operation-result:1'),r)
    def cli(argv,exits=(0,),exe=product,extra=None):
        p=subprocess.run([str(exe),'--json',*argv],capture_output=True,cwd=root,env=dict(env,**(extra or {})),timeout=15)
        assert p.returncode in exits and not p.stderr,(argv[:4],p.returncode,p.stdout[:400],p.stderr);v=json.loads(p.stdout);validate(v);check('native-cli',True,exit_code=p.returncode,output_sha256=digest(p.stdout));return v
    def frame(id,cmd,p,features=()):return dict(schema='org.disked.request/1',request_id=id,command=cmd,parameters=p,required_features=list(features))
    def wire(id,cmd,p,features=(),exits=(0,),exe=product,extra=None):
        data=canonical(frame(id,cmd,p,features))+b'\n';r=subprocess.run([str(exe),'protocol','serve','--format=ndjson'],input=data,capture_output=True,cwd=root,env=dict(env,**(extra or {})),timeout=15)
        assert r.returncode in exits and not r.stderr,(id,r.returncode,r.stdout[:400],r.stderr);frames=[json.loads(row) for row in r.stdout.splitlines()];v=frames[-1];assert v['request_id']==id;validate(v)
        for e in frames[:-1]:bundle.validate('urn:disked:schema:verification-operation-event:1',e)
        check('native-stdio',True,exit_code=r.returncode,input_sha256=digest(data),output_sha256=digest(r.stdout));return v,frames[:-1]
    def grants(r):return dict(phase='execute',definition=r['definition'],definition_digest=r['definition_digest'],**{'allow_'+f.replace('-','_'):True for f in FLAGS})
    def inert(p):return not list(Path(p['state_directory']).iterdir())
    def retained(p):return {f.name:f.read_bytes() for f in Path(p['state_directory']).iterdir() if f.is_file()}
    def gui(p,selected):
        before=retained(selected)
        with patch.dict(os.environ,env,clear=True):ui=Gui(product,['--gui',*command(p)],render=True)
        try:
            ui.click(109);d=ui.details();check('gui-review-inert',d['parameters']==p and d['reviewed'] and d['expected_revision'] is None and retained(selected)==before)
            if a.evidence:ui.screenshot(a.evidence.parent/('gui-verification-'+p.get('phase','watch')+'-review.png'))
            ui.click(110);v=wait(lambda:ui.details() if ui.details().get('schema')=='org.disked.response/1' else None);validate(v);journeys.append(dict(frontend='gui',phase=p.get('phase','watch'),response=v,observation=ui.observation()));return v
        finally:ui.close();assert ui.code==0 and not ui.error
    def console(kind,p,folder):
        inp=folder/(kind+'-'+p.get('phase','watch')+'-input.json');out=folder/(kind+'-'+p.get('phase','watch')+'-output.json');inp.write_bytes(canonical(p));startup=subprocess.STARTUPINFO();startup.dwFlags=1;startup.wShowWindow=0
        r=subprocess.run([sys.executable,str(Path(__file__).with_name('verification_console_fixture.py')),str(product),str(inp),str(out),kind],cwd=root,env=env,timeout=75,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
        v=json.loads(out.read_bytes());assert r.returncode==0 and 'fixture_error' not in v,v.get('fixture_error');validate(v['response']);check('console-inert-review-and-restore',v['inert_review'] and all(v['restored'].values()));journeys.append(v);return v['response']
    def finish(p,first,exe=product):
        deadline=time.monotonic()+20
        while True:
            v=cli(['operation','inspect',first['operation_id'],'--state-dir',p['state_directory']],(0,6),exe);s=v['result'].get('state')
            if s and s['phase']=='finished':
                h=report_process(s,exe)
                if h:
                    try:assert K.WaitForSingleObject(h,3000)==0,('retain actual worker',s)
                    finally:K.CloseHandle(h)
                return v
            assert time.monotonic()<deadline,('retain unresolved fixture',v);time.sleep(.03)
    def independent(p,done):
        store=Path(p['state_directory']);header=json.loads((store/'verification.request').read_bytes());raw=(store/'verification.records').read_bytes();rows=[];previous='0'*64
        for n,line in enumerate(raw.splitlines(),1):
            row=json.loads(line);unsigned=copy.deepcopy(row);hash_=unsigned.pop('digest');assert canonical(row)==line and row['previous']==previous and hashlib.sha256(canonical(unsigned)).hexdigest()==hash_ and row['state']['sequence']==str(n);previous=hash_;rows.append(row);bundle.validate('urn:disked:schema:verification-worker-record:1',row)
        s=done['result']['state'];check('independent-canonical-history',raw.endswith(b'\n') and s==rows[-1]['state'] and s['quiescent'] and len(rows)<=32)
        body=(store/'verification.collection').read_bytes()
        if s['retention']['state']=='verified':
            collection=json.loads(body);check('independent-collection-and-observer',body.endswith(b'\n') and digest(body)==s['retention']['digest'] and len(body)==int(s['retention']['bytes']) and digest(canonical(collection))==s['retention']['collection_revision'] and collection['records'][0]['observation']['outcome']==s['outcome'] and collection['records'][0]['observer']=={n:s['binding'][n] for n in ('attempt_id','worker_epoch','capture_epoch','process_id','process_created')})
        samples.append(dict(header=header,rows=rows,result=done['result'],history_sha256=digest(raw),collection_sha256=digest(body),collection_hex=body.hex()));return header,rows
    K.CreateEventW.argtypes=[C.c_void_p,W.BOOL,W.BOOL,W.LPCWSTR];K.CreateEventW.restype=W.HANDLE;K.SetEvent.argtypes=[W.HANDLE];K.SetEvent.restype=W.BOOL
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        case=owned/'case';case.mkdir();src=owned/'source.img';image=owned/'copy.img';mapping=owned/'copy.map';expected=source_bytes(262145);src.write_bytes(expected)
        r=cli(['image','acquire','prepare',str(src),str(image),'--map',str(mapping),'--state-dir',str(case)])['result'];start=cli(['image','acquire','execute','--definition-json',canonical(r['definition']).decode(),'--definition-digest',r['definition_digest'],'--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects'],(0,5));deadline=time.monotonic()+20
        while True:
            s=cli(['operation','inspect',start['operation_id'],'--state-dir',str(case)])['result']['state']
            if s['phase']=='finished':break
            assert time.monotonic()<deadline;time.sleep(.03)
        h=owned_process(s,str(product))
        if h:
            try:assert K.WaitForSingleObject(h,3000)==0
            finally:K.CloseHandle(h)
        check('independent-generated-acquisition',src.read_bytes()==image.read_bytes()==expected and s['outcome']['status']=='completed');map_check(mapping,expected);original={f.name:f.read_bytes() for f in case.iterdir() if f.is_file()};case_id=start['operation_id']
        def fixture(name):
            folder=owned/name;folder.mkdir();store=folder/'state';store.mkdir();return folder,dict(phase='prepare',case_operation_id=case_id,case_directory=str(case),image=str(image),map=str(mapping),state_directory=str(store))
        discovery=cli(['commands'])['result']['commands'];d=next(c for c in discovery if c['id']=='image.verify');check('explicit-provisional-product-selection',sum(c['availability']=='available' for c in discovery)==20 and d['availability']=='available' and d['contract_status']=='planned' and d['reason']=='recorded_acquired_image_verification')
        check('explicit-verifier-identity',cli(['build','inspect'])['result']['verification_provider']=='provider.image.verify.recorded.prototype/1')
        for kind in ('cli','stdio','gui','tui','shell'):
            folder,p=fixture(kind)
            if kind=='cli':prepared=cli(command(p));execute=lambda q:cli(command(q),(0,5,6))
            elif kind=='stdio':prepared=wire(kind+'-prepare','image.verify',p)[0];execute=lambda q:wire(kind+'-execute','image.verify',q,exits=(0,5,6))[0]
            elif kind=='gui':prepared=gui(p,p);execute=lambda q:gui(q,p)
            else:prepared=console(kind,p,folder);execute=lambda q:console(kind,q,folder)
            check(kind+'-prepare-inert',prepared['status']=='completed' and not prepared['result']['execution_admitted'] and inert(p));q=grants(prepared['result']);first=execute(q);check(kind+'-actual-operation-id',first['operation_id'] and first['operation_id'].startswith('verify-op:'))
            done=finish(p,first);header,rows=independent(p,done);check(kind+'-actual-match',done['result']['state']['outcome']['status']=='matched' and done['result']['state']['outcome']['matched_bytes']==str(len(expected)) and done['result']['attachment_applicability']=='applicable')
            before={f.name:f.read_bytes() for f in Path(p['state_directory']).iterdir()};again=wire(kind+'-repeat','image.verify',q)[0];check(kind+'-no-restarted-attempt',again['operation_id']==first['operation_id'] and before=={f.name:f.read_bytes() for f in Path(p['state_directory']).iterdir()})
            w=dict(operation_id=first['operation_id'],state_directory=p['state_directory']);watched,events=wire(kind+'-watch','operation.watch',w,[FEATURE]);check(kind+'-negotiated-exact-events',[e['payload']['record'] for e in events]==rows and watched['result']['events']==[])
            if kind=='gui':watch=gui(w,p)
            elif kind in ('tui','shell'):watch=console(kind,w,folder)
            else:watch=cli(['operation','watch',first['operation_id'],'--state-dir',p['state_directory']])
            check(kind+'-watch-retained-rows',[e['payload']['record'] for e in watch['result']['events']]==rows)
        folder,p=fixture('invalid');q=grants(cli(command(p))['result'])
        for bits in itertools.product((False,True),repeat=6):
            if all(bits):continue
            bad=dict(q,**{'allow_'+f.replace('-','_'):b for f,b in zip(FLAGS,bits)});v,_=wire('missing-grants','image.verify',bad,exits=(2,));check('missing-grant-before-effects',v['status']=='refused' and inert(p))
        v,_=wire('wrong-digest','image.verify',dict(q,definition_digest='sha256:'+'0'*64),exits=(3,));check('wrong-digest-inert',v['status']=='refused' and inert(p));wire('unsupported-watch-feature','image.verify',p,[FEATURE],exits=(3,))
        # A live named gate establishes actual callback occupancy across timeout.
        gate='Local\\DiskEdVerificationTest-'+uuid.uuid4().hex;entered=K.CreateEventW(None,True,False,gate+'.entered');release=K.CreateEventW(None,True,False,gate+'.release');assert entered and release
        folder,p=fixture('bounded-wait');folder2,p2=fixture('busy');q=grants(cli(command(p),exe=fault)['result']);process=None
        try:
            process=subprocess.Popen([str(fault),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=dict(env,DISKED_VERIFICATION_TEST_GATE=gate));inbox=queue.Queue()
            def read():
                for line in process.stdout:inbox.put(line)
                inbox.put(None)
            thread=threading.Thread(target=read,daemon=True);thread.start()
            def exchange(id,cmd,params):
                started=time.monotonic();process.stdin.write(canonical(frame(id,cmd,params))+b'\n');process.stdin.flush();raw=inbox.get(timeout=8);assert raw is not None;v=json.loads(raw);assert v['request_id']==id;validate(v);return v,time.monotonic()-started
            expired,elapsed=exchange('expired','image.verify',q);check('bounded-wait-retains-review',expired['status']=='unknown' and expired['result']['state_directory']==p['state_directory'] and expired['result']['definition_digest']==q['definition_digest'] and 3.8<=elapsed<6 and K.WaitForSingleObject(entered,0)==0 and inert(p),elapsed_seconds=elapsed)
            cached,elapsed=exchange('cached','command.list',{});check('cached-discovery-with-live-callback',cached['status']=='completed' and elapsed<1)
            busy,elapsed=exchange('busy','image.verify',p2);check('occupied-slot-not-replaced',busy['status']=='refused' and busy['diagnostics'][0]['code']=='request_resource_limit' and elapsed<1 and inert(p2));assert K.SetEvent(release)
            try:unexpected=inbox.get(timeout=.2)
            except queue.Empty:unexpected=None
            check('no-unsolicited-late-response',unexpected is None)
            deadline=time.monotonic()+10
            while True:
                reconciled,_=exchange('reconcile','image.verify',q)
                if reconciled['status']!='refused' or reconciled['diagnostics'][0]['code']!='request_resource_limit':break
                assert time.monotonic()<deadline;time.sleep(.03)
            done=finish(p,reconciled,fault);independent(p,done);check('released-callback-single-matched-effect',done['result']['state']['outcome']['status']=='matched' and inert(p2));journeys.append(dict(frontend='stdio',phase='occupied-callback',expired=expired,cached=cached,busy=busy,reconciled=reconciled))
            process.stdin.close();assert process.wait(timeout=5)==6 and not process.stderr.read();thread.join(timeout=1)
        finally:
            K.SetEvent(release)
            if process is not None and process.poll() is None:process.kill();process.wait(timeout=5)
            if process is not None:
                for file in (process.stdin,process.stdout,process.stderr):
                    if not file.closed:file.close()
            K.CloseHandle(entered);K.CloseHandle(release)
        # The actual GUI changes view while its owned callback remains pending.
        gate='Local\\DiskEdVerificationView-'+uuid.uuid4().hex;entered=K.CreateEventW(None,True,False,gate+'.entered');release=K.CreateEventW(None,True,False,gate+'.release');assert entered and release
        folder,p=fixture('stale-view');ui=None
        try:
            with patch.dict(os.environ,dict(env,DISKED_VERIFICATION_TEST_GATE=gate),clear=True):ui=Gui(fault,['--gui',*command(p)],render=True)
            ui.click(109);check('gui-stale-review-inert',ui.details()['parameters']==p and inert(p));ui.click(110)
            wait(lambda:K.WaitForSingleObject(entered,0)==0);pending=ui.details()['pending_request'];ui.click(111);current=ui.details()
            check('gui-changed-view-retains-pending-correlation',current.get('pending_request')==pending and current.get('schema')!='org.disked.response/1' and inert(p))
            assert K.SetEvent(release);late=wait(lambda:ui.details() if ui.details().get('earlier_request') else None);validate(late['earlier_request'])
            check('gui-late-completion-separate',late.get('schema')!='org.disked.response/1' and late['earlier_request']['request_id']==pending and late['earlier_request']['status']=='completed' and not late.get('pending_request') and inert(p))
            journeys.append(dict(frontend='gui',phase='changed-view',pending=current,completed=late,observation=ui.observation()))
            if a.evidence:ui.screenshot(a.evidence.parent/'gui-verification-earlier-request.png')
        finally:
            K.SetEvent(release)
            if ui is not None:ui.close();assert ui.code==0 and not ui.error
            K.CloseHandle(entered);K.CloseHandle(release)
        folder,p=fixture('oversized-reply');q=grants(cli(command(p),exe=fault)['result']);bad=cli(command(q),(6,),fault,dict(DISKED_VERIFICATION_COMMAND_TEST_OVERSIZED_REPLY='1'))
        check('oversized-reply-keeps-routing-and-allocated-id',bad['operation_id'] and bad['result']['state_directory']==p['state_directory'] and bad['result']['definition_digest']==q['definition_digest'] and bad['diagnostics'][0]['code']=='request_completion_unresolved');done=finish(p,bad,fault);independent(p,done);check('bad-reply-does-not-undo-worker',done['result']['state']['outcome']['status']=='matched')
        with image.open('r+b') as f:f.seek(65536);f.write(bytes([expected[65536]^1]))
        folder,p=fixture('mismatch');q=grants(cli(command(p))['result']);first=cli(command(q),(4,5,6));done=finish(p,first);independent(p,done);check('actual-mismatch-is-read-result',done['status']=='completed' and done['result']['state']['outcome']['status']=='mismatch' and done['result']['state']['outcome']['covered_bytes']=='65536');cli(command(q),(4,));image.write_bytes(expected)
        folder,p=fixture('cancel-prefix');q=grants(cli(command(p),exe=fault)['result']);first=cli(command(q),(5,),fault,dict(DISKED_VERIFICATION_WORKER_TEST_PROGRESS_DELAY='1'));deadline=time.monotonic()+10
        while True:
            v=cli(['operation','inspect',first['operation_id'],'--state-dir',p['state_directory']],exe=fault)
            if int(v['result']['state']['progress']['covered_bytes']):break
            assert time.monotonic()<deadline;time.sleep(.02)
        cancel=cli(['operation','cancel',first['operation_id'],'--state-dir',p['state_directory']],exe=fault)
        check('actual-cancel-request-not-worker-observation',cancel['result']['cancellation_request']=='requested' and cancel['result']['state']['cancellation_observation']=='not_observed')
        done=finish(p,first,fault);independent(p,done);check('actual-cancelled-prefix',done['status']=='completed' and done['result']['state']['outcome']['status']=='cancelled' and done['result']['state']['outcome']['covered_bytes']=='65536');cli(command(q),(4,),fault)
        folder,p=fixture('uncertain-retention');q=grants(cli(command(p),exe=fault)['result']);first=cli(command(q),(5,6),fault,dict(DISKED_TEST_STORE_FAULT='verification_collection.short'));done=finish(p,first,fault);independent(p,done)
        check('actual-retention-failure-keeps-verdict',done['status']=='completed' and done['result']['state']['outcome']['status']=='matched' and done['result']['state']['disposition']=='unknown' and done['result']['state']['retention']['state']=='uncertain');before=retained(p);cli(command(q),(6,),fault);check('unknown-retention-never-restarts',retained(p)==before)
        folder,p=fixture('observer-disconnect');q=grants(cli(command(p),exe=fault)['result']);first=cli(command(q),(5,),fault,dict(DISKED_VERIFICATION_WORKER_TEST_EFFECT_DELAY='1'))
        observer=subprocess.Popen([str(fault),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=env)
        try:
            observer.stdin.write(canonical(frame('closed-watch','operation.watch',dict(operation_id=first['operation_id'],state_directory=p['state_directory'],follow_ms='2000'),[FEATURE]))+b'\n');observer.stdin.flush();event=json.loads(observer.stdout.readline());bundle.validate('urn:disked:schema:verification-operation-event:1',event)
            check('disconnect-follows-real-active-event',event['payload']['record']['state']['phase']!='finished');observer.stdout.close();observer.stdin.close();code=observer.wait(timeout=8);check('observer-output-disconnect-reported',code==4 and not observer.stderr.read())
        finally:
            if observer.poll() is None:observer.kill();observer.wait(timeout=5)
            for file in (observer.stdin,observer.stdout,observer.stderr):
                if not file.closed:file.close()
        done=finish(p,first,fault);independent(p,done);check('disconnected-observer-does-not-cancel-or-restart',done['result']['state']['outcome']['status']=='matched' and done['result']['state']['cancellation_observation']=='not_observed' and done['operation_id']==first['operation_id'])
        started=time.monotonic();safe=cli(command(p2),extra=dict(DISKED_VERIFICATION_TEST_GATE='missing-event',DISKED_VERIFICATION_COMMAND_TEST_OVERSIZED_REPLY='1',DISKED_VERIFICATION_WORKER_TEST_ADMISSION_DELAY='1'));check('product-ignores-private-controls',safe['status']=='completed' and time.monotonic()-started<2 and inert(p2))
        check('source-and-original-metadata-unchanged',src.read_bytes()==image.read_bytes()==expected and original=={f.name:f.read_bytes() for f in case.iterdir() if f.is_file()})
    report=dict(passed=True,checks=len(checks),observations=checks,native_journeys=journeys,samples=samples,scope='Actual Windows ordinary-file CLI/stdio/GUI/TUI/shell prepare/execute/watch, occupied callback, late GUI view, observer disconnect, cancellation, retention and reply-bound faults. No full platform/storage or custody qualification.',owner_accepted=False,source_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root,text=True).strip(),source_dirty=bool(subprocess.check_output(['git','status','--porcelain'],cwd=root,text=True)))
    if a.evidence:a.evidence.parent.mkdir(parents=True,exist_ok=True);a.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,checks=len(checks),samples=len(samples),native_journeys=len(journeys))))
if __name__=='__main__':main()
