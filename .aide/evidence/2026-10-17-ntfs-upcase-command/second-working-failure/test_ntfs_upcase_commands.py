"""Complete retained table bytes through real common product actions, generated images only."""
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import queue
import subprocess
import sys
import tempfile
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'images'))
from test_ntfs_upcase_capture import UpcaseVolume
from test_ntfs_capture import bytes_at
from test_ntfs_commands import canonical, digest, file_digest, Gui, wait, Gate
from test_ntfs_directory_commands import CAPS, prefix
from protocol_trace import ProtocolTrace


def fixtures():
    for minor in (0, 1):
        for controls in ({}, dict(cluster=512, mft_first=21), dict(usa=42), dict(size=32768),
                         dict(list_form='resident', split=True, reverse=True),
                         dict(list_form='nonresident', extension_only=True),
                         dict(mft_closure=True, list_form='nonresident', split=True)):
            yield dict(minor=minor, offset=173, **controls), None, 0, None
        yield dict(minor=minor), '3.'+str(minor), 0, None
        yield dict(minor=minor), '3.'+str(1-minor), 4, 'ntfs_volume_version'
    yield dict(minor=0, offset=(1 << 32)+4096), None, 0, None
    for controls, diagnostic in [(dict(data_length=131071, place_data=False), 'ntfs_upcase_stream_size'),
                                 (dict(initialized=131071), 'ntfs_upcase_stream_size'),
                                 (dict(base_options=dict(flags=3)), 'ntfs_upcase_record'),
                                 (dict(table_runs=[(32, 8)], place_data=False), 'ntfs_upcase_physical_alias')]:
        yield controls, None, 4, diagnostic


def compact_record(row):
    if row is None:
        return None
    def attribute(value):
        if 'runs' in value:
            value['runs'] = prefix(value['runs'], 16, 2048)
        return value
    if 'attributes' in row:
        row['attributes'] = prefix(row['attributes'], 16, 8192, attribute)
    return row


def chunks(raw):
    assert len(raw) == 131072
    return dict(schema='org.disked.ntfs-upcase-bytes-projection/1', encoding='hex-chunks/1',
        bytes='131072', sha256='sha256:'+hashlib.sha256(raw).hexdigest(), complete=True,
        chunks=[dict(byte_offset=str(at), byte_count='16384', hex=raw[at:at+16384].hex())
                for at in range(0, 131072, 16384)])


def expected_observation(original):
    value = copy.deepcopy(original)
    value.update(schema='org.disked.ntfs-upcase-projection/1', original_schema=original['schema'])
    value['regions'] = prefix(original['regions'], 64, 16384)
    for key in ('primary', 'mirror', 'volume_record', 'upcase_record'):
        value[key] = compact_record(value[key])
    for closure in value.get('record_closures', {}).values():
        closure['extensions'] = prefix(closure['extensions'], 8, 8192, compact_record)
        if closure.get('join') is not None:
            for key in ('records', 'parts', 'runs', 'required_records'):
                closure['join'][key] = prefix(closure['join'][key], 8, 2048)
        if 'entries' in closure.get('attribute_list', {}):
            closure['attribute_list']['entries'] = prefix(closure['attribute_list']['entries'], 64, 8192)
    if value['upcase'] is not None:
        table = value['upcase']
        raw = table.pop('table_hex')
        table.update(original_schema=table['schema'], schema='org.disked.ntfs-upcase-table-projection/1',
                     table_data=chunks(bytes.fromhex(raw)) if table['complete'] else None)
    return value


def stable(response):
    value = copy.deepcopy(response['result'])
    for key in ('context', 'worker', 'file_sha256', 'capture_sha256', 'capture'):
        value.pop(key, None)
    def clean(row):
        if isinstance(row, dict):
            wrapped = all(k in row for k in ('items', 'total', 'returned', 'omitted'))
            return {k:clean(v) for k,v in row.items() if k not in ('source_id', 'epoch')
                    and not (wrapped and k == 'sha256')}
        return [clean(v) for v in row] if isinstance(row, list) else row
    return clean(value)


def main():
    parser = argparse.ArgumentParser()
    for key in ('exe', 'fault', 'worker', 'worker-fault', 'probe', 'root', 'output'):
        parser.add_argument('--'+key, type=Path, required=True)
    a = parser.parse_args()
    for key in vars(a): setattr(a, key, getattr(a, key).resolve())
    env = {k:v for k,v in os.environ.items() if not k.startswith('DISKED_')}
    records, sources = [], []
    passed = False
    def record(name, **values):
        print('CASE', name, flush=True); records.append(dict(name=name, **values))
    def params(v, path, version=None):
        value = dict(path=str(path), view='ntfs-upcase', volume_offset=v.input['offset'], volume_bytes=v.input['length'])
        if version is not None: value['ntfs_version'] = version
        return value
    def options(v, version=None):
        value = ['--view','ntfs-upcase','--volume-offset',v.input['offset'],'--volume-bytes',v.input['length']]
        return value + (['--ntfs-version', version] if version is not None else [])
    def wire(parameters, ident='upcase:req'):
        return dict(schema='org.disked.request/1',request_id=ident,command='image.inspect',parameters=parameters,required_features=[])
    def run(name, command, data=b'', settings=None, expected=0):
        started = time.monotonic()
        process = subprocess.run(list(map(str,command)),input=data,capture_output=True,cwd=a.root,
                                 env=dict(env,**(settings or {})),timeout=30)
        raw = a.output.with_name(a.output.stem+'-response-'+str(len(records))+'.json')
        raw.write_bytes(process.stdout)
        record(name,command=list(map(str,command)),exit_code=process.returncode,elapsed_seconds=time.monotonic()-started,
               stdin_sha256='sha256:'+hashlib.sha256(data).hexdigest(),
               stdin_utf8=data.decode('utf-8') if len(data)<=16384 else None,
               stdout_sha256='sha256:'+hashlib.sha256(process.stdout).hexdigest(),stdout_bytes=len(process.stdout),
               stderr=process.stderr.decode(errors='replace'),raw_output=str(raw))
        assert process.returncode == expected and not process.stderr, records[-1]
        assert not any(n<32 and n not in (9,10,13) for n in process.stdout)
        return json.loads(process.stdout)
    def launch(name, argv, expected=0, exe=None, **extra):
        value = run(name,[exe or a.exe,*argv],expected=expected,**extra)
        assert len(canonical(value))+1 <= 524288 and value['operation_id'] is None
        return value
    def pure(parameters, full=None, status='captured', **extra):
        body=dict(parameters=parameters,status=status,**extra)
        if full is not None: body['file']=full
        return run('pure-projection',[a.probe],data=canonical(body))
    def worker(v, path, version=None, fixture=None):
        body=dict(path=str(path),offset=v.input['offset'],length=v.input['length'],capture_epoch='9',upcase=True,limits=CAPS)
        if version is not None:body['profile']=version
        if fixture is not None:body['fixture']=fixture
        result=run('independent-worker',[a.worker_fault if fixture is not None else a.worker],data=canonical(body));assert result['has_snapshot'],result
        return result['snapshot']
    def compare(left,right):
        assert left['status']==right['status'] and left['diagnostics']==right['diagnostics']
        assert stable(left)==stable(right)
    def facts(response,v,diagnostic=None):
        result=response['result'];obs=result['observation'];capture=result['capture'];context=result['context'];owned=result['worker']['worker']
        assert result['schema']=='org.disked.ntfs-upcase-inspection/1'
        assert result['scope']=='ordinary-local-file-ntfs-upcase' and result['applicability_scope']=='volume-uppercase-table'
        assert obs['schema']=='org.disked.ntfs-upcase-projection/1' and obs['original_schema']=='org.disked.ntfs-upcase-observation-prototype/1'
        assert not result['authorizes_effects'] and not any(obs[k] for k in ('atomic_snapshot','current_source_authority','effects_authorized'))
        assert capture['domain']['provider']=='ntfs-upcase-file-prototype' and capture['domain']['limits']==CAPS
        assert not any(k in capture['domain'] for k in ('directory_reference','directory_limits','target_limit'))
        assert owned['observation']=='exited' and owned['pid']==context['pid']==capture['process_id']
        assert owned['created']==context['created']==capture['process_created']
        assert context['code_sha256']==hashlib.sha256(a.exe.read_bytes()).hexdigest()
        assert context['image_profile']=='ordinary-file-ntfs-upcase'
        assert result['capture_sha256']==digest(capture)
        table=obs['upcase']
        if table is not None and table['complete']:
            assert 'table_hex' not in table and table['table_data']==chunks(v.table)
            assert table['base_reference']==str(v.reference) and table['base_record_sha256']=='sha256:'+hashlib.sha256(v.base_raw).hexdigest()
            assert table['volume_serial']==str(int.from_bytes(bytes_at(v.input,v.offset+72,8),'little'))
            assert table['source_id']==obs['source_id']==capture['source_identity_digest'] and table['epoch']==obs['epoch']==capture['sequence']
            restored=b''.join(bytes.fromhex(c['hex']) for c in table['table_data']['chunks'])
            assert restored==v.table and len(restored)==131072
        if diagnostic:assert obs['diagnostic']==diagnostic and 'ntfs_capture_incomplete' in [d['code'] for d in response['diagnostics']]
    try:
        with tempfile.TemporaryDirectory(prefix='disked-upcase-command-') as temp:
            folder=Path(temp).resolve();baseline=None
            for index,(controls,version,exit_code,diagnostic) in enumerate(fixtures()):
                v=UpcaseVolume(**controls);path=folder/f'generated-{index}.img'
                # Reuse the actual ordinary/sparse fixture writer; it checks native sparse support.
                import test_ntfs_file as held
                owner=type('Owned',(),{})();owner.root=folder;owner.index=index
                owner.skipTest=lambda reason: (_ for _ in ()).throw(AssertionError(reason))
                _,path=held.Tests.fixture(owner,v,path.name)
                before=file_digest(path)
                value=launch('cli-'+str(index),['--json','image','inspect',str(path),*options(v,version)],exit_code)
                facts(value,v,diagnostic)
                protocol=launch('stdio-'+str(index),['protocol','serve','--json'],exit_code,data=canonical(wire(params(v,path,version))))
                compare(value,protocol);assert file_digest(path)==before
                sources.append(dict(controls=controls,version=version,bytes=path.stat().st_size,before_sha256=before,after_sha256=file_digest(path)))
                if index==6:baseline=(v,path,value)
            v,path,value=baseline;full=worker(v,path);selected=pure(params(v,path),full)
            assert selected['port_called'] and selected['exit_code']==0
            assert selected['response']['result']['observation']==expected_observation(full['observation'])
            assert selected['response']['result']['file_sha256']==digest(full);compare(value,selected['response'])
            for fault,call in [('short',len(v.initial_reads)),('changed',2*len(v.initial_reads))]:
                partial=worker(v,path,fixture=dict(capture_fault=fault,capture_call=str(call)))
                report=pure(params(v,path),partial)
                assert report['exit_code']==4 and report['port_called']
                projected=report['response']['result']['observation']
                assert projected==expected_observation(partial['observation']) and not projected['applicable']
                if fault=='short':assert projected['upcase']['table_data'] is None and not projected['upcase']['complete']
                else:
                    assert projected['upcase']['table_data']==chunks(v.table)
                    assert 'ntfs_source_changed' in [d['code'] for d in report['response']['diagnostics']]
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
                assert p.returncode==0;result=json.loads(report.read_bytes());compare(value,result['response']);record(frontend,response_sha256=digest(result['response']))
            for field in ('source_id','epoch','volume_offset','volume_bytes','base_reference','base_record_sha256','schema','table_bytes','table_sha256','volume_serial'):
                bad=copy.deepcopy(full);table=bad['observation']['upcase'];old=table[field]
                table[field]='wrong' if field in ('source_id','schema','table_sha256','base_record_sha256') else str(int(old)+1)
                # Serial has no duplicate summary field. Type-check it here; exact bytes are parent-authenticated.
                if field=='volume_serial':table[field]=True
                result=pure(params(v,path),bad);assert result['exit_code']==4 and result['response']['diagnostics'][0]['code']=='internal_error',field
            for change in ('odd','upper','short','byte','incomplete-hash','incomplete-hex','unreached','outer-effect','atomic','provider','domain','selector','window','limits'):
                bad=copy.deepcopy(full);table=bad['observation']['upcase'];capture=bad['capture']
                if change=='odd':table['table_hex']=table['table_hex'][:-1]
                elif change=='upper':table['table_hex']=table['table_hex'].upper()
                elif change=='short':table['table_hex']=table['table_hex'][:-4]
                elif change=='byte':table['table_hex']=('00' if table['table_hex'][:2]!='00' else '01')+table['table_hex'][2:]
                elif change=='incomplete-hash':table.update(complete=False,table_hex=None)
                elif change=='incomplete-hex':table.update(complete=False,table_sha256=None)
                elif change=='unreached':
                    bad['observation']['upcase']=None;bad['observation']['applicable']=False;capture['observed_stable']=False
                elif change=='outer-effect':bad['authorizes_effects']=True
                elif change=='atomic':bad['observation']['atomic_snapshot']=True
                elif change=='provider':capture['domain']['provider']='ntfs-file-prototype';capture['capture_domain']=digest(capture['domain'])
                elif change=='domain':capture['capture_domain']='sha256:'+'0'*64
                elif change=='selector':capture['selector']='3.0'
                elif change=='window':bad['observation']['volume_offset']='1'
                elif change=='limits':capture['domain']['limits']['read_requests']='511';capture['capture_domain']=digest(capture['domain'])
                result=pure(params(v,path),bad);assert result['exit_code']==4 and result['response']['diagnostics'][0]['code']=='internal_error',change
            # Prefixes bind complete original arrays even where display omits entries.
            padded=copy.deepcopy(full)
            for key in ('primary','mirror','volume_record','upcase_record'):
                row=padded['observation'][key];row['attributes']=row.get('attributes',[])*40
            result=pure(params(v,path),padded);assert result['exit_code']==0
            assert result['response']['result']['observation']==expected_observation(padded['observation'])
            assert any(result['response']['result']['observation'][k]['attributes']['omitted']!='0' for k in ('primary','mirror','volume_record','upcase_record'))
            boundary=copy.deepcopy(full);boundary['capture']['padding']=[]
            size=pure(params(v,path),boundary)['wire_bytes'];remaining=524288-size
            while remaining:
                charge=3 if boundary['capture']['padding'] else 2;n=min(32768,remaining-charge);assert n>=0
                if remaining-n-charge in (1,2):n-=3
                boundary['capture']['padding'].append('x'*n);remaining-=n+charge
            result=pure(params(v,path),boundary);assert result['exit_code']==0 and result['wire_bytes']==524288
            boundary['capture']['padding'][-1]+='x';result=pure(params(v,path),boundary)
            assert result['exit_code']==4 and result['response']['diagnostics'][0]['code']=='ntfs_report_limit'
            missing=folder/'missing.img'
            for key,invalid in [('volume_bytes','511'),('volume_offset',str((1<<63)-512)),('directory_reference','0'),('ntfs_target_limit','64'),('upcase_format','auto'),('fat_copy','0'),('lookup',dict(directory='0',names=['A'])),('ntfs_version',True)]:
                parameters=params(v,missing);parameters[key]=invalid
                result=launch('invalid-before-source',['protocol','serve','--json'],2,exe=a.fault,
                    settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD':'1'},data=canonical(wire(parameters)))
                assert result['diagnostics'][0]['code']=='invalid_parameter' and not pure(parameters,status='unresolved')['port_called']
            for flags in (['--directory-reference','0'],['--ntfs-target-limit','64'],['--upcase-format','auto'],['--ntfs-version','2.0']):
                result=launch('invalid-cli-before-source',['--json','image','inspect',str(missing),*options(v),*flags],2,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD':'1'})
                assert result['diagnostics'][0]['code']=='invalid_option_value'
            assert run('known-kind-admitted',[a.probe],data=canonical(dict(private_kind='upcase')))==dict(rejected=False)
            assert run('unknown-kind-rejected',[a.probe],data=canonical(dict(private_kind='unknown')))==dict(rejected=True,diagnostic='ntfs_inspection_kind')
            for status,expected in [('refused',3),('unresolved',6)]:assert pure(params(v,path),status=status)['exit_code']==expected
            launch('missing-source',['--json','image','inspect',str(missing),*options(v)],3)
            for flag,expected,diagnostic in [('VERIFY_CHANGED',4,'ntfs_source_changed'),('VERIFY_ERROR',4,'ntfs_capture_incomplete'),('INVALID_REPLY',6,'ntfs_reader_validation_unresolved'),('HANG',6,None)]:
                result=launch('fault-'+flag,['--json','image','inspect',str(path),*options(v)],expected,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_'+flag:'1'})
                if diagnostic:assert diagnostic in [d['code'] for d in result['diagnostics']]
                if flag=='VERIFY_CHANGED':assert result['result']['observation']['upcase']['table_data']==chunks(v.table)
            launch('normal-fault-isolation',['--json','image','inspect',str(path),*options(v)],settings={'DISKED_NTFS_COMMAND_TEST_HANG':'1'})
            gate=Gate();process=subprocess.Popen([str(a.fault),'protocol','serve','--format=ndjson'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,cwd=a.root,env=dict(env,DISKED_NTFS_COMMAND_TEST_GATE=gate.name))
            trace=ProtocolTrace(process,a.output,canonical)
            try:
                before=file_digest(path);trace.send(wire(params(v,path)));gate.entered();trace.event('gate_entered');expired=trace.get(6)
                assert expired['status']=='unknown' and expired['diagnostics'][0]['code']=='request_wait_expired'
                try:
                    with path.open('r+b'):raise AssertionError('Source writable before actual completion')
                except PermissionError:pass
                trace.send(wire(params(v,path),'busy'));assert trace.get(2)['diagnostics'][0]['code']=='request_resource_limit'
                essential=wire({},'essential');essential['command']='command.list';trace.send(essential);assert trace.get(2)['status']=='completed'
                trace.event('gate_release');gate.release();after=None
                for _ in range(35):
                    time.sleep(.1);trace.send(wire(params(v,path),'fresh'));after=trace.get(3)
                    if after['status']=='completed':break
                    assert after['diagnostics'][0]['code']=='request_resource_limit'
                trace.event('final_assertion',after=after and after['status'],queued=trace.messages.qsize())
                assert after and after['status']=='completed' and trace.messages.empty()
                process.stdin.close();code=process.wait(timeout=8);stderr=process.stderr.read();assert code==6 and not stderr
                assert file_digest(path)==before;record('late-retains-source-slot',trace=str(trace.log),frames=trace.frames)
            except BaseException as error:
                trace.event('failure',error=repr(error),parent_returncode=process.poll(),queued=trace.messages.qsize());trace.snapshot('failure_pending_responses');raise
            finally:
                gate.release();gate.close()
                if process.poll() is None:
                    if not process.stdin.closed:process.stdin.close()
                    process.wait(timeout=15)
                trace.event('teardown',parent_returncode=process.poll(),queued=trace.messages.qsize())
            for argv in (['help','--json'],['build','inspect','--json'],['command','list','--json']):
                launch('essential-'+argv[0],argv,exe=a.fault,settings={'DISKED_NTFS_COMMAND_TEST_OPEN_GUARD':'1'})
            passed=True
    finally:
        a.output.write_text(json.dumps(dict(passed=passed,cases=len(records),records=records,source_receipts=sources,
            recipe_sha256='sha256:'+hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),owner_accepted=False,full_0_1_0_complete=False),indent=2)+'\n',encoding='utf-8',newline='\n')


if __name__=='__main__':main()
