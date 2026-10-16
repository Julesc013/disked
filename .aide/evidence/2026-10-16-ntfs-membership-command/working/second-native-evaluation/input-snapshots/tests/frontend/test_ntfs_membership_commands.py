"""Independent raw-name expectations through actual common product frontends."""
import argparse, copy, hashlib, json, os, queue, subprocess, sys, tempfile, threading, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'images'))
from ntfs_membership_fixture import MembershipVolume, filename, ref
from test_ntfs_directory_commands import CAPS, DIRECTORY, display, prefix
from test_ntfs_commands import canonical, digest, write, file_digest, Gui, wait, Gate


def stable(response):
    result = copy.deepcopy(response['result'])
    for key in ('context', 'worker', 'file_sha256', 'capture_sha256'):
        result.pop(key, None)
    # Acquisition identities vary per request. Prefix hashes over those identities
    # are checked separately against exact worker bytes, never compared across runs.
    result.pop('capture', None)
    def clean(value):
        if isinstance(value, dict):
            wrapped = all(k in value for k in ('items', 'total', 'returned', 'omitted'))
            return {k: clean(v) for k, v in value.items()
                    if k not in ('source_id', 'epoch') and not (wrapped and k == 'sha256')}
        if isinstance(value, list):
            return [clean(v) for v in value]
        return value
    return clean(result)


def target_projection(row):
    def record(row):
        if 'attributes' in row:
            def attribute(a):
                if 'runs' in a:
                    a['runs'] = prefix(a['runs'], 32, 4096)
                return a
            row['attributes'] = prefix(row['attributes'], 32, 16384, attribute)
        return row
    if 'record' in row:
        row['record'] = record(row['record'])
    if 'extensions' in row:
        row['extensions'] = prefix(row['extensions'], 32, 16384, record)
    if row.get('inventory') is not None:
        inv = row['inventory']
        inv['original_schema'] = inv['schema']
        inv['schema'] = 'org.disked.ntfs-filename-projection/1'
        def named(name):
            name['name_display'] = display(bytes.fromhex(name['name_hex']))
            return name
        inv['names'] = prefix(inv['names'], 128, 32768, named)
        inv['records'] = prefix(inv['records'], 128, 8192)
        inv['required_records'] = prefix(inv['required_records'], 64, 4096)
    return row


def main():
    ap = argparse.ArgumentParser()
    for key in ('exe', 'fault', 'worker', 'probe', 'root', 'output'):
        ap.add_argument('--' + key, type=Path, required=True)
    a = ap.parse_args()
    for key in vars(a):
        setattr(a, key, getattr(a, key).resolve())
    env = {k: v for k, v in os.environ.items() if not k.startswith('DISKED_')}
    records, sources = [], []
    passed = False
    def record(name, **values):
        print('CASE', name, flush=True)
        records.append(dict(name=name, **values))
    def params(v, path, version=None, reference=None, targets=None):
        result = dict(path=str(path), view='ntfs-membership', volume_offset=v.input['offset'], volume_bytes=v.input['length'])
        for key, value in [('ntfs_version', version), ('directory_reference', reference), ('ntfs_target_limit', targets)]:
            if value is not None:
                result[key] = value
        return result
    def options(v, version=None, reference=None, targets=None):
        result = ['--view', 'ntfs-membership', '--volume-offset', v.input['offset'], '--volume-bytes', v.input['length']]
        for key, value in [('--ntfs-version', version), ('--directory-reference', reference), ('--ntfs-target-limit', targets)]:
            if value is not None:
                result += [key, value]
        return result
    def wire(parameters, ident='membership:req'):
        return dict(schema='org.disked.request/1', request_id=ident, command='image.inspect', parameters=parameters, required_features=[])
    def run(name, command, data=b'', settings=None, timeout=30):
        started = time.monotonic()
        process = subprocess.run([str(x) for x in command], input=data, capture_output=True, env=dict(env, **(settings or {})), cwd=a.root, timeout=timeout)
        row = dict(command=[str(x) for x in command], exit_code=process.returncode,
                   elapsed_seconds=time.monotonic()-started, stdout_bytes=len(process.stdout), stderr_bytes=len(process.stderr), stdout_sha256='sha256:'+hashlib.sha256(process.stdout).hexdigest())
        try:
            value = json.loads(process.stdout)
        except (ValueError, UnicodeError):
            value = None
        # Always retain complete output before assertions; availability failures
        # cannot lose their raw worker response in this harness.
        output = a.output.with_name(a.output.stem+'-response-'+str(len(records))+'.json')
        output.write_bytes(process.stdout)
        row['raw_output'] = str(output)
        if process.stderr:
            row['stderr'] = process.stderr.decode(errors='replace')
        record(name, **row)
        assert value is not None and not process.stderr, row
        return process, value
    def launch(name, argv, expected=0, exe=None, settings=None, data=b''):
        p, value = run(name, [exe or a.exe, *argv], data, settings)
        assert p.returncode == expected, (name, p.returncode, value)
        assert len(p.stdout) <= 524288 and not any(n < 32 and n not in (9, 10, 13) for n in p.stdout)
        assert value['operation_id'] is None
        return value
    def pure(parameters, full=None, status='captured', **extra):
        body = dict(parameters=parameters, status=status, **extra)
        if full is not None:
            body['file'] = full
        p, value = run('pure-projection', [a.probe], canonical(body))
        assert p.returncode == 0 and len(canonical(value['response'])) <= 524287
        return value
    def worker(v, path, version=None, reference=None, targets=None):
        request = dict(path=str(path), offset=v.input['offset'], length=v.input['length'], capture_epoch='9', limits=CAPS,
                       directory=dict(reference=reference or '0', limits=DIRECTORY), membership=dict(targets=targets or '64'))
        if version:
            request['profile'] = version
        p, value = run('independent-owned-worker', [a.worker], canonical(request))
        assert p.returncode == 0 and value['has_snapshot'], value
        return value['snapshot']
    def compare(left, right):
        assert left['status'] == right['status'] and left['diagnostics'] == right['diagnostics']
        assert stable(left) == stable(right), (stable(left), stable(right))
    def projection(result, full):
        assert result['file_sha256'] == digest(full) and result['capture_sha256'] == digest(full['capture'])
        orig = full['observation']['membership']
        selected = result['observation']['membership']
        assert selected['schema'] == 'org.disked.ntfs-name-correspondence-projection/1'
        assert selected['original_schema'] == orig['schema']
        assert selected['name_display_encoding'] == 'escaped-utf16le-code-units/1'
        assert selected['targets'] == prefix(orig['targets'], 64, 131072, target_projection)
        assert selected['edges'] == prefix(orig['edges'], 256, 32768)
    def facts(value, v, expected, reference=None, targets=None, version=None, diagnostic=None):
        result = value['result']; obs = result['observation']; capture = result['capture']; context = result['context']; process = result['worker']['worker']
        assert result['schema'] == 'org.disked.ntfs-membership-inspection/1'
        assert result['scope'] == 'ordinary-local-file-ntfs-membership'
        assert result['applicability_scope'] == 'single-directory-raw-name-correspondence'
        assert result['requested_target_limit'] == obs['requested_target_limit'] == capture['domain']['target_limit'] == (targets or '64')
        assert result['requested_directory_reference'] == obs['requested_directory_reference'] == capture['domain']['directory_reference'] == (reference or '0')
        assert result['requested_version'] == (version or 'auto')
        assert obs['schema'] == 'org.disked.ntfs-membership-projection/1' and obs['original_schema'] == 'org.disked.ntfs-membership-observation-prototype/1'
        assert not result['authorizes_effects'] and not any(obs[k] for k in ('atomic_snapshot','current_source_authority','effects_authorized'))
        assert process['observation'] == 'exited' and process['pid'] == context['pid'] == capture['process_id']
        assert process['created'] == context['created'] == capture['process_created']
        assert context['capture_epoch'] == obs['epoch'] == capture['sequence']
        assert context['code_sha256'] == hashlib.sha256(a.exe.read_bytes()).hexdigest()
        assert context['image_profile'] == 'ordinary-file-ntfs-membership'
        assert capture['domain']['limits'] == CAPS and capture['domain']['directory_limits'] == DIRECTORY
        assert result['capture_sha256'] == digest(capture)
        if diagnostic:
            assert obs['diagnostic'] == diagnostic
            assert ('ntfs_membership_name_mismatch' if diagnostic == 'ntfs_membership_name_mismatch' else 'ntfs_capture_incomplete') in [d['code'] for d in value['diagnostics']]
        if diagnostic == 'ntfs_membership_name_mismatch':
            assert obs['complete'] and not obs['applicable'] and 'ntfs_capture_incomplete' not in [d['code'] for d in value['diagnostics']]
            assert obs['reread_equal'] and capture['metadata_complete'] and not capture['observed_stable']
        if not expected or diagnostic == 'ntfs_membership_name_mismatch':
            m = obs['membership']; want = v.correspondence()
            assert m['collection_complete'] and m['edges']['items'] == want[:int(m['edges']['returned'])]
            assert m['all_edges_matched'] == all(e['corresponds'] for e in want)
            assert not any(m[k] for k in ('namespace_verified','collation_verified','lookup_verified','uniqueness_verified'))
            for target in m['targets']['items']:
                names = target['inventory']['names']['items']
                expected_names = v.inventories[int(target['reference'])]
                for name, wanted in zip(names, expected_names):
                    assert name['name_hex'] == wanted['name'].hex() and name['name_display'] == display(wanted['name'])
                    assert name['value_sha256'] == 'sha256:'+hashlib.sha256(wanted['value']).hexdigest()
    try:
        with tempfile.TemporaryDirectory(prefix='disked-membership-command-') as temp:
            folder = Path(temp).resolve(); fixtures = []
            for minor, version, expected in [(0,None,0),(1,None,0),(0,'3.0',0),(1,'3.1',0),(0,'3.1',4),(1,'3.0',4)]:
                fixtures.append((MembershipVolume(minor=minor,offset=173,list_form='nonresident'), version, expected, None, None, 'ntfs_volume_version' if expected else None))
            for kind in ('leaf','empty','single','siblings','deep','preallocated'):
                fixtures.append((MembershipVolume(kind=kind),None,0,None,None,None))
            for reference, minor in [(ref(17,9),1),(ref(5,65535),0)]:
                fixtures.append((MembershipVolume(number=reference&((1<<48)-1),sequence=reference>>48,minor=minor,usa=42 if minor==0 else 48),None,0,str(reference),None,None))
            for limit in ('1','64','256'):
                fixtures.append((MembershipVolume(),None,0,None,limit,None))
            for field in ('parent','name','namespace','empty'):
                v=MembershipVolume(); values=[]
                for original in v.target_recipes[v.edges[0]['reference']]['values']:
                    raw=bytearray(original)
                    if field=='parent':raw[0]^=1
                    elif field=='name':raw[66]^=1
                    elif field=='namespace':raw[65]=2
                    if field!='empty':values.append(bytes(raw))
                v.replace_target(values=values)
                fixtures.append((v,None,4,None,None,'ntfs_membership_name_mismatch'))
            v=MembershipVolume(kind='leaf',size=4096); one=filename(b'A\0',parent=v.reference)[0]; two=filename(b'B\0',parent=v.reference)[0]
            v.leaf_edges([(ref(14,9),one),(ref(15,10),two),(ref(14,9),one)]);v.install_target(ref(14,9),[one,one]);v.install_target(ref(15,10),[two]);v.finish_reads()
            fixtures += [(v,None,4,None,'1','ntfs_membership_target_budget'),(v,None,0,None,'2',None)]
            fixtures.append((MembershipVolume(offset=(1<<32)+17),None,0,None,None,None))
            large=MembershipVolume(kind='single',size=4096,name=(b'\x1b\0\0\xd8\xff\xdc\x22\0\x5c\0')*51,list_form='nonresident')
            names=large.target_recipes[large.edges[0]['reference']]['values'];large.replace_target(values=names+[names[0]]*3)
            fixtures.append((large,None,0,None,None,None))
            baseline=None; large_case=None
            for index,(v,version,expected,reference,targets,diagnostic) in enumerate(fixtures):
                path=folder/f'generated-{index}.img';write(v,path);before=file_digest(path)
                value=launch('cli-'+str(index),['--json','image','inspect',str(path),*options(v,version,reference,targets)],expected)
                facts(value,v,expected,reference,targets,version,diagnostic)
                protocol=launch('stdio-'+str(index),['protocol','serve','--json'],expected,data=canonical(wire(params(v,path,version,reference,targets))))
                compare(value,protocol);after=file_digest(path);assert before==after
                sources.append(dict(bytes=path.stat().st_size,before_sha256=before,after_sha256=after))
                if index==1:baseline=(v,path,value)
                if index==len(fixtures)-1:large_case=(v,path,value)
            for v,path,value in (baseline,large_case):
                full=worker(v,path);selected=pure(params(v,path),full)
                assert selected['exit_code']==0 and selected['port_called'];projection(selected['response']['result'],full);compare(value,selected['response'])
            v,path,value=large_case;full=worker(v,path)
            human=launch('human-cli',['--cli','image','inspect',str(path),*options(v)]);compare(value,human)
            ndjson=launch('ndjson',['protocol','serve','--format=ndjson'],data=canonical(wire(params(v,path)))+b'\n');compare(value,ndjson)
            ui=Gui(a.exe,['--gui','image','inspect',str(path),*options(v)],render=True)
            try:
                ui.click(109);assert ui.details()['reviewed'] and 'status' not in ui.details()
                ui.click(110);report=wait(lambda:ui.details() if 'status' in ui.details() else None)
                compare(value,report);assert 'presentation_unavailable' not in ui.text(101);record('gui',response_sha256=digest(report))
            finally:ui.close()
            assert ui.code==0 and not ui.error and ui.created_files==[]
            for frontend in ('tui','shell'):
                report=folder/(frontend+'.json');startup=subprocess.STARTUPINFO();startup.dwFlags=1;startup.wShowWindow=0
                command=[sys.executable,str(a.root/'tests/frontend/image_console_fixture.py'),str(a.exe),frontend,'image.inspect',str(path),'-',str(report),json.dumps(options(v)),'8000']
                p=subprocess.run(command,cwd=folder,env=env,creationflags=subprocess.CREATE_NEW_CONSOLE,startupinfo=startup,timeout=40)
                result=json.loads(report.read_bytes());record(frontend,exit_code=p.returncode,observation=result)
                assert p.returncode==0 and 'fixture_error' not in result,result
                compare(value,result['response']);assert 'presentation_unavailable' not in result['display'];report.unlink()
            # Synthetic source-free inventories exercise independent nested caps
            # without pretending that those fabricated rows came from the source.
            detailed=copy.deepcopy(full);m=detailed['observation']['membership'];m['targets']*=80;m['edges']*=160
            assert len(canonical(detailed))<8*1024*1024
            selected=pure(params(v,path),detailed);assert selected['exit_code']==0;projection(selected['response']['result'],detailed)
            assert int(selected['response']['result']['observation']['membership']['targets']['omitted'])>0
            for field in ('domain-target','request-target','inner-target','schema','name','membership-schema'):
                bad=copy.deepcopy(full);parameters=params(v,path)
                if field=='domain-target':bad['capture']['domain']['target_limit']='1'
                elif field=='request-target':parameters['ntfs_target_limit']='1'
                elif field=='inner-target':bad['observation']['membership']['target_limit']='1'
                elif field=='schema':bad['schema']='org.disked.ntfs-directory-file-capture/1'
                elif field=='membership-schema':bad['observation']['membership']['schema']='wrong'
                else:bad['observation']['membership']['targets'][0]['inventory']['names'][0]['name_hex']='0'
                out=pure(parameters,bad);assert out['exit_code']==4 and out['response']['diagnostics'][0]['code']=='internal_error'
            boundary=copy.deepcopy(full);boundary['capture']['padding']=[]
            size=len(canonical(pure(params(v,path),boundary)['response']));remaining=524287-size
            while remaining:
                charge=3 if boundary['capture']['padding'] else 2
                n=min(32768,remaining-charge);assert n>=0
                if remaining-n-charge in (1,2):n-=3
                boundary['capture']['padding'].append('x'*n);remaining-=n+charge
            selected=pure(params(v,path),boundary);assert selected['exit_code']==0 and selected['wire_bytes']==524288
            boundary['capture']['padding'][-1]+='x';selected=pure(params(v,path),boundary)
            assert selected['exit_code']==4 and selected['response']['diagnostics'][0]['code']=='ntfs_report_limit'
            v,path,value=baseline;missing=folder/'missing.img'
            for limit in ('0','257','01','-1',str(1<<64),'true'):
                result=launch('invalid-limit-before-source',['--json','image','inspect',str(missing),*options(v,targets=limit)],2,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD':'1'})
                assert result['diagnostics'][0]['code']=='invalid_option_value'
            for view in (None,'map','fat','exfat','ntfs','ntfs-directory'):
                parameters=dict(path=str(missing),ntfs_target_limit='64')
                flags=['--ntfs-target-limit','64']
                if view:parameters['view']=view;flags+=['--view',view]
                if view not in (None,'map'):parameters.update(volume_offset='0',volume_bytes='512');flags+=['--volume-offset','0','--volume-bytes','512']
                result=launch('wrong-view-before-source',['--json','image','inspect',str(missing),*flags],2,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD':'1'})
                assert result['diagnostics'][0]['code']=='invalid_option_value'
                assert not pure(parameters,status='unresolved')['port_called']
            for key,invalid in [('ntfs_target_limit','0'),('ntfs_target_limit',True),('ntfs_target_limit',None),('ntfs_target_limit',str(1<<64)),('directory_reference','1'),('volume_bytes','511'),('volume_offset',str((1<<63)-512)),('fat_copy','0'),('retain_capture','no')]:
                parameters=params(v,missing);parameters[key]=invalid
                result=launch('invalid-stdio-before-source',['protocol','serve','--json'],2,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD':'1'},data=canonical(wire(parameters)))
                assert result['diagnostics'][0]['code']=='invalid_parameter' and not pure(parameters,status='unresolved')['port_called']
            launch('missing-source',['--json','image','inspect',str(missing),*options(v)],3)
            for flag,exit_code,diagnostic in [('VERIFY_CHANGED',4,'ntfs_source_changed'),('VERIFY_ERROR',4,'ntfs_capture_incomplete'),('INVALID_REPLY',6,'ntfs_reader_validation_unresolved'),('HANG',6,None)]:
                result=launch('fault-'+flag,['--json','image','inspect',str(path),*options(v)],exit_code,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_'+flag:'1'})
                if diagnostic:assert diagnostic in [d['code'] for d in result['diagnostics']],result
            launch('normal-fault-isolation',['--json','image','inspect',str(path),*options(v)],settings={'DISKED_NTFS_COMMAND_TEST_HANG':'1'})
            gate=Gate();process=subprocess.Popen([str(a.fault),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=a.root,env=dict(env,DISKED_NTFS_COMMAND_TEST_GATE=gate.name));messages=queue.Queue()
            threading.Thread(target=lambda:[messages.put(json.loads(line)) for line in process.stdout],daemon=True).start()
            def send(request):process.stdin.write(canonical(request)+b'\n');process.stdin.flush()
            try:
                before=file_digest(path);send(wire(params(v,path)));gate.entered();expired=messages.get(timeout=6)
                assert expired['status']=='unknown' and expired['diagnostics'][0]['code']=='request_wait_expired'
                try:
                    with path.open('r+b'):raise AssertionError('Source writable before actual completion')
                except PermissionError:pass
                send(wire(params(v,path),'busy'));assert messages.get(timeout=2)['diagnostics'][0]['code']=='request_resource_limit'
                essential=wire({},'essential');essential['command']='command.list';send(essential);assert messages.get(timeout=2)['status']=='completed'
                gate.release();after=None
                for _ in range(35):
                    time.sleep(.1);send(wire(params(v,path),'fresh'));after=messages.get(timeout=3)
                    if after['status']=='completed':break
                    assert after['diagnostics'][0]['code']=='request_resource_limit'
                assert after and after['status']=='completed' and messages.empty()
                process.stdin.close();assert process.wait(timeout=8)==6 and not process.stderr.read()
                assert file_digest(path)==before;record('late-retains-source-slot',expired=expired)
            finally:
                gate.release();gate.close()
                if process.poll() is None:
                    if not process.stdin.closed:process.stdin.close()
                    process.wait(timeout=15)
            for argv in (['help','--json'],['build','inspect','--json'],['command','list','--json']):
                launch('essential-'+argv[0],argv,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD':'1'})
            passed=True
    finally:
        a.output.write_text(json.dumps(dict(passed=passed,cases=len(records),records=records,source_receipts=sources,owner_accepted=False,full_0_1_0_complete=False),indent=2)+'\n',encoding='utf-8',newline='\n')
    print('NTFS membership command/frontend cases:',len(records))


if __name__=='__main__':main()
