"""Actual shared FAT extraction, exact review/grants and independent byte oracles."""
import argparse,copy,json,os,subprocess,sys,time
from pathlib import Path
from gui_fixture import Gui,wait
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_fat_content import fixture
from test_acquisition_worker import canonical,digest,map_check,fixture_directory,owned_process,K

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from support.tempdir import fixture_parent as managed_parent, managed_directory

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ('exe','gui','tui','fat','output'):ap.add_argument('--'+name,type=Path,required=True)
    a=ap.parse_args();exe=str(a.exe.resolve());records=[];copies=[];passed=False
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_ACQ_','DISKED_TEST_','DISKED_FAT_'))}
    def record(name,**v):records.append(dict(name=name,**v));print('PASS '+name,flush=True)
    def cli(args,exits=(0,),name='cli'):
        result=subprocess.run([exe,'--json',*args],capture_output=True,env=env,timeout=30)
        assert result.returncode in exits and not result.stderr,(name,result.returncode,result.stdout,result.stderr)
        value=json.loads(result.stdout);record(name,exit_code=result.returncode,output_sha256=digest(result.stdout));return value
    def wire(command,p,exits=(0,),features=None,ndjson=False):
        request=dict(schema='org.disked.request/1',request_id='extract:req',command=command,parameters=p,required_features=features or [])
        result=subprocess.run([exe,'protocol','serve','--format','ndjson' if ndjson else 'json'],input=canonical(request)+(b'\n' if ndjson else b''),capture_output=True,env=env,timeout=30)
        assert result.returncode in exits and not result.stderr,(command,result.returncode,result.stdout,result.stderr)
        values=[json.loads(line) for line in result.stdout.splitlines()];record('protocol-'+command,exit_code=result.returncode,frames=len(values),output_sha256=digest(result.stdout));return values
    def argv(p):
        out=['filesystem','extract',p['phase']]
        if p['phase']=='prepare':
            out += [p['source'],p['destination'],'--map',p['map'],'--state-dir',p['state_directory'],'--selection-json',canonical(p['logical_source']).decode()]
            if 'chunk_bytes' in p:out += ['--chunk-bytes',p['chunk_bytes']]
            if p.get('resume'):out += ['--resume']
        else:
            out += ['--definition-json',canonical(p['definition']).decode(),'--definition-digest',p['definition_digest']]
            for k in ('source_read','destination_write','map_write','host_effects'):
                if p.get('allow_'+k):out += ['--allow-'+k.replace('_','-')]
        return out
    def grants(review):return dict(phase='execute',definition=review['definition'],definition_digest=review['definition_digest'],allow_source_read=True,allow_destination_write=True,allow_map_write=True,allow_host_effects=True)
    def no_effects(p):
        assert not Path(p['destination']).exists() and not Path(p['map']).exists()
        assert not list(Path(p['state_directory']).iterdir())
    def finish(p,first,data):
        assert first['status'] in ('completed','accepted_running') and first['operation_id']
        # Match the existing raw acquisition progress policy. A progressing
        # durable copy is not a failed/stalled writer merely at total30s.
        end=time.monotonic()+90;progress_end=time.monotonic()+30;checkpoint=-1
        while True:
            out=cli(['operation','inspect',first['operation_id'],'--state-dir',p['state_directory']],name='observe')
            assert out['result']['scope']=='ordinary-local-fat-file-extraction'
            state=out['result']['state']
            if state['phase']=='finished':break
            current=int(state['checkpoint_bytes']);assert current>=checkpoint,state
            now=time.monotonic()
            if current>checkpoint:checkpoint=current;progress_end=now+30
            assert now<end and now<progress_end,('retain unfinished worker dependencies',out)
            time.sleep(.02)
        h=owned_process(state,exe)
        if h:
            try:assert K.WaitForSingleObject(h,2000)==0
            finally:K.CloseHandle(h)
        assert state['quiescent'] and state['outcome']['status']=='completed',out
        assert Path(p['destination']).read_bytes()==data
        map_check(Path(p['map']),data)
        copies.append(dict(bytes=len(data),sha256=digest(data),operation_id=first['operation_id']))
        record('verified-copy',bytes=len(data),sha256=digest(data))
        return out
    scratch=managed_parent();scratch.mkdir(exist_ok=True)
    try:
        with fixture_directory(scratch) as root:
            serial=0
            def setup(bits=12,large=False,empty=False,cancellable=False):
                nonlocal serial
                serial+=1;folder=root/str(serial);folder.mkdir();state=folder/'state';state.mkdir()
                kw=dict(unit=512,per=128,chain=tuple(range(3,263))) if cancellable else dict(unit=4096,per=16,chain=(3,8,5,11,7,15,4,20,9,24,6,28,10,32,12,35,13,39)) if large else dict(chain=(),size=0) if empty else {}
                v,data=fixture(bits,**kw);source=folder/'源.img';v.write(source)
                params=dict(phase='prepare',source=str(source),destination=str(folder/'输出.bin'),map=str(folder/'copy.map'),state_directory=str(state),chunk_bytes='65536' if cancellable else '1048576' if large else '4096')
                inspection=cli(['image','inspect',str(source),'--view','fat','--volume-offset',str(v.offset),'--volume-bytes',str(v.length)],name='selection')
                rows=inspection['result']['observation']['nodes']['items'];selector=next(r['extraction_selector'] for r in rows if r['kind']=='file')
                assert selector['node_id']=='1' and selector['expected_file_bytes']==str(len(data))
                raw=canonical(dict(op='file',path=str(source),offset=str(v.offset),length=str(v.length),mode='frame'))+b'\n'
                captured=subprocess.run([str(a.fat.resolve())],input=raw,capture_output=True,timeout=30,env=env)
                assert captured.returncode==0 and not captured.stderr
                exact=json.loads(captured.stdout)['frame']['result']['observation'];exact['capture_epoch']='0'
                assert selector['metadata_digest']==digest(canonical(exact))
                params['logical_source']=selector;return folder,params,data,v
            listing=cli(['command','list']);assert any(x['id']=='filesystem.extract' and x['availability']=='available' for x in listing['result']['commands'])
            cli(['filesystem','extract','--help'],name='static-help')
            for bits in (12,16,32):
                for empty in (False,True):
                    folder,p,data,v=setup(bits,empty=empty);before=digest(Path(p['source']).read_bytes())
                    prepared=cli(argv(p),name='prepare')['result'];no_effects(p)
                    assert not prepared['execution_admitted'] and prepared['scope']=='ordinary-local-fat-file-extraction'
                    assert prepared['definition']['schema']=='org.disked.acquisition-worker-definition/2'
                    assert prepared['definition']['request']['logical_source']==prepared['definition']['plan']['logical_source']==p['logical_source']
                    finish(p,cli(argv(grants(prepared)),(0,5),name='execute'),data)
                    assert digest(Path(p['source']).read_bytes())==before
            folder,p,data,v=setup(16,large=True);assert len(data)>1048576
            prepared=wire('filesystem.extract',p)[0]['result'];no_effects(p)
            finish(p,wire('filesystem.extract',grants(prepared),(0,5))[0],data)
            # Logical operations retain the existing event/reconnect/cancellation domain.
            completed=cli(['operation','inspect',copies[-1]['operation_id'],'--state-dir',p['state_directory']])
            watch=wire('operation.watch',dict(operation_id=copies[-1]['operation_id'],state_directory=p['state_directory']),features=['org.disked.acquisition-operation-events/1'],ndjson=True)
            events=[r for r in watch if r['schema']=='org.disked.event/1'];assert events
            assert watch[-1]['result']['scope']=='ordinary-local-fat-file-extraction'
            assert all(r['operation_id']==copies[-1]['operation_id'] for r in watch)
            late=wire('operation.cancel.request',dict(operation_id=copies[-1]['operation_id'],state_directory=p['state_directory']))[0]
            assert late['result']['cancellation_request']=='too_late' and late['result']['state']['outcome']==completed['result']['state']['outcome']
            folder,p,data,v=setup(cancellable=True);prepared=cli(argv(p))['result'];first=cli(argv(grants(prepared)),(0,5));end=time.monotonic()+30
            op=dict(operation_id=first['operation_id'],state_directory=p['state_directory'])
            while True:
                observed=wire('operation.inspect',op)[0]['result']['state'];checkpoint=int(observed['checkpoint_bytes'])
                if observed['phase']=='active' and 0<checkpoint<len(data):break
                assert observed['phase']!='finished' and time.monotonic()<end,'partial checkpoint required for real cancellation/resume'
                time.sleep(.02)
            wire('operation.cancel.request',op);end=time.monotonic()+30
            while True:
                observed=wire('operation.inspect',op)[0]['result']['state']
                if observed['phase']=='finished':break
                assert time.monotonic()<end;time.sleep(.02)
            assert observed['outcome']['status']=='paused' and int(observed['checkpoint_bytes'])>=checkpoint
            h=owned_process(observed,exe)
            if h:
                try:assert K.WaitForSingleObject(h,2000)==0
                finally:K.CloseHandle(h)
            state=folder/'resume-state';state.mkdir();resumed={**p,'resume':True,'state_directory':str(state)}
            review=cli(argv(resumed))['result'];finish(resumed,cli(argv(grants(review)),(0,5)),data)
            record('real-cancel-resume',original_operation=op['operation_id'],observed_prefix=checkpoint)
            folder,p,data,v=setup();prepared=cli(argv(p))['result'];g=grants(prepared)
            for k in ('allow_source_read','allow_destination_write','allow_map_write','allow_host_effects'):
                bad=copy.deepcopy(g);bad[k]=False;wire('filesystem.extract',bad,(2,3));no_effects(p)
            for schema in ('org.disked.acquisition-worker-definition/1','unknown'):
                bad=copy.deepcopy(g);bad['definition']['schema']=schema;bad['definition_digest']=digest(canonical(bad['definition']));wire('filesystem.extract',bad,(2,3));no_effects(p)
            wire('image.acquire',g,(2,3));no_effects(p)
            bad=copy.deepcopy(g);bad['definition']['request']['logical_source']['node_id']='0';bad['definition_digest']=digest(canonical(bad['definition']));wire('filesystem.extract',bad,(2,3));no_effects(p)
            for key,value in [('node_id','128'),('volume_offset','18446744073709551616'),('expected_file_bytes','1'),('metadata_digest','sha256:'+'0'*64)]:
                bad=copy.deepcopy(p);bad['logical_source'][key]=value;wire('filesystem.extract',bad,(2,3));no_effects(p)
            wire('filesystem.extract',{**p,'retry_limit':'1'},(2,3));no_effects(p)
            wire('filesystem.extract',{**p,'allow_host_effects':True},(2,3));no_effects(p)
            raw=Path(p['source']).read_bytes();Path(p['source']).write_bytes(raw)
            wire('filesystem.extract',p,(3,));no_effects(p)
            folder,p,data,v=setup();Path(p['destination']).write_bytes(b'existing');wire('filesystem.extract',p,(3,));assert Path(p['destination']).read_bytes()==b'existing'
            folder,p,data,v=setup();bad={**p,'destination':p['source']};wire('filesystem.extract',bad,(3,));no_effects(p)
            nonbasic=cli(['image','inspect',p['source'],'--view','fat','--volume-offset',str(v.offset),'--volume-bytes',str(v.length),'--auxiliary-checks','yes'])
            assert all('extraction_selector' not in r for r in nonbasic['result']['observation']['nodes']['items'])
            # Descriptor-driven model review keeps grants explicit in both interfaces.
            prepared=cli(argv(p))['result'];g=grants(prepared)
            for kind,probe in [('gui',a.gui),('tui',a.tui)]:
                review=dict(op='review') if kind=='gui' else dict(op='key',key='f9');submit=dict(op='submit') if kind=='gui' else dict(op='key',key='f9')
                for params in (p,g):
                    steps=[dict(op='stage',command='filesystem.extract',parameters=params),review,submit]
                    result=subprocess.run([str(probe.resolve()),'--acquisition-forms'],input=b''.join(canonical(s)+b'\n' for s in steps),capture_output=True,env=env,timeout=15)
                    assert result.returncode==0 and not result.stderr
                    values=[json.loads(line) for line in result.stdout.splitlines()]
                    assert values[-1]['state']['last_outcome']['result'] and values[-1]['state']['last_outcome']['result']['test_parameters']==params,values[-1]['state']
                    record(kind+'-model-review',phase=params['phase'],output_sha256=digest(result.stdout))
                no_effects(p)
            # Actual native windows and owned consoles run preparation and extraction.
            for frontend in ('gui','tui','shell'):
                folder,p,data,v=setup();prepared=None
                for phase in ('prepare','execute'):
                    params=p if phase=='prepare' else grants(prepared)
                    if frontend=='gui':
                        ui=Gui(Path(exe),['--gui',*argv(params)],render=True)
                        try:
                            no_effects(p);ui.click(109);assert ui.details()['reviewed'];no_effects(p)
                            ui.click(110);reply=wait(lambda:ui.details() if ui.details().get('schema')=='org.disked.response/1' else None)
                        finally:ui.close()
                        assert ui.code==0 and not ui.error
                    else:
                        inp=folder/(phase+'-input.json');out=folder/(phase+'-console.json');inp.write_bytes(canonical(dict(parameters=params,command=argv(params))))
                        startup=subprocess.STARTUPINFO();startup.dwFlags=1;startup.wShowWindow=0
                        proc=subprocess.run([sys.executable,str(Path(__file__).with_name('fat_extraction_console_fixture.py')),exe,str(inp),str(out),frontend],env=env,timeout=40,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
                        observed=json.loads(out.read_bytes());assert proc.returncode==0,observed;reply=observed['response'];assert all(observed['restored'].values())
                    record('native-'+frontend,phase=phase,status=reply['status'])
                    if phase=='prepare':prepared=reply['result'];no_effects(p)
                    else:finish(p,reply,data)
            passed=True
    finally:
        a.output.write_text(json.dumps(dict(passed=passed,checks=len(records),records=records,verified_copies=copies,scope='Actual shared prototype complete mapped FAT byte extraction; no physical/release qualification'),indent=2)+'\n',encoding='utf-8',newline='\n')
    assert passed

if __name__=='__main__':main()
