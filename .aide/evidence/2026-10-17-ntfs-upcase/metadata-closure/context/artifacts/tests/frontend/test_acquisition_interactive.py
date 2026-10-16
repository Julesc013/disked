"""Structured shell copying and native rendering of the full 64-event profile.

Dense history is explicitly synthetic, derived from an actual completed worker.
Only generated owned files are changed, after that worker has demonstrably exited.
"""
import argparse,copy,hashlib,json,os,subprocess,sys,time
from pathlib import Path
from gui_fixture import Gui,wait
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,digest,source_bytes,map_check,history_check,fixture_directory,owned_process,K

def quote(word):return '"'+word.replace('"','""')+'"'

def main():
    ap=argparse.ArgumentParser()
    for flag in ('exe','product','shell','reader'):ap.add_argument('--'+flag,type=Path,required=True)
    ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path)
    a=ap.parse_args();root=a.root.resolve()
    for flag in ('exe','product','shell','reader'):setattr(a,flag,getattr(a,flag).resolve())
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_ACQ_','DISKED_TEST_'))}
    observations=[];native=[];verified=[];producer=[]
    lifecycle={}
    def call(args,exe=a.exe,exits=(0,5)):
        p=subprocess.run([str(exe),'--json',*args],capture_output=True,cwd=root,env=env,timeout=15)
        assert p.returncode in exits and not p.stderr,(p.returncode,p.stdout,p.stderr)
        observations.append(dict(name='native-cli',exit_code=p.returncode,output_sha256=digest(p.stdout),passed=True))
        return json.loads(p.stdout),p.stdout
    def command(p):
        if p.get('phase')=='prepare':return ['image','acquire','prepare',p['source'],p['destination'],'--map',p['map'],'--state-dir',p['state_directory']]
        return ['image','acquire','execute','--definition-json',canonical(p['definition']).decode(),'--definition-digest',p['definition_digest'],
            '--allow-source-read','--allow-destination-write','--allow-map-write','--allow-host-effects']
    def console(frontend,p,folder,exe):
        input=folder/(frontend+'-input.json');output=folder/(frontend+'-output.json');input.write_bytes(canonical(p))
        startup=subprocess.STARTUPINFO();startup.dwFlags=1;startup.wShowWindow=0
        process=subprocess.run([sys.executable,str(Path(__file__).with_name('acquisition_console_fixture.py')),str(exe),str(input),str(output),frontend],
            cwd=root,env=env,timeout=90,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
        value=json.loads(output.read_bytes());assert process.returncode==0 and 'fixture_error' not in value,value
        native.append(value);return value['response']
    def models(steps):
        p=subprocess.run([str(a.shell),'--acquisition-forms'],input=b''.join(canonical(s)+b'\n' for s in steps),capture_output=True,cwd=root,env=env,timeout=20)
        assert p.returncode==0 and not p.stderr
        values=[json.loads(r) for r in p.stdout.splitlines()];assert len(values)==len(steps) and all('error' not in v for v in values),values
        observations.append(dict(name='shell-model',steps=len(steps),output_sha256=digest(p.stdout),passed=True));return values
    def key(name,text=None,repeat=False):
        v=dict(op='key',key=name,repeat=repeat)
        if text is not None:v['text']=text
        return v
    def no_effects(p):assert not Path(p['destination']).exists() and not Path(p['map']).exists() and not list(Path(p['state_directory']).iterdir())
    def wire(parameters,exits=(0,5),**extra):
        request=dict(schema='org.disked.request/1',request_id='public-acquisition',command='image.acquire',parameters=parameters,required_features=[])
        request.update(extra);raw=canonical(request)+b'\n'
        p=subprocess.run([str(a.product),'protocol','serve','--format','json'],input=raw,capture_output=True,cwd=root,env=env,timeout=15)
        assert p.returncode in exits and not p.stderr,(p.returncode,p.stdout,p.stderr)
        response=json.loads(p.stdout);assert response['request_id']=='public-acquisition'
        observations.append(dict(name='public-stdio',exit_code=p.returncode,input_sha256=digest(raw),output_sha256=digest(p.stdout),passed=True));return response
    def finish(p,first):
        # This is a completion/byte-integrity journey, not a 30-second transfer
        # performance contract. Per-chunk FlushFileBuffers can legitimately
        # exceed that total while durable checkpoints keep advancing. Retain
        # finite overall and no-progress limits; neither timeout permits replay
        # or cleanup of an unfinished worker's dependencies.
        end=time.monotonic()+90;progress_end=time.monotonic()+30;checkpoint=-1
        while True:
            value,_=call(['operation','inspect',first['operation_id'],'--state-dir',p['state_directory']]);state=value['result']['state']
            if state['phase']=='finished':break
            current=int(state['checkpoint_bytes']);assert current>=checkpoint,state
            now=time.monotonic()
            if current>checkpoint:checkpoint=current;progress_end=now+30
            assert now<end and now<progress_end,('retain unfinished worker dependencies',state)
            time.sleep(.02)
        h=owned_process(state,str(a.exe))
        if h:
            try:assert K.WaitForSingleObject(h,2000)==0
            finally:K.CloseHandle(h)
        data=Path(p['source']).read_bytes();assert data==source_bytes(len(data)) and Path(p['destination']).read_bytes()==data;map_check(Path(p['map']),data)
        rows=history_check(Path(p['state_directory'])/'acquisition.records')
        assert state['outcome']['status']=='completed' and state['quiescent']
        verified.append(dict(bytes=str(len(data)),sha256=digest(data),operation_id=first['operation_id']));return rows
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        def fixture(letters,size):
            folder=owned/('磁'*letters);folder.mkdir();state=folder/'state';state.mkdir();src=folder/'source.img'
            assert len(str(src))<=240;src.write_bytes(source_bytes(size))
            return folder,dict(phase='prepare',source=str(src),destination=str(folder/'copy.img'),map=str(folder/'copy.map'),state_directory=str(state))
        def grants(review):return dict(phase='execute',definition=review['definition'],definition_digest=review['definition_digest'],
            allow_source_read=True,allow_destination_write=True,allow_map_write=True,allow_host_effects=True)
        folder,p=fixture(70,65537);review=call(command(p))[0]['result'];g=grants(review);no_effects(p)
        line=' '.join(quote(w) for w in command(g));assert len(line.encode())>4096
        values=models([key('text',line),key('enter'),key('f9'),key('f9',repeat=True),dict(op='calls'),key('f9'),dict(op='calls')])
        assert values[4]==[] and values[-1]==[dict(command='image.acquire',parameters=g,revision='')]
        assert values[2]['view']=='review' and '"expected_revision": null' in '\n'.join(sum(values[2]['transcript'],[]))
        for bad in ('\n', 'x'*65537):
            values=models([key('text',line),key('f9'),key('text',bad),key('text',''),key('f9'),key('f9'),dict(op='calls')])
            assert values[-1]==[] and 'shell_rejected_definition_input' in values[-2]['notice']
        values=models([key('text',line),key('text','\n'),key('backspace'),key('text',line[-1]),key('f9'),key('f9'),dict(op='calls')])
        assert values[-1]==[dict(command='image.acquire',parameters=g,revision='')]
        # Use two duplicate members, rather than changing the reviewed contract.
        duplicate=canonical(g['definition']).decode().replace('{','{"schema":"duplicate",',1)
        badline=' '.join(quote(w) for w in [*command(g)[:4],duplicate,*command(g)[5:]])
        values=models([key('text',badline),key('f9'),key('f9'),dict(op='calls')]);assert values[-1]==[]
        no_effects(p)
        first=console('shell',p,folder,a.exe);assert first['status']=='completed';no_effects(p)
        first=console('shell',grants(first['result']),folder,a.exe);finish(p,first)

        # Public producer discovery and protocol effects use the same executable.
        discovery,_=call(['command','list'],a.product,(0,))
        item=next(c for c in discovery['result']['commands'] if c['id']=='image.acquire')
        assert item['availability']=='available' and item['reason']=='ordinary_local_raw_file_acquisition'
        folder,p=fixture(80,65537);review=wire(p)['result'];g=grants(review);no_effects(p)
        missing=copy.deepcopy(g);del missing['allow_host_effects'];wire(missing,(2,));no_effects(p)
        wrong=copy.deepcopy(g);wrong['definition_digest']='sha256:'+'0'*64
        assert wire(wrong,(3,))['diagnostics'][0]['code']=='acquisition_worker_grant';no_effects(p)
        assert wire(g,(2,),expected_revision='sha256:'+'0'*64)['diagnostics'][0]['code']=='unexpected_revision';no_effects(p)
        wire(g,(3,),required_features=['unknown']);no_effects(p)
        first=wire(g);finish(p,first)
        old={f.name:f.read_bytes() for f in Path(p['state_directory']).iterdir()}
        replay=wire(g,(0,));assert replay['status']=='completed' and replay['operation_id']==first['operation_id']
        assert old=={f.name:f.read_bytes() for f in Path(p['state_directory']).iterdir()}
        lifecycle['stdio_no_replay']=True
        build,_=call(['build','inspect'],a.product,(0,))
        assert build['result']['acquisition_provider']==g['definition']['plan']['resources']['provider']['identity']
        role_before={f.relative_to(folder).as_posix():f.read_bytes() for f in folder.rglob('*') if f.is_file()}
        for args in [[],['1','2','3','4']]:
            process=subprocess.run([str(a.product),'__disked_acquisition_worker',*args],capture_output=True,cwd=folder,env=env,timeout=8)
            assert process.returncode==199 and not process.stdout and not process.stderr
        assert role_before=={f.relative_to(folder).as_posix():f.read_bytes() for f in folder.rglob('*') if f.is_file()}
        lifecycle['worker_role_requires_exact_capabilities']=True

        # A real ordinary-file worker is cancelled, then its verified checkpoint
        # is resumed through a fresh public definition and fresh metadata store.
        folder,p=fixture(60,16777216);review=call(command(p),a.product,(0,))[0]['result'];g=grants(review)
        first,_=call(command(g),a.product);op=dict(operation_id=first['operation_id'],state_directory=p['state_directory'])
        # The public worker may see cancellation before its first chunk. Observe
        # a real partial checkpoint first so this journey qualifies prefix resume.
        end=time.monotonic()+30
        while True:
            observed,_=call(['operation','inspect',op['operation_id'],'--state-dir',op['state_directory']],a.product,(0,))
            before_cancel=observed['result']['state'];observed_checkpoint=int(before_cancel['checkpoint_bytes'])
            if 0<observed_checkpoint<16777216 and before_cancel['phase']=='active':break
            assert before_cancel['phase']!='finished' and time.monotonic()<end,'retain unfinished worker dependencies'
            time.sleep(.02)
        cancelled,_=call(['operation','cancel',op['operation_id'],'--state-dir',op['state_directory']],a.product,(0,))
        end=time.monotonic()+30
        while True:
            value,_=call(['operation','inspect',op['operation_id'],'--state-dir',op['state_directory']],a.product,(0,));state=value['result']['state']
            if state['phase']=='finished':break
            assert time.monotonic()<end;time.sleep(.02)
        h=owned_process(state,str(a.product))
        if h:
            try:assert K.WaitForSingleObject(h,2000)==0
            finally:K.CloseHandle(h)
        assert cancelled['result']['cancellation_request']=='requested' and state['outcome']['status']=='paused',state
        checkpoint=int(state['checkpoint_bytes']);assert 0<checkpoint<16777216
        assert Path(p['destination']).read_bytes()==Path(p['source']).read_bytes()[:checkpoint]
        history_check(Path(p['state_directory'])/'acquisition.records')
        late,_=call(['operation','cancel',op['operation_id'],'--state-dir',op['state_directory']],a.product,(0,));assert late['result']['cancellation_request']=='too_late'
        resume_state=folder/'resume';resume_state.mkdir();resume=dict(p,state_directory=str(resume_state),resume=True)
        prepared,_=call([*command(resume),'--resume'],a.product,(0,));again=grants(prepared['result'])
        assert again['definition']['plan']['capture_epoch']==g['definition']['plan']['capture_epoch']
        resumed,_=call(command(again),a.product);finish(resume,resumed)
        lifecycle['public_checkpoint_cancel_resume']=dict(observed_before_cancel=str(observed_checkpoint),checkpoint_bytes=str(checkpoint),original_operation=op['operation_id'],resumed_operation=resumed['operation_id'])

        folder,p=fixture(100,2097152);g=grants(call(command(p))[0]['result']);first,_=call(command(g));original=finish(p,first)
        original_bytes=(Path(p['state_directory'])/'acquisition.records').read_bytes()
        assert 2<=len(original)<64 and original[0]['state']['phase']=='active'
        rows=[copy.deepcopy(original[0]) for _ in range(64-len(original))]+copy.deepcopy(original);previous='0'*64
        for sequence,row in enumerate(rows,1):
            row['state']['sequence']=str(sequence);row['previous']=previous;row.pop('digest',None)
            row['digest']=hashlib.sha256(canonical(row)).hexdigest();previous=row['digest']
        records=Path(p['state_directory'])/'acquisition.records';records.write_bytes(b''.join(canonical(row)+b'\n' for row in rows))
        assert history_check(records)==rows
        dense=dict(scope='synthetic-expanded-history-after-actual-worker-exit',original_records=len(original),expanded_records=len(rows),
            original_sha256=digest(original_bytes),expanded_sha256=digest(records.read_bytes()))
        op=dict(operation_id=first['operation_id'],state_directory=p['state_directory'])
        response,raw=call(['operation','watch',op['operation_id'],'--state-dir',op['state_directory']],a.product,(0,))
        assert len(raw)>65536,'fixture must exceed the ordinary response slot'
        def verify(response):
            assert response['status']=='completed' and response['operation_id']==op['operation_id']
            assert response['result']['last_sequence']=='64' and response['result']['last_digest']==rows[-1]['digest']
            events=response['result']['events'];assert len(events)==64 and [e['payload']['record'] for e in events]==rows
            producer.extend(events)
        verify(response);dense['response_bytes']=len(raw)
        gui=Gui(a.product,['--gui','operation','watch',op['operation_id'],'--state-dir',op['state_directory']],render=True)
        try:
            gui.click(109);assert gui.details()['reviewed'] and gui.details()['expected_revision'] is None
            gui.click(110);response=wait(lambda:gui.details() if gui.details().get('schema')=='org.disked.response/1' else None)
            verify(response);native.append(dict(frontend='gui',response=response,observation=gui.observation()))
            if a.evidence:gui.screenshot(a.evidence.parent/'gui-acquisition-watch-64-events.png')
        finally:gui.close()
        assert gui.code==0 and not gui.error
        for frontend in ('tui','shell'):verify(console(frontend,op,folder,a.product))
        request=dict(op='read',definition=g['definition'],operation_id=op['operation_id'],events=response['result']['events'])
        result=subprocess.run([str(a.reader)],input=canonical(request)+b'\n',capture_output=True,cwd=root,timeout=15)
        assert result.returncode==0 and not result.stderr and all(r['accepted'] for r in json.loads(result.stdout)['results'])
        assert records.read_bytes()==b''.join(canonical(row)+b'\n' for row in rows),'observation modified retained records'
    report=dict(passed=True,public_copy_admitted=True,checks=len(observations),observations=observations,native_journeys=native,
        verified_copies=verified,dense_history=dense,producer_events=producer,lifecycle=lifecycle)
    if a.evidence:a.evidence.write_bytes(json.dumps(report,indent=2).encode()+b'\n')
    print('PASS acquisition interactive:',len(observations),'checks;',len(native),'native journeys;',len(verified),'verified copies; synthetic 64-event response',dense['response_bytes'],'bytes')

if __name__=='__main__':main()
