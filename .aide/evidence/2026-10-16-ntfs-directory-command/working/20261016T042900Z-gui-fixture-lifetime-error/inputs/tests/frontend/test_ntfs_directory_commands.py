"""Independent ordinary-image NTFS indexes through the actual common frontends."""
import argparse,copy,hashlib,json,os,queue,subprocess,sys,tempfile,threading,time
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'images'))
from ntfs_directory_fixture import DirectoryVolume,ref,filename,index_entry
from test_ntfs_directory import cases as directory_cases
from test_ntfs_commands import canonical,digest,write,file_digest,Gui,wait,Gate

CAPS=dict(read_requests='512',read_bytes='2097152',retained_bytes='524288',attributes='4096',runs='4096',output_bytes='1048576')
DIRECTORY=dict(entries='4096',blocks='128',bitmap_bytes='65536')

def display(raw):
    units=[int.from_bytes(raw[i:i+2],'little') for i in range(0,len(raw),2)]
    return ''.join(('\\'+chr(n) if n in (34,92) else chr(n)) if 32<=n<127 else '\\u%04x'%n for n in units)

def prefix(original,maximum,budget,project=lambda x:x):
    selected=[];used=0
    for row in original:
        value=project(copy.deepcopy(row));size=len(canonical(value))+1
        if len(selected)==maximum or size>budget-used:break
        selected.append(value);used+=size
    return dict(items=selected,total=str(len(original)),returned=str(len(selected)),omitted=str(len(original)-len(selected)),sha256=digest(original))

def large_volume():
    name=bytes([27,0,0,216,255,220])*85
    v=DirectoryVolume(kind='deep',size=4096,index=8192,name=name)
    for ordinal in (1,2):
        rows=[index_entry(key=filename(name[:504]+('%02d'%i).encode('utf-16le'),parent=v.reference),target=ref(14+i,9)) for i in range(12)]
        rows.append(index_entry(end=True));v.block_recipes[ordinal]=(rows,False);v.replace_block(ordinal,rows)
    v.expected_rows=[(None,r) for r in v.root_rows]+[(v.vbn(i),r) for i,(rows,_) in v.block_recipes.items() for r in rows]
    return v

def stable(response):
    value=copy.deepcopy(response['result'])
    for key in ('context','worker','file_sha256','capture_sha256'):value.pop(key)
    observation=value['observation']
    for key in ('epoch','source_id'):observation.pop(key)
    for closure in observation.get('record_closures',{}).values():
        if closure.get('join'):
            for key in ('epoch','source_id'):closure['join'].pop(key)
    for key in ('process_id','process_created','sequence','capture_domain','domain','profile_probe_sha256',
                'profile_prefix_validation_sha256','profile_probe_foundation_sha256','profile_selected_foundation_sha256'):
        value['capture'].pop(key)
    return value

def main():
    ap=argparse.ArgumentParser()
    for key in ('exe','fault','worker','probe','root','output'):ap.add_argument('--'+key,type=Path,required=True)
    a=ap.parse_args()
    for key in vars(a):setattr(a,key,getattr(a,key).resolve())
    env={k:v for k,v in os.environ.items() if not k.startswith('DISKED_')}
    records=[];sources=[];passed=False
    def record(name,**values):print('CASE',name,flush=True);records.append(dict(name=name,**values))
    def options(v,version=None,reference=None):
        out=['--view','ntfs-directory','--volume-offset',v.input['offset'],'--volume-bytes',v.input['length']]
        if version is not None:out+=['--ntfs-version',version]
        if reference is not None:out+=['--directory-reference',reference]
        return out
    def params(v,path,version=None,reference=None):
        out=dict(path=str(path),view='ntfs-directory',volume_offset=v.input['offset'],volume_bytes=v.input['length'])
        if version is not None:out['ntfs_version']=version
        if reference is not None:out['directory_reference']=reference
        return out
    def wire(parameters,id='ntfs-directory:req'):
        return dict(schema='org.disked.request/1',request_id=id,command='image.inspect',parameters=parameters,required_features=[])
    def launch(name,argv,expected=0,exe=None,settings=None,data=b'',human=False):
        command=[str(exe or a.exe),*argv]
        p=subprocess.run(command,input=data,capture_output=True,env=dict(env,**(settings or {})),cwd=a.root,timeout=25)
        assert p.returncode==expected and not p.stderr,(name,p.returncode,p.stdout[:2500],p.stderr)
        assert len(p.stdout)<=524288
        assert not any(n<32 and n not in (9,10,13) for n in p.stdout),name
        value=json.loads(p.stdout);assert value['operation_id'] is None
        if human:assert p.stdout.isascii()
        record(name,command=command,exit_code=p.returncode,bytes=len(p.stdout),response_sha256='sha256:'+hashlib.sha256(p.stdout).hexdigest())
        return value
    def pure(parameters,file=None,status='captured',**extra):
        payload=dict(parameters=parameters,status=status,**extra)
        if file is not None:payload['file']=file
        p=subprocess.run([str(a.probe)],input=canonical(payload),capture_output=True,timeout=20)
        assert p.returncode==0 and not p.stderr,(p.returncode,p.stdout[:2000],p.stderr)
        value=json.loads(p.stdout);assert len(canonical(value['response']))<=524288
        record('pure-port',exit_code=value['exit_code'],port_called=value['port_called'],sha256=digest(value))
        return value
    def worker(v,path,reference=None):
        selected=dict(path=str(path),offset=v.input['offset'],length=v.input['length'],capture_epoch='9',
                      limits=CAPS,directory=dict(reference=reference or '0',limits=DIRECTORY))
        p=subprocess.run([str(a.worker)],input=canonical(selected),capture_output=True,timeout=30)
        assert p.returncode==0 and not p.stderr,(p.returncode,p.stdout[:2000],p.stderr)
        value=json.loads(p.stdout);assert value['has_snapshot']
        record('independent-worker',input_sha256=digest(selected),snapshot_sha256=digest(value['snapshot']))
        return value['snapshot']
    def compare(left,right):
        assert left['status']==right['status'] and left['diagnostics']==right['diagnostics']
        assert stable(left)==stable(right),(stable(left),stable(right))
    def facts(value,v,expected,reference=None):
        assert value['operation_id'] is None
        result=value['result'];obs=result['observation'];capture=result['capture'];context=result['context'];process=result['worker']['worker']
        assert result['schema']=='org.disked.ntfs-directory-inspection/1' and result['scope']=='ordinary-local-file-ntfs-directory'
        assert result['applicability_scope']=='single-directory-index-envelope'
        assert result['requested_directory_reference']==(reference or '0')
        assert obs['schema']=='org.disked.ntfs-directory-projection/1' and obs['original_schema']=='org.disked.ntfs-directory-observation-prototype/1'
        assert obs['applicable']==(expected==0) and not result['authorizes_effects']
        assert not any(obs[k] for k in ('atomic_snapshot','current_source_authority','effects_authorized'))
        assert process['observation']=='exited' and process['pid']==context['pid']==capture['process_id']
        assert process['created']==context['created']==capture['process_created']
        assert context['capture_epoch']==obs['epoch']==capture['sequence']
        assert context['code_sha256']==hashlib.sha256(a.exe.read_bytes()).hexdigest()
        assert context['image_profile']=='ordinary-file-ntfs-directory'
        assert capture['domain']['limits']==CAPS and capture['domain']['directory_limits']==DIRECTORY
        assert capture['domain']['directory_reference']==(reference or '0')
        assert result['capture_sha256']==digest(capture)
        if expected:
            assert 'ntfs_capture_incomplete' in [d['code'] for d in value['diagnostics']]
            return
        d=obs['directory'];assert d['schema']=='org.disked.ntfs-index-projection/1' and d['original_schema']=='org.disked.ntfs-index-collection/1'
        assert d['name_display_encoding']=='escaped-utf16le-code-units/1'
        assert d['reference']==str(v.reference) and d['index_complete'] and d['bitmap_complete']
        assert not any(d[k] for k in ('namespace_verified','collation_verified','target_membership_verified','cluster_allocation_verified'))
        assert d['entries']['total']==str(len(v.expected_rows))
        assert d['header_count']==str(len(v.expected_rows))
        for (_,(_,wanted)),entry in zip(v.expected_rows,d['entries']['items']):
            assert entry['end_marker']==wanted['end_marker'] and entry['has_child']==wanted['has_child']
            if not wanted['end_marker']:
                assert entry['name_hex']==wanted['filename']['name_hex']
                assert entry['name_display']==display(bytes.fromhex(entry['name_hex']))
                assert entry['parent_reference']==str(v.reference) and entry['parent_matches']
        assert d['entries']['returned']==str(len(d['entries']['items']))
        assert int(d['entries']['returned'])+int(d['entries']['omitted'])==int(d['entries']['total'])
    def check_projection(projected,full):
        original=full['observation'];obs=projected['observation']
        assert projected['file_sha256']==digest(full) and projected['capture_sha256']==digest(full['capture'])
        assert obs['regions']==prefix(original['regions'],128,32768)
        def attr(row):
            if 'runs' in row:row['runs']=prefix(row['runs'],64,8192)
            return row
        def rec(row):
            if 'attributes' in row:row['attributes']=prefix(row['attributes'],128,65536,attr)
            return row
        for key in ('primary','mirror','volume_record','directory_record'):assert obs[key]==rec(copy.deepcopy(original[key]))
        for role,c in original.get('record_closures',{}).items():
            assert obs['record_closures'][role]['extensions']==prefix(c['extensions'],128,65536,rec)
            if c['join']:
                for key in ('records','parts','runs','required_records'):
                    small=key in ('runs','required_records')
                    assert obs['record_closures'][role]['join'][key]==prefix(c['join'][key],64 if small else 128,8192 if small else 32768)
        assert obs['directory_stream_queries']==prefix(original['directory_stream_queries'],16,4096)
        d=original['directory'];selected=obs['directory']
        if d is None:assert selected is None;return
        def stream(row):
            row['runs']=prefix(row['runs'],64,8192);row['parts']=prefix(row['parts'],128,32768);return row
        def entry(row):
            if 'name_hex' in row:row['name_display']=display(bytes.fromhex(row['name_hex']))
            return row
        for key,maximum,budget,project in [('streams',16,65536,stream),('blocks',128,65536,lambda x:x),('entries',256,65536,entry)]:
            assert selected[key]==prefix(d[key],maximum,budget,project),key
    try:
        with tempfile.TemporaryDirectory(prefix='disked-ntfs-directory-command-') as temp:
            folder=Path(temp).resolve();baseline=None
            fixtures=[]
            for minor,version,expected in [(0,None,0),(1,None,0),(0,'3.0',0),(1,'3.1',0),(0,'3.1',4),(1,'3.0',4)]:
                fixtures.append((DirectoryVolume(minor=minor,offset=173),version,expected,None))
            for kind in ('leaf','empty','single','deep','preallocated'):
                fixtures.append((DirectoryVolume(kind=kind),None,0,None))
            for minor in (0,1):
                fixtures.append((DirectoryVolume(minor=minor,usa=42 if minor==0 else 48,list_form='nonresident',bitmap_form='nonresident',split_allocation=True,fragmented_allocation=True,mft_closure=True),None,0,None))
            for namespace in (0,1,2,3):fixtures.append((DirectoryVolume(namespace=namespace,name=b'\x1b\0\0\xd8\xff\xdc\x22\0\x5c\0'),None,0,None))
            for n,sequence in [(17,9),(5,65535)]:
                v=DirectoryVolume(number=n,sequence=sequence);fixtures.append((v,None,0,str(v.reference)))
            chain=next(case[1] for case in directory_cases() if case[0]=='exact-128-node-chain')
            fixtures.append((chain,None,0,None))
            fixtures.append((DirectoryVolume(offset=(1<<32)+17),None,0,None))
            fixtures.append((large_volume(),None,0,None))
            large=None
            for index,(v,version,expected,reference) in enumerate(fixtures):
                path=folder/f'generated-{index}.img';write(v,path);before=file_digest(path)
                result=launch('cli-'+str(index),['--json','image','inspect',str(path),*options(v,version,reference)],expected)
                facts(result,v,expected,reference)
                protocol=launch('stdio-'+str(index),['protocol','serve','--json'],expected,data=canonical(wire(params(v,path,version,reference))))
                compare(result,protocol);after=file_digest(path);assert before==after
                sources.append(dict(bytes=path.stat().st_size,before_sha256=before,after_sha256=after))
                if index==1:baseline=(v,path,result)
                if index==len(fixtures)-1:large=(v,path,result)
            for v,path,result in (baseline,large):
                full=worker(v,path);selected=pure(params(v,path),full)
                assert selected['exit_code']==0 and selected['port_called'];check_projection(selected['response']['result'],full)
                compare(result,selected['response'])
            v,path,expected=large;full=worker(v,path)
            assert len(canonical(expected))>65536 and int(expected['result']['observation']['directory']['entries']['omitted'])>0
            human=launch('large-human-cli',['--cli','image','inspect',str(path),*options(v)],human=True);compare(expected,human)
            ndjson=launch('ndjson',['protocol','serve','--format=ndjson'],data=canonical(wire(params(v,path)))+b'\n');compare(expected,ndjson)
            with Gui(a.exe,['--gui','image','inspect',str(path),*options(v)]) as ui:
                ui.click(108);ui.click(109);ui.click(110)
                wait(lambda:ui.details().get('response',{}).get('status')=='completed')
                report=ui.details();compare(expected,report['response']);assert not ui.error and ui.created_files==[]
                assert 'presentation_unavailable' not in ui.text(101);record('large-gui',response_sha256=digest(report['response']))
            for frontend in ('tui','shell'):
                report=folder/(frontend+'.json');startup=subprocess.STARTUPINFO();startup.dwFlags=1;startup.wShowWindow=0
                command=[sys.executable,str(a.root/'tests/frontend/image_console_fixture.py'),str(a.exe),frontend,'image.inspect',str(path),'-',str(report),json.dumps(options(v)),'8000']
                p=subprocess.run(command,cwd=folder,env=env,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=40)
                value=json.loads(report.read_bytes());assert p.returncode==0 and 'fixture_error' not in value,value
                compare(expected,value['response']);assert 'presentation_unavailable' not in value['display'];record('large-'+frontend,observation=value);report.unlink()
            synthetic=copy.deepcopy(full)
            d=synthetic['observation']['directory'];d['entries']*=15;d['blocks']*=50
            for stream in d['streams']:stream['runs']*=150;stream['parts']*=150
            d['streams']*=10
            assert len(canonical(synthetic))<8*1024*1024
            selected=pure(params(v,path),synthetic);assert selected['exit_code']==0;check_projection(selected['response']['result'],synthetic)
            assert int(selected['response']['result']['observation']['directory']['blocks']['omitted'])>0
            for key in ('entries','streams'):assert int(selected['response']['result']['observation']['directory'][key]['omitted'])>0
            for field in ('name_hex','domain','request','schema'):
                bad=copy.deepcopy(full);parameters=params(v,path)
                if field=='name_hex':bad['observation']['directory']['entries'][0]['name_hex']='0'
                elif field=='domain':bad['capture']['domain']['directory_reference']='1'
                elif field=='request':parameters['directory_reference']=str(ref(17,9))
                else:bad['schema']='org.disked.ntfs-file-capture/1'
                selected=pure(parameters,bad);assert selected['exit_code']==4 and selected['response']['diagnostics'][0]['code']=='internal_error'
            for n in (32769,600000):
                bad=copy.deepcopy(full);bad['capture']['padding']='x'*n
                selected=pure(params(v,path),bad);assert selected['exit_code']==4 and selected['response']['diagnostics'][0]['code']=='ntfs_report_limit'
            # Size the independent injected port report at the exact public frame
            # boundary. Digest values retain fixed width as the original changes.
            boundary=copy.deepcopy(full);boundary['capture']['padding']=['']*20
            base=pure(params(v,path),boundary);assert base['exit_code']==0
            remaining=524287-len(canonical(base['response']))
            for index in range(20):
                count=min(32768,remaining);boundary['capture']['padding'][index]='x'*count;remaining-=count
            assert remaining==0
            selected=pure(params(v,path),boundary)
            assert selected['exit_code']==0 and len(canonical(selected['response']))==524287 and selected['wire_bytes']==524288
            boundary['capture']['padding'][-1]+='x'
            selected=pure(params(v,path),boundary)
            assert selected['exit_code']==4 and selected['response']['diagnostics'][0]['code']=='ntfs_report_limit'
            for status,exit in [('unresolved',6),('refused',3)]:assert pure(params(v,path),status=status,diagnostic='ntfs_test_'+status)['exit_code']==exit
            v,path,expected=baseline;before=file_digest(path);missing=folder/'missing.img'
            invalid=[(['--view','ntfs-directory'],'missing_parameter'),
                     (['--view','ntfs-directory','--volume-offset','0','--volume-bytes','511'],'invalid_option_value')]
            for reference in ('1',str((1<<48)-1),str(1<<64),'01','-1'):
                invalid.append((options(v)+['--directory-reference',reference],'invalid_option_value'))
            for flags in [options(v)+['--ntfs-version','2.0'],options(v)+['--fat-copy','0'],options(v)+['--upcase-format','auto'],options(v)+['--retain-capture','no'],options(v)+['--volume-offset',str(1<<63)]]:
                # Duplicate options have their existing distinct diagnostic.
                invalid.append((flags,'duplicate_option' if flags.count('--volume-offset')==2 else 'invalid_option_value'))
            for view in ('map','ntfs','fat','exfat'):
                flags=['--view',view,'--directory-reference','0']
                if view!='map':flags+=['--volume-offset','0','--volume-bytes','512']
                invalid.append((flags,'invalid_option_value'))
            for index,(flags,diagnostic) in enumerate(invalid):
                value=launch('invalid-before-source-'+str(index),['--json','image','inspect',str(missing),*flags],2,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD':'1'})
                assert value['diagnostics'][0]['code']==diagnostic,value
            for parameters in [dict(params(v,missing),directory_reference='1'),dict(params(v,missing),directory_reference=str(1<<64)),dict(params(v,missing),volume_offset=str((1<<63)-512)),dict(params(v,missing),unknown=True)]:
                value=launch('invalid-stdio-before-source',['protocol','serve','--json'],2,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD':'1'},data=canonical(wire(parameters)))
                assert value['diagnostics'][0]['code']==('unexpected_parameter' if 'unknown' in parameters else 'invalid_parameter')
                assert pure(parameters,status='unresolved')['port_called'] is False
            launch('missing-source',['--json','image','inspect',str(missing),*options(v)],3)
            for flag,exit,diagnostic in [('VERIFY_CHANGED',4,'ntfs_source_changed'),('VERIFY_ERROR',4,'ntfs_capture_incomplete'),('INVALID_REPLY',6,'ntfs_reader_validation_unresolved'),('HANG',6,None)]:
                value=launch('fault-'+flag,['--json','image','inspect',str(path),*options(v)],exit,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_'+flag:'1'})
                if diagnostic:assert diagnostic in [d['code'] for d in value['diagnostics']],value
            launch('normal-fault-isolation',['--json','image','inspect',str(path),*options(v)],settings={'DISKED_NTFS_COMMAND_TEST_HANG':'1'})
            gate=Gate();process=subprocess.Popen([str(a.fault),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=a.root,env=dict(env,DISKED_NTFS_COMMAND_TEST_GATE=gate.name));messages=queue.Queue()
            thread=threading.Thread(target=lambda:[messages.put(json.loads(line)) for line in process.stdout],daemon=True);thread.start()
            def send(value):process.stdin.write(canonical(value)+b'\n');process.stdin.flush()
            try:
                send(wire(params(v,path)));gate.entered();expired=messages.get(timeout=6)
                assert expired['status']=='unknown' and expired['diagnostics'][0]['code']=='request_wait_expired'
                try:
                    with path.open('r+b'):raise AssertionError('Source writable before actual worker completion')
                except PermissionError:pass
                send(wire(params(v,path),'busy'));assert messages.get(timeout=2)['diagnostics'][0]['code']=='request_resource_limit'
                request=wire({},'essential');request['command']='command.list';send(request);assert messages.get(timeout=2)['status']=='completed'
                gate.release();after=None
                for _ in range(35):
                    time.sleep(.1);send(wire(params(v,path),'fresh'));after=messages.get(timeout=3)
                    if after['status']=='completed':break
                    assert after['diagnostics'][0]['code']=='request_resource_limit'
                assert after and after['status']=='completed' and messages.empty()
                process.stdin.close();assert process.wait(timeout=8)==6 and not process.stderr.read()
                record('late-retains-source-slot',expired=expired)
            finally:
                gate.release();gate.close()
                if process.poll() is None:process.kill();process.wait(timeout=5)
            assert file_digest(path)==before
            for argv in (['help','--json'],['build','inspect','--json'],['command','list','--json']):launch('essential-'+argv[0],argv,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD':'1'})
            passed=True
    finally:a.output.write_text(json.dumps(dict(passed=passed,cases=len(records),records=records,source_receipts=sources,owner_accepted=False,full_0_1_0_complete=False),indent=2)+'\n',encoding='utf-8',newline='\n')
    print('NTFS directory command/frontend cases:',len(records))

if __name__=='__main__':main()
