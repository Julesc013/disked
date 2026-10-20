"""Owned NTFS bootstrap through actual shared frontends, generated ordinary files only."""
import argparse,copy,hashlib,json,os,queue,subprocess,sys,tempfile,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from support.sparse import size_empty_file
from test_ntfs_capture import Volume
from ntfs_closure_fixture import ClosureVolume
from test_ntfs_file import canonical,file_digest
from gui_fixture import Gui,wait
from test_image_commands import Gate

def digest(value):return 'sha256:'+hashlib.sha256(canonical(value)).hexdigest()
def write(volume,path):
    with path.open('xb') as stream:
        size_empty_file(stream,int(volume.input['source_bytes']))
        for row in volume.input['regions']:
            stream.seek(int(row['offset']));stream.write(bytes.fromhex(row['hex']))

def main():
    ap=argparse.ArgumentParser()
    for key in ('exe','fault','worker','probe','root','output'):ap.add_argument('--'+key,type=Path,required=True)
    a=ap.parse_args()
    for key in ('exe','fault','worker','probe','root','output'):setattr(a,key,getattr(a,key).resolve())
    env={k:v for k,v in os.environ.items() if not k.startswith('DISKED_')};records=[];passed=False
    def record(name,**values):print('CASE',name,flush=True);records.append(dict(name=name,**values))
    def options(v,selector=None):
        out=['--view','ntfs','--volume-offset',v.input['offset'],'--volume-bytes',v.input['length']]
        return out+(['--ntfs-version',selector] if selector else [])
    def params(v,path,selector=None):
        out=dict(path=str(path),view='ntfs',volume_offset=v.input['offset'],volume_bytes=v.input['length'])
        if selector:out['ntfs_version']=selector
        return out
    def wire(parameters,id='ntfs:req'):
        return dict(schema='org.disked.request/1',request_id=id,command='image.inspect',parameters=parameters,required_features=[])
    def launch(name,argv,expected=0,exe=None,settings=None,data=b''):
        command=[str(exe or a.exe),*argv];p=subprocess.run(command,input=data,capture_output=True,env=dict(env,**(settings or {})),cwd=a.root,timeout=20)
        assert p.returncode==expected and not p.stderr,(name,p.returncode,p.stdout[:3000],p.stderr)
        assert len(p.stdout)<=524288
        value=json.loads(p.stdout);assert value['operation_id'] is None
        record(name,command=command,exit_code=p.returncode,response_sha256='sha256:'+hashlib.sha256(p.stdout).hexdigest())
        return value
    def stable(value):
        value=copy.deepcopy(value['result'])
        for key in ('context','worker','file_sha256','capture_sha256'):value.pop(key)
        value['observation'].pop('epoch');value['observation'].pop('source_id')
        for closure in value['observation'].get('record_closures',{}).values():
            if closure.get('join'):
                closure['join'].pop('epoch');closure['join'].pop('source_id')
        for key in ('process_id','process_created','sequence','capture_domain','domain'):value['capture'].pop(key)
        return value
    def compare(left,right):
        assert left['status']==right['status'] and left['diagnostics']==right['diagnostics']
        assert stable(left)==stable(right),(stable(left),stable(right))
    def pure(parameters,file=None,status='captured',**extra):
        payload=dict(parameters=parameters,status=status,**extra)
        if file is not None:payload['file']=file
        p=subprocess.run([str(a.probe)],input=canonical(payload),capture_output=True,timeout=15)
        assert p.returncode==0 and not p.stderr,(p.returncode,p.stdout[:1000],p.stderr)
        value=json.loads(p.stdout);assert len(canonical(value['response']))<=524288
        record('pure-port',exit_code=value['exit_code'],port_called=value['port_called'],sha256=digest(value))
        return value
    def wrapper(value,original,maximum,budget,project=lambda x:x):
        expected=[];used=0
        for row in original:
            item=project(copy.deepcopy(row));size=len(canonical(item))+1
            if len(expected)==maximum or size>budget-used:break
            used+=size;expected.append(item)
        assert value==dict(items=expected,total=str(len(original)),returned=str(len(expected)),omitted=str(len(original)-len(expected)),sha256=digest(original))
    try:
        with tempfile.TemporaryDirectory(prefix='disked-ntfs-command-') as temp:
            folder=Path(temp).resolve();baseline=None;full=None
            fixtures=[(Volume(minor=minor,offset=173,sector=sector,size=size,usa=usa),selector,expected)
                      for minor,selector,expected,sector,size,usa in [(0,None,0,512,1024,42),(1,None,0,512,1024,48),(0,'3.0',0,512,1024,48),(1,'3.1',0,4096,4096,48),(0,'3.1',4,512,1024,48),(1,'3.0',4,512,1024,48)]]
            fixtures[1]=(ClosureVolume(offset=173,nonresident_list=True,volume_nonresident=True),None,0)
            advisory=Volume(offset=173);advisory.change(0,510)
            fixtures.append((advisory,None,0))
            bad=Volume(offset=173);bad.change(0,11,0);bad.change(0,12,0)
            fixtures.append((bad,None,4))
            bad_record=Volume(offset=173);bad_record.change(1,510)
            fixtures.append((bad_record,None,4))
            for minor in (0,1):
                for form in (False,True):fixtures.append((ClosureVolume(minor=minor,offset=173,nonresident_list=form,volume_nonresident=form),None,0))
            for index,(v,selector,expected) in enumerate(fixtures):
                path=folder/f'generated-{index}.img';write(v,path);before=file_digest(path)
                value=launch('cli-profile-'+str(index),['--json','image','inspect',str(path),*options(v,selector)],expected)
                result=value['result'];obs=result['observation']
                assert result['schema']=='org.disked.ntfs-inspection/1' and result['scope']=='ordinary-local-file-ntfs'
                assert result['applicability_scope']=='boot-mft0-mirror0-volume-information'
                assert obs['schema']=='org.disked.ntfs-bootstrap-projection/1'
                assert obs['original_schema']=='org.disked.ntfs-bootstrap-observation-prototype/1'
                assert obs['applicable']==(expected==0) and not result['authorizes_effects']
                if index==6:assert int(obs['boot']['issues'])!=0
                assert result['worker']['worker']['observation']=='exited'
                context=result['context'];worker=result['worker']['worker']
                assert context['pid']==worker['pid']==result['capture']['process_id']
                assert context['created']==worker['created']==result['capture']['process_created']
                assert context['code_sha256']==hashlib.sha256(a.exe.read_bytes()).hexdigest()
                assert context['capture_epoch']==obs['epoch']==result['capture']['sequence']
                if index<6:
                    assert obs['volume_information']['minor']==str(0 if index in (0,2,4) else 1)
                    assert obs['boot']['record_bytes']==str(v.size)
                protocol=launch('stdio-profile-'+str(index),['protocol','serve','--json'],expected,data=canonical(wire(params(v,path,selector))))
                compare(value,protocol);assert file_digest(path)==before
                if index==1:baseline=(v,path,value)
            v,path,expected=baseline
            # Independently qualified worker returns the full original lists for
            # projection comparison; no frontend result defines its expectation.
            p=subprocess.run([str(a.worker)],input=canonical(dict(path=str(path),offset=v.input['offset'],length=v.input['length'],capture_epoch='9')),capture_output=True,timeout=35)
            assert p.returncode==0 and not p.stderr
            full=json.loads(p.stdout)['snapshot'];before=file_digest(path)
            projected=pure(params(v,path),full)['response']['result']['observation']
            wrapper(projected['regions'],full['observation']['regions'],128,32768)
            assert projected['mft']==full['observation']['mft']
            assert projected['mft']['runs']=='4'
            for key in ('primary','mirror','volume_record'):
                original=full['observation'][key]['attributes']
                def attribute(row):
                    if 'runs' in row:
                        runs=row['runs'];row['runs']=dict(items=runs,total=str(len(runs)),returned=str(len(runs)),omitted='0',sha256=digest(runs))
                    return row
                wrapper(projected[key]['attributes'],original,128,65536,attribute)
            def record_projection(original):
                out=copy.deepcopy(original)
                attrs=out.get('attributes')
                if attrs is not None:
                    for attr in attrs:
                        if 'runs' in attr:
                            runs=attr['runs'];attr['runs']=dict(items=runs,total=str(len(runs)),returned=str(len(runs)),omitted='0',sha256=digest(runs))
                    out['attributes']=dict(items=attrs,total=str(len(attrs)),returned=str(len(attrs)),omitted='0',sha256=digest(original['attributes']))
                return out
            for role,closure in full['observation']['record_closures'].items():
                selected=projected['record_closures'][role]
                wrapper(selected['extensions'],closure['extensions'],128,65536,record_projection)
                for key in ('records','parts','runs','required_records'):
                    small=key in ('runs','required_records')
                    wrapper(selected['join'][key],closure['join'][key],64 if small else 128,8192 if small else 32768)
            record('full-original-list-projection',file_sha256=digest(full))
            detailed=copy.deepcopy(full);original_runs=full['observation']['primary']['attributes'][0]['runs']*60
            for key in ('primary','mirror','volume_record'):
                attr=copy.deepcopy(full['observation']['primary']['attributes'][0]);attr['runs']=original_runs
                detailed['observation'][key]['attributes']=[copy.deepcopy(attr) for _ in range(170)]
            detailed['observation']['regions']*=60
            for closure in detailed['observation']['record_closures'].values():
                closure['extensions']*=170
                for key in ('records','parts','runs'):
                    closure['join'][key]=copy.deepcopy(full['observation']['record_closures']['mft']['join'][key])*170
                closure['join']['required_records']=[str(i) for i in range(170)]
            # Keep the synthetic report within the declared8MiB transport ceiling.
            assert len(canonical(detailed))<8*1024*1024
            detail=pure(params(v,path),detailed);assert detail['exit_code']==0
            observed=detail['response']['result']['observation']
            for key in ('primary','mirror','volume_record'):
                rows=observed[key]['attributes'];assert int(rows['omitted'])>0
                original=detailed['observation'][key]['attributes'];assert rows['sha256']==digest(original)
                assert int(rows['returned'])==len(rows['items']) and int(rows['total'])==int(rows['returned'])+int(rows['omitted'])
                for attr in rows['items']:wrapper(attr['runs'],original_runs,64,8192)
                assert sum(len(canonical(r))+1 for r in rows['items'])<=65536
            assert observed['mft']==detailed['observation']['mft']
            wrapper(observed['regions'],detailed['observation']['regions'],128,32768)
            for role,closure in detailed['observation']['record_closures'].items():
                selected=observed['record_closures'][role]
                wrapper(selected['extensions'],closure['extensions'],128,65536,record_projection)
                assert int(selected['extensions']['omitted'])>0
                for key in ('records','parts','runs','required_records'):
                    small=key in ('runs','required_records')
                    wrapper(selected['join'][key],closure['join'][key],64 if small else 128,8192 if small else 32768)
                    assert int(selected['join'][key]['omitted'])>0
            record('nested-original-digests-and-prefix-bounds')
            excessive=copy.deepcopy(full);excessive['capture']['padding']='x'*600000
            assert pure(params(v,path),excessive)['response']['diagnostics'][0]['code']=='ntfs_report_limit'
            assert pure(dict(params(v,path),fat_copy='0'))['port_called'] is False
            assert pure(dict(params(v,path),volume_offset=str((1<<63)-512),volume_bytes='512'))['port_called'] is False
            unknown=pure(params(v,path),status='unresolved',diagnostic='ntfs_test_unresolved');assert unknown['exit_code']==6
            changed=copy.deepcopy(full);changed['capture']['metadata_equal']=False;changed['capture']['observed_stable']=False;changed['observation']['applicable']=False
            assert 'ntfs_source_changed' in [d['code'] for d in pure(params(v,path),changed)['response']['diagnostics']]
            # Review is inert in the actual native window; submission uses the
            # same service. TUI/shell run in owned hidden consoles.
            ui=Gui(a.exe,['--gui','image','inspect',str(path),*options(v)],render=True)
            try:
                ui.click(109);assert ui.details()['reviewed'] and 'status' not in ui.details()
                assert file_digest(path)==before
                ui.click(110);actual=wait(lambda:ui.details() if 'status' in ui.details() else None);compare(expected,actual)
                record('gui',response=actual,native=ui.observation())
            finally:ui.close()
            assert not ui.error and ui.created_files==[]
            for frontend in ('tui','shell'):
                report=folder/(frontend+'.json');startup=subprocess.STARTUPINFO();startup.dwFlags=1;startup.wShowWindow=0
                command=[sys.executable,str(a.root/'tests/frontend/image_console_fixture.py'),str(a.exe),frontend,'image.inspect',str(path),'-',str(report),json.dumps(options(v))]
                p=subprocess.run(command,cwd=folder,env=env,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=35)
                value=json.loads(report.read_bytes());assert p.returncode==0 and 'fixture_error' not in value,value
                compare(expected,value['response']);record(frontend,observation=value);report.unlink()
            invalid=[['--view','ntfs'],['--view','ntfs','--volume-offset','0','--volume-bytes','511'],['--view','ntfs','--volume-offset',str((1<<63)-512),'--volume-bytes','512'],[*options(v),'--ntfs-version','2.0'],[*options(v),'--fat-copy','0'],[*options(v),'--upcase-format','auto'],['--ntfs-version','auto']]
            missing=folder/'missing.img'
            for i,flags in enumerate(invalid):
                value=launch('invalid-before-source-'+str(i),['--json','image','inspect',str(missing),*flags],2,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD':'1'})
                assert value['diagnostics'][0]['code']==('missing_parameter' if i==0 else 'invalid_option_value'),value
            launch('missing-source',['--json','image','inspect',str(missing),*options(v)],3)
            for index,selected in enumerate((dict(params(v,missing),fat_copy='0'),dict(params(v,missing),volume_offset=str((1<<63)-512),volume_bytes='512'),dict(params(v,missing),unknown=True))):
                value=launch('invalid-protocol-before-source-'+str(index),['protocol','serve','--json'],2,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD':'1'},data=canonical(wire(selected)))
                assert value['diagnostics'][0]['code']==('unexpected_parameter' if index==2 else 'invalid_parameter'),value
            for flag,exit,diagnostic in [('VERIFY_CHANGED',4,'ntfs_source_changed'),('VERIFY_ERROR',4,'ntfs_capture_incomplete'),('INVALID_REPLY',6,'ntfs_reader_validation_unresolved'),('HANG',6,None)]:
                value=launch('fault-'+flag,['--json','image','inspect',str(path),*options(v)],exit,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_'+flag:'1'})
                if diagnostic:assert diagnostic in [d['code'] for d in value['diagnostics']],value
            launch('normal-ignores-fault',['--json','image','inspect',str(path),*options(v)],settings={'DISKED_NTFS_COMMAND_TEST_HANG':'1'})
            gate=Gate();process=subprocess.Popen([str(a.fault),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=a.root,env=dict(env,DISKED_NTFS_COMMAND_TEST_GATE=gate.name));messages=queue.Queue()
            thread=threading.Thread(target=lambda:[messages.put(json.loads(line)) for line in process.stdout],daemon=True);thread.start()
            def send(value):process.stdin.write(canonical(value)+b'\n');process.stdin.flush()
            try:
                send(wire(params(v,path)));gate.entered();expired=messages.get(timeout=6)
                assert expired['status']=='unknown' and expired['diagnostics'][0]['code']=='request_wait_expired'
                try:
                    with path.open('r+b'):raise AssertionError('Source writable while unresolved')
                except PermissionError:pass
                send(wire(params(v,path),'busy'));busy=messages.get(timeout=2);assert busy['diagnostics'][0]['code']=='request_resource_limit'
                request=wire({},'essential');request['command']='command.list';send(request);assert messages.get(timeout=2)['status']=='completed'
                gate.release();after=None
                for _ in range(35):
                    time.sleep(.1);send(wire(params(v,path),'fresh'));after=messages.get(timeout=3)
                    if after['status']=='completed':break
                    assert after['diagnostics'][0]['code']=='request_resource_limit',after
                assert after and after['status']=='completed' and messages.empty()
                process.stdin.close();assert process.wait(timeout=8)==6 and not process.stderr.read()
                record('late-read-retains-source-slot',expired=expired,busy=busy)
            finally:
                gate.release();gate.close()
                if process.poll() is None:process.kill();process.wait(timeout=5)
            assert file_digest(path)==before
            for argv in (['help','--json'],['build','inspect','--json'],['command','list','--json']):
                launch('essential-'+argv[0],argv,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD':'1'})
            passed=True
    finally:a.output.write_text(json.dumps(dict(passed=passed,cases=len(records),records=records),indent=2)+'\n',encoding='utf-8',newline='\n')
    print('NTFS command/frontend cases:',len(records))
if __name__=='__main__':main()
