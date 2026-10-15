"""Exact reviewed routing under unknown acquisition/extraction responses; generated files only."""
import argparse,copy,ctypes as C,json,os,queue,subprocess,sys,threading,time,uuid
from pathlib import Path
from gui_fixture import Gui,wait
from acquisition_console_fixture import run as console_run
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,digest,source_bytes,fixture_directory,K
from test_fat_content import fixture as fat_fixture

def main():
    ap=argparse.ArgumentParser()
    for name in ('product','fault','probe'):ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path);a=ap.parse_args()
    root=a.root.resolve();product=a.product.resolve();fault=a.fault.resolve();probe=a.probe.resolve()
    env={k:v for k,v in os.environ.items() if not k.startswith('DISKED_')};records=[];responses=[]
    def check(name,condition,**values):assert condition,(name,values);records.append(dict(name=name,passed=True,**values))
    def call(command,parameters,oversized=False):
        raw=canonical(dict(mode='oversized-unresolved' if oversized else 'unresolved',command=command,parameters=parameters));p=subprocess.run([str(probe)],input=raw,capture_output=True,cwd=root,env=env,timeout=12)
        assert p.returncode==6 and not p.stderr,(p.returncode,p.stdout,p.stderr)
        value=json.loads(p.stdout);check('pure-unresolved',value['status']=='unknown' and value['request_id']=='probe',input_sha256=digest(raw),output_sha256=digest(p.stdout));return value
    def cli(args,extra=None,exe=product,exits=(0,)):
        started=time.monotonic();p=subprocess.run([str(exe),'--json',*args],capture_output=True,cwd=root,env=dict(env,**(extra or {})),timeout=15)
        assert p.returncode in exits and not p.stderr,(args,p.returncode,p.stdout,p.stderr)
        return json.loads(p.stdout),time.monotonic()-started
    def args(command,p):
        prefix=['image','acquire'] if command=='image.acquire' else ['filesystem','extract']
        if p['phase']=='prepare':
            result=prefix+['prepare',p['source'],p['destination'],'--map',p['map'],'--state-dir',p['state_directory']]
            if 'logical_source' in p:result+=['--selection-json',canonical(p['logical_source']).decode()]
            return result
        result=prefix+['execute','--definition-json',canonical(p['definition']).decode(),'--definition-digest',p['definition_digest']]
        for k in ('source_read','destination_write','map_write','host_effects'):
            if p['allow_'+k]:result+=['--allow-'+k.replace('_','-')]
        return result
    def no_effects(p):return not Path(p['destination']).exists() and not Path(p['map']).exists() and not list(Path(p['state_directory']).iterdir())
    def expected(value,store,digest_value,kind='acquisition-execution'):
        result=value['result'];check('exact-unknown-routing',value['status']=='unknown' and value['operation_id'] is None and result['request_state']=='unresolved' and result['request_kind']==kind and result.get('state_directory')==store and result.get('definition_digest')==digest_value and 'scope' not in result,result=result)
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    K.CreateEventW.argtypes=[C.c_void_p,C.c_int,C.c_int,C.c_wchar_p];K.CreateEventW.restype=C.c_void_p
    K.SetEvent.argtypes=[C.c_void_p];K.SetEvent.restype=C.c_int
    with fixture_directory(scratch) as owned:
        for logical in (False,True):
            folder=owned/('logical' if logical else 'raw');folder.mkdir();state=folder/'state';state.mkdir();path=folder/'source.img'
            command='filesystem.extract' if logical else 'image.acquire'
            prep=dict(phase='prepare',source=str(path),destination=str(folder/'copy.bin'),map=str(folder/'copy.map'),state_directory=str(state))
            if logical:
                v,_=fat_fixture();v.write(path)
                inspection,_=cli(['image','inspect',str(path),'--view','fat','--volume-offset',str(v.offset),'--volume-bytes',str(v.length)])
                prep['logical_source']=next(row['extraction_selector'] for row in inspection['result']['observation']['nodes']['items'] if row['kind']=='file')
            else:path.write_bytes(source_bytes(65537))
            before=digest(path.read_bytes());prepared,_=cli(args(command,prep));review=prepared['result']
            execute=dict(phase='execute',definition=review['definition'],definition_digest=review['definition_digest'],**{'allow_'+k:True for k in ('source_read','destination_write','map_write','host_effects')})
            expected(call(command,execute),str(state),review['definition_digest'])
            p=call(command,prep);expected(p,str(state),None,'acquisition-preparation')
            oversized=call(command,execute,True);check('oversized-no-routing','state_directory' not in oversized['result'] and 'definition_digest' not in oversized['result'])
            for action in ('digest','schema','options','source-end','store-type','missing','wrong-command'):
                selected=copy.deepcopy(execute);target=command
                if action=='digest':selected['definition_digest']='sha256:'+'0'*64
                elif action=='missing':del selected['definition']
                elif action=='wrong-command':target='image.acquire' if logical else 'filesystem.extract'
                else:
                    if action=='schema':selected['definition']['schema']='unknown'
                    elif action=='options':selected['definition']['request']['chunk_bytes']='4096' if selected['definition']['plan']['chunk_bytes']!='4096' else '65536'
                    elif action=='source-end':selected['definition']['plan']['resources']['source']['end']='-1'
                    else:selected['definition']['store']['path']=5
                    selected['definition_digest']=digest(canonical(selected['definition']))
                out=call(target,selected);check('invalid-definition-no-reviewed-routing','state_directory' not in out['result'] and 'definition_digest' not in out['result'],case=action,logical=logical)
            # No re-opening can be required to retain this historical routing.
            path.unlink();state.rmdir()
            expected(call(command,execute),str(state),review['definition_digest'])
            state.mkdir()
            if logical:v.write(path)
            else:path.write_bytes(source_bytes(65537))
            # A missing private gate throws before provider entry in this fault
            # product. The async GUI/TUI/shell fallback must keep the same route.
            missing=dict(DISKED_IMAGE_TEST_GATE='Local\\DiskEdMissingGate-'+uuid.uuid4().hex)
            p,elapsed=cli(args(command,execute),missing,fault,(6,));expected(p,str(state),review['definition_digest']);responses.append(dict(frontend='cli-throw',command=command,response=p,seconds=elapsed))
            original=os.environ.get('DISKED_IMAGE_TEST_GATE');os.environ.update(missing)
            try:
                ui=Gui(fault,['--gui',*args(command,execute)],render=True)
                try:
                    ui.click(109);ui.click(110);value=wait(lambda:ui.details() if ui.details().get('schema')=='org.disked.response/1' else None)
                    expected(value,str(state),review['definition_digest']);responses.append(dict(frontend='gui',command=command,response=value))
                finally:ui.close();assert not ui.error
                for frontend in ('tui','shell'):
                    input=folder/(frontend+'-input.json');output=folder/(frontend+'-output.json');input.write_bytes(canonical(dict(parameters=execute,argv=args(command,execute))))
                    startup=subprocess.STARTUPINFO();startup.dwFlags=1;startup.wShowWindow=0
                    child=subprocess.run([sys.executable,str(Path(__file__).resolve()),'--console-case',str(fault),str(input),str(output),frontend],cwd=root,env=os.environ.copy(),timeout=60,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
                    report=json.loads(output.read_bytes());assert child.returncode==0,report
                    assert 'fixture_error' not in report,report
                    expected(report['response'],str(state),review['definition_digest']);responses.append(dict(frontend=frontend,command=command,response=report['response']))
            finally:
                if original is None:os.environ.pop('DISKED_IMAGE_TEST_GATE',None)
                else:os.environ['DISKED_IMAGE_TEST_GATE']=original
            gate='Local\\DiskEdAcquisitionRoute-'+uuid.uuid4().hex;entered=K.CreateEventW(None,True,False,gate+'.entered');release=K.CreateEventW(None,True,False,gate+'.release');assert entered and release
            process=None
            try:
                process=subprocess.Popen([str(fault),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=root,env=dict(env,DISKED_IMAGE_TEST_GATE=gate))
                inbox=queue.Queue()
                def read():
                    for line in process.stdout:inbox.put(line)
                    inbox.put(None)
                thread=threading.Thread(target=read,daemon=True);thread.start()
                def exchange(id,cmd,parameters):
                    frame=dict(schema='org.disked.request/1',request_id=id,command=cmd,parameters=parameters,required_features=[])
                    started=time.monotonic();process.stdin.write(canonical(frame)+b'\n');process.stdin.flush();raw=inbox.get(timeout=8);assert raw is not None
                    result=json.loads(raw);assert result['request_id']==id;return result,time.monotonic()-started
                value,elapsed=exchange('pending','image.acquire' if not logical else 'filesystem.extract',execute)
                expected(value,str(state),review['definition_digest']);check('original-wait-retained',3.8<=elapsed<6,seconds=elapsed)
                check('actual-gate-entered',K.WaitForSingleObject(entered,0)==0)
                cached,_=exchange('cached','command.list',{});check('discovery-remains-responsive',cached['status']=='completed')
                busy,_=exchange('busy',command,execute);check('pending-slot-not-reused',busy['status']=='refused' and busy['diagnostics'][0]['code']=='request_resource_limit')
                responses.append(dict(frontend='stdio-timeout',command=command,response=value,seconds=elapsed))
                # End the owned client while the gate still excludes provider
                # entry. Never release a granted writer merely to finish a test.
                process.stdin.close();assert process.wait(timeout=5)==6;thread.join(timeout=1);assert not process.stderr.read()
            finally:
                if process is not None and process.poll() is None:process.kill();process.wait(timeout=5)
                K.SetEvent(release)
                K.CloseHandle(entered);K.CloseHandle(release)
            check('all-selected-effects-absent',no_effects(prep));check('source-unchanged',digest(path.read_bytes())==before)
        for op in ('operation.inspect','operation.cancel.request','operation.watch'):
            selected='image-op:'+'1'*32;p=dict(operation_id=selected,state_directory='C:\\generated-state')
            value=call(op,p);check('observation-routing',value['operation_id']==selected and value['result']['request_kind']=='operation-observation' and value['result'].get('state_directory')==p['state_directory'])
        value=call('operation.inspect',dict(operation_id='image-op:invalid',state_directory='C:\\generated-state'))
        check('invalid-operation-not-invented',value['operation_id'] is None)
    report=dict(passed=True,checks=len(records),observations=records,responses=responses,scope='Pure raw/logical reviewed routing and five native frontend fallbacks; no acquired writer is retried or storage execution admitted.')
    if a.evidence:a.evidence.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(dict(passed=True,checks=len(records),frontends=len(responses))))
if __name__=='__main__':
    if len(sys.argv)>1 and sys.argv[1]=='--console-case':
        report={};code=0
        try:
            selected=json.loads(Path(sys.argv[3]).read_bytes());console_run(sys.argv[2],selected['parameters'],report,sys.argv[5],selected['argv'])
        except Exception as error:report['fixture_error']=str(error);code=1
        Path(sys.argv[4]).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n');raise SystemExit(code)
    main()
