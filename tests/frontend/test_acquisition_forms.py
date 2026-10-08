"""Phase-specific shared forms and actual native Windows acquisition journeys.

Product image.acquire stays unavailable; copying uses the marked test variant.
All media and outputs are created and owned by this finite test harness.
"""
import argparse
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from gui_fixture import Gui,wait,send
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from test_acquisition_worker import canonical,digest,source_bytes,map_check,history_check,fixture_directory,owned_process,K


def main():
    ap=argparse.ArgumentParser()
    for name in ('exe','product','gui','tui'):ap.add_argument('--'+name,type=Path,required=True)
    ap.add_argument('--root',type=Path,default=Path('.'));ap.add_argument('--evidence',type=Path)
    a=ap.parse_args();a.exe=a.exe.resolve();a.product=a.product.resolve();root=a.root.resolve()
    env={k:v for k,v in os.environ.items() if not k.startswith(('DISKED_ACQ_','DISKED_TEST_'))}
    observations=[];native=[];verified=[]
    def record(name,**fields):observations.append(dict(name=name,passed=True,**fields))
    def cli(argv,exits=(0,),product=False):
        p=subprocess.run([str(a.product if product else a.exe),'--json',*argv],capture_output=True,env=env,cwd=root,timeout=15)
        assert p.returncode in exits and not p.stderr,(argv,p.returncode,p.stdout,p.stderr)
        record('native-cli',exit_code=p.returncode,output_sha256=digest(p.stdout));return json.loads(p.stdout)
    def model(exe,steps):
        p=subprocess.run([str(exe.resolve()),'--acquisition-forms'],input=b''.join(canonical(s)+b'\n' for s in steps),
            capture_output=True,cwd=root,env=env,timeout=10)
        assert p.returncode==0 and not p.stderr
        values=[json.loads(row) for row in p.stdout.splitlines()];assert len(values)==len(steps)
        assert all('error' not in row for row in values),values
        record('model-journey',steps=len(steps),output_sha256=digest(p.stdout));return values
    def console(params,folder):
        input=folder/'console-input.json';output=folder/'console-output.json';input.write_bytes(canonical(params))
        startup=subprocess.STARTUPINFO();startup.dwFlags=1;startup.wShowWindow=0
        p=subprocess.run([sys.executable,str(Path(__file__).with_name('acquisition_console_fixture.py')),str(a.exe),str(input),str(output)],
            env=env,timeout=30,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup)
        report=json.loads(output.read_bytes());assert p.returncode==0 and 'fixture_error' not in report,report
        native.append(dict(frontend='tui',phase=params['phase'],**report));return report['response']
    scratch=root/'.aide-local';scratch.mkdir(exist_ok=True)
    with fixture_directory(scratch) as owned:
        def fixture(name):
            folder=owned/name/('owned-'+ '磁'*70);folder.mkdir(parents=True);state=folder/'state';state.mkdir()
            src=folder/'source.img';src.write_bytes(source_bytes(65537))
            return folder,dict(phase='prepare',source=str(src),destination=str(folder/'copy.img'),map=str(folder/'copy.map'),state_directory=str(state))
        def no_effects(p):
            assert not Path(p['destination']).exists() and not Path(p['map']).exists() and not list(Path(p['state_directory']).iterdir())
        def prep(p):return cli(['image','acquire','prepare',p['source'],p['destination'],'--map',p['map'],'--state-dir',p['state_directory']])['result']
        def grants(review):return dict(phase='execute',definition=review['definition'],definition_digest=review['definition_digest'],
            allow_source_read=True,allow_destination_write=True,allow_map_write=True,allow_host_effects=True)
        def finished(p,first):
            deadline=time.monotonic()+20
            while time.monotonic()<deadline:
                result=cli(['operation','inspect',first['operation_id'],'--state-dir',p['state_directory']])
                state=result['result']['state']
                if state['phase']=='finished':
                    h=owned_process(state,str(a.exe))
                    if h:
                        try:assert K.WaitForSingleObject(h,2000)==0
                        finally:K.CloseHandle(h)
                    expected=Path(p['source']).read_bytes();assert Path(p['destination']).read_bytes()==expected
                    map_check(Path(p['map']),expected);history_check(Path(p['state_directory'])/'acquisition.records')
                    assert state['outcome']['status']=='completed' and state['quiescent']
                    verified.append(dict(bytes=str(len(expected)),sha256=digest(expected),operation_id=first['operation_id']))
                    return result
                time.sleep(.02)
            raise AssertionError('owned copy has not finished; retain dependencies')

        folder,p=fixture('model');review=prep(p);g=grants(review);no_effects(p)
        assert len(canonical(g['definition']))>4096,'fixture must exercise structured editor beyond old limit'
        expected_prepare={'phase','source','destination','map','state_directory','resume','chunk_bytes','retry_limit','read_policy','substitution'}
        expected_execute={'phase','definition','definition_digest','allow_source_read','allow_destination_write','allow_map_write','allow_host_effects'}
        for kind,exe in [('gui',a.gui),('tui',a.tui)]:
            stage=lambda params:dict(op='stage',command='image.acquire',parameters=params)
            reviewstep=dict(op='review') if kind=='gui' else dict(op='key',key='f9')
            submit=dict(op='submit') if kind=='gui' else dict(op='key',key='f9')
            values=model(exe,[stage(p),reviewstep,submit]);assert set(values[0]['state']['parameters'])==expected_prepare
            assert values[-1]['state']['last_outcome']['result']['test_parameters']==p
            values=model(exe,[stage(g),reviewstep,submit]);assert set(values[0]['state']['parameters'])==expected_execute
            assert values[-1]['state']['last_outcome']['result']['test_parameters']==g
            missing=copy.deepcopy(g);del missing['allow_host_effects']
            values=model(exe,[stage(missing),reviewstep,submit]);assert values[-1]['state']['requests']=='0'
            if kind=='gui':
                values=model(exe,[stage(g),reviewstep,dict(op='edit',field='phase',value='prepare'),submit])
                assert values[-1]['state']['requests']=='0' and set(values[-1]['state']['parameters'])==expected_prepare
                assert all(not v for k,v in values[-1]['state']['parameters'].items() if k!='phase')
                for bad in ['{}','{"schema":"x","schema":"y"}','x'*16385]:
                    values=model(exe,[stage(g),reviewstep,dict(op='edit',field='definition',value=bad),reviewstep,submit])
                    assert values[-1]['state']['requests']=='0'
            else:
                # Definition follows the discriminator and four explicit grants.
                to_definition=[dict(op='key',key='tab') for _ in range(5)]
                values=model(exe,[stage(g),*to_definition,dict(op='text',text='x'*16385),dict(op='text',text=''),reviewstep,submit])
                assert values[-1]['state']['requests']=='0'
                values=model(exe,[stage(g),dict(op='key',key='backspace'),reviewstep,submit])
                assert values[-1]['state']['requests']=='0' and set(values[-1]['state']['parameters'])=={'phase'}
        no_effects(p)

        for name in ('native-gui','native-tui'):
            folder,p=fixture(name)
            if name=='native-gui':
                phase_ui=Gui(a.exe,['--gui','image','acquire','prepare',p['source'],p['destination'],'--map',p['map'],'--state-dir',p['state_directory']],render=True)
                try:
                    send(phase_ui.child(200),0xB1,7,7);phase_ui.key(8,hwnd=phase_ui.child(200))
                    wait(lambda:phase_ui.text(200)=='prepar');assert (send(phase_ui.child(200),0xB0)&0xffff)==6
                    phase_ui.key(8,hwnd=phase_ui.child(200));wait(lambda:phase_ui.text(200)=='prepa')
                    phase_ui.set(200,'execute');assert set(phase_ui.details()['parameters'])==expected_execute
                    assert not phase_ui.details()['reviewed'];assert all(not v for k,v in phase_ui.details()['parameters'].items() if k!='phase')
                    phase_ui.click(110);no_effects(p)
                    native.append(dict(frontend='gui',phase='edit-phase',cleared_grants=True,caret_preserved=True,observation=phase_ui.observation()))
                finally:phase_ui.close()
                assert phase_ui.code==0 and not phase_ui.error
                ui=Gui(a.exe,['--gui','image','acquire','prepare',p['source'],p['destination'],'--map',p['map'],'--state-dir',p['state_directory']],render=True)
                try:
                    assert ui.details()['parameters']['phase']=='prepare';no_effects(p)
                    ui.click(109);assert ui.details()['reviewed'];no_effects(p)
                    if a.evidence:ui.screenshot(a.evidence.parent/'gui-acquisition-prepare-review.png')
                    ui.click(110);result=wait(lambda:ui.details() if ui.details().get('schema')=='org.disked.response/1' else None)
                    assert result['status']=='completed';review=result['result'];no_effects(p)
                    native.append(dict(frontend='gui',phase='prepare',response=result,observation=ui.observation()))
                finally:ui.close()
                assert ui.code==0 and not ui.error
                g=grants(review);assert len(canonical(g['definition']))>4096
                argv=['--gui','image','acquire','execute','--definition-json',canonical(g['definition']).decode(),'--definition-digest',g['definition_digest']]
                for flag in ('source-read','destination-write','map-write','host-effects'):argv.append('--allow-'+flag)
                ui=Gui(a.exe,argv,render=True)
                try:
                    no_effects(p);ui.click(109);details=ui.details();assert details['parameters']==g and details['reviewed'] and details['expected_revision'] is None;no_effects(p)
                    if a.evidence:ui.screenshot(a.evidence.parent/'gui-acquisition-execute-review.png')
                    ui.click(110);first=wait(lambda:ui.details() if ui.details().get('schema')=='org.disked.response/1' else None)
                    assert first['status'] in ('completed','accepted_running');native.append(dict(frontend='gui',phase='execute',response=first,observation=ui.observation()))
                finally:ui.close()
                assert ui.code==0 and not ui.error;finished(p,first)
            else:
                first=console(p,folder);assert first['status']=='completed';no_effects(p)
                first=console(grants(first['result']),folder);assert first['status'] in ('completed','accepted_running');finished(p,first)
        _,p=fixture('public-still-gated');cli(['image','acquire','prepare',p['source'],p['destination'],'--map',p['map'],'--state-dir',p['state_directory']],(3,),True);no_effects(p)

    report=dict(passed=True,scope='private-native-acquisition-form-composition',public_acquisition_admitted=False,
        checks=len(observations),observations=observations,native_journeys=native,verified_copies=verified)
    if a.evidence:a.evidence.write_bytes(json.dumps(report,indent=2).encode()+b'\n')
    print('PASS acquisition forms:',len(observations),'checks;',len(native),'native journeys;',len(verified),'verified copies')


if __name__=='__main__':main()
