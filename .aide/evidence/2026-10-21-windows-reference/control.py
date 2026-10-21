"""Actual native/API observations of four owned virtual images; UI remains pending."""
import hashlib
import json
import lzma
import os
from pathlib import Path
import platform
import re
import shutil
import sys
import tarfile
import traceback

FILES=(
 'source/portable/primitives/checked.c','source/portable/primitives/checked.h',
 'source/portable/primitives/view.c','source/portable/primitives/view.h',
 'source/portable/primitives/extent.c','source/portable/primitives/extent.h',
 'source/portable/mbr/mbr.c','source/portable/mbr/mbr.h','source/portable/ebr/ebr.c','source/portable/ebr/ebr.h',
 'source/portable/gpt/encoding.c','source/portable/gpt/gpt.c','source/portable/gpt/gpt.h',
 'source/runtime/command/json.cpp','source/runtime/command/json.h',
 'tests/unit/mbr_probe.cpp','tests/unit/gpt_probe.cpp','tests/differential/windows_api_probe.cpp',
 'tests/differential/windows_observations.py','tests/differential/projections.py',
 'tests/differential/collector.py','tests/differential/evidence.py','tests/corpus/windows_partitions.py')

def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()

def exercise(g,work,environment,executor,result):
    sys.path.insert(0,str(g.ROOT/'tests/differential'))
    from collector import Output, executable_hash, process_result
    from projections import field, native_projection, strict_json
    from windows_observations import request, native_expectations, api_projection, matching_candidates
    recipes=g.load('windows_reference_fixtures',g.ROOT/'tests/corpus/windows_partitions.py')
    media_module=g.load('windows_reference_media',g.ROOT/'windows-reference-media.py')
    expected=json.loads((g.ROOT/'expected.json').read_bytes())['windows_reference']
    facts=expected['fixtures'];assert facts['status']=='expected_before_native_or_windows_evaluation'
    assert facts['generator_sha256']=='sha256:'+sha(g.ROOT/facts['generator'])
    assert [recipes.describe(name) for name in recipes.CASES]==facts['cases']
    observations=work/'reference-observations';observations.mkdir();output=Output(observations)
    report=dict(status='running',scope=__doc__,cases=[],compilation=[],guards=[],ui_observations=0,
                campaign_complete=False,expected_observation_tuples=facts['required_observations'],actual_observation_tuples=[],
                source_revision=json.loads((g.ROOT/'source-manifest.json').read_bytes())['base_revision'],
                source_inputs={path:'sha256:'+sha(g.ROOT/path) for path in FILES},all_owned_media_retired=True)
    result['windows_reference']=report
    import winreg
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion') as key:
        system={name:winreg.QueryValueEx(key,name)[0] for name in ('CurrentBuildNumber','UBR','EditionID','BuildLabEx')}
    report['environment']=dict(os=platform.system(),build=platform.version(),architecture=platform.machine(),
        python=sys.version,windows_registry=system,observer_actor=result['native_identity'],
        coordinator_identity_source='Outer PowerShell receipt verifies BLACKGLASS-HYPE\\Agents')
    components=[Path(os.environ['WINDIR'])/'System32'/name for name in ('kernel32.dll','KernelBase.dll','virtdisk.dll')]
    components += [Path(os.environ['WINDIR'])/'System32/drivers'/name for name in ('disk.sys','partmgr.sys','vhdmp.sys')]
    components += [Path('C:/Program Files (x86)/Windows Kits/10/Include/10.0.19041.0/um')/name for name in ('Windows.h','winioctl.h','virtdisk.h')]
    report['components']={}
    for path in components:
        assert path.is_file() and 0<path.stat().st_size<=67108864
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for body in iter(lambda:stream.read(65536),b''):digest.update(body)
        report['components'][str(path)]=dict(bytes=path.stat().st_size,sha256='sha256:'+digest.hexdigest())
    binary=Path(environment['PATH'].split(os.pathsep)[0]);obj=work/'reference-obj';obj.mkdir()
    probes={family:work/(family+'-probe.exe') for family in ('mbr','gpt')}
    api=work/'windows-api-probe.exe'
    common=['/nologo','/W4','/WX','/MT','/O2','/GS','/sdl','/guard:cf','/I'+str(g.ROOT/'source'),'/Fo'+str(obj)+'\\']
    c_sources=[path for path in FILES if path.endswith('.c')]
    cpp_sources=['source/runtime/command/json.cpp','tests/unit/mbr_probe.cpp','tests/unit/gpt_probe.cpp']
    commands=[
      [str(binary/'cl.exe'),*common,'/TC','/c',*[str(g.ROOT/path) for path in c_sources]],
      [str(binary/'cl.exe'),*common,'/std:c++14','/EHsc','/permissive-','/utf-8','/c',*[str(g.ROOT/path) for path in cpp_sources]]]
    for family in probes:
        names=['checked','view','extent','json',family+'_probe',*(['mbr','ebr'] if family=='mbr' else ['encoding','gpt'])]
        commands.append([str(binary/'link.exe'),'/nologo','/INCREMENTAL:NO','/MACHINE:X64','/DYNAMICBASE','/NXCOMPAT','/guard:cf',
            '/SUBSYSTEM:CONSOLE','/OUT:'+str(probes[family]),*[str(obj/(name+'.obj')) for name in names],'kernel32.lib'])
    def call(label,argv,payload=b'',timeout=15):
        value=executor(argv=argv,cwd=work,payload=payload,timeout=timeout,output_limit=1048576)
        row=dict(label=label,argv=argv,call_index=executor.calls,status=process_result(value,dict(timeout_seconds=timeout)),
            execution={k:value[k] for k in ('outcome','exit_code','elapsed_seconds','terminal')},
            raw={stream:output.artifact(label+'.'+stream,value[stream]) for stream in ('stdout','stderr')})
        return row,value
    for index,argv in enumerate(commands):
        row,value=call('compile/native-'+str(index),argv,timeout=120);report['compilation'].append(row);assert row['status']=='completed'
    for family,path in probes.items():
        row,value=call('guards/'+family,[str(path),'--guard']);report['guards'].append(row)
        assert row['status']=='completed' and value['stdout'].rstrip()==expected['native_guard_stdout'][family].encode() and not value['stderr']
    argv=[str(binary/'cl.exe'),*common,'/std:c++14','/EHsc','/permissive-','/utf-8','/D_WIN32_WINNT=0x0A00',
          '/Fe'+str(api),str(g.ROOT/'tests/differential/windows_api_probe.cpp'),str(obj/'json.obj'),'kernel32.lib','advapi32.lib',
          '/link','/DYNAMICBASE','/NXCOMPAT','/guard:cf']
    row,value=call('compile/api',argv,timeout=120);report['compilation'].append(row);assert row['status']=='completed'
    row,value=call('api-abi',[str(api),'--abi']);report['abi_call']=row;assert row['status']=='completed' and not value['stderr']
    abi=strict_json(value['stdout']);report['abi']=abi
    assert abi==expected['sdk_abi']
    row,value=call('guards/invalid-handle',[str(api)],b'{"handle":"0","expected_bytes":"4194304","attachment_uuid":"invalid","nonce":"invalid"}\n')
    report['guards'].append(row);assert row['status']=='refused' and value['exit_code']==2 and not value['stdout']
    report['executables']={str(path):executable_hash(str(path)) for path in [*probes.values(),api]}
    report['toolchain']={str(binary/name):executable_hash(str(binary/name)) for name in ('cl.exe','link.exe')}
    try:
        for fact in facts['cases']:
            name=fact['name'];data=recipes.generate(name)
            row=dict(fixture=fact,native={},windows_api={},ui=dict(status='not_run'),media={});report['cases'].append(row)
            source=work/(name+'-native.img')
            with source.open('xb') as stream:
                for offset in range(0,len(data),65536):stream.write(data[offset:offset+65536])
            before=source.stat();assert before.st_nlink==1 and not before.st_file_attributes&0x400
            native_body=source.read_bytes();assert 'sha256:'+hashlib.sha256(native_body).hexdigest()==fact['sha256']
            payload=(json.dumps(request(native_body,fact),separators=(',',':'))+'\n').encode()
            native_call,value=call('cases/'+name+'.native',[str(probes[fact['family']])],payload)
            row['native'].update(call=native_call,request=output.artifact('cases/'+name+'.request',payload),checks=[])
            assert native_call['status']=='completed' and not value['stderr']
            observed=strict_json(value['stdout'])
            for path,wanted in native_expectations(fact).items():
                actual=field(observed,path);matched=type(actual) is type(wanted) and actual==wanted
                row['native']['checks'].append(dict(path=path,expected=wanted,actual=actual,matched=matched));assert matched
            row['native']['projection']=native_projection(observed,fact['family'])
            after=source.stat();assert (before.st_dev,before.st_ino)==(after.st_dev,after.st_ino)
            assert 'sha256:'+hashlib.sha256(source.read_bytes()).hexdigest()==fact['sha256']
            row['native']['source']=dict(file_id=[str(before.st_dev),str(before.st_ino)],bytes=len(data),sha256=fact['sha256'],unchanged=True)
            source.unlink();row['native']['source_removed']=not source.exists()
            report['actual_observation_tuples'].append(dict(name=name,participant='native',kind='partition-candidates'))
            media=media_module.Media(g,work,name,data,fact['sha256'],abi,row['media']);builder=executor.payload_builder
            report['all_owned_media_retired']=False
            try:
                media.start()
                def transfer(process,job):
                    body=media.transfer(process,job)
                    row['windows_api']['request']=output.artifact('cases/'+name+'.api-request',body)
                    return body
                executor.payload_builder=transfer
                row['windows_api']['attempted']=True
                api_call,value=call('cases/'+name+'.api',[str(api)])
                row['windows_api']['call']=api_call
                assert api_call['status']=='completed' and not value['stderr']
                actual=strict_json(value['stdout']);row['windows_api']['projection']=api_projection(actual,abi)
                row['windows_api']['operation_status']='completed' if actual['queries']['layout']['success'] else 'refused'
                assert actual['nonce']==media.nonce and actual['attachment_uuid']==str(media.identifier)
                assert actual['device_number']==int(re.search(r'([0-9]+)$',row['media']['physical_path'])[1])
                projection=row['windows_api']['projection']
                # Reference disagreement/refusal is an observation. Native byte
                # validity does not prescribe a Windows selection or acceptance.
                matches=matching_candidates(row['native']['projection'],projection)
                row['windows_api']['matching_native_candidates']=matches
                row['windows_api']['comparison_status']='not_comparable' if projection is None else 'agreement' if matches else 'disagreement'
                report['actual_observation_tuples'].append(dict(name=name,participant='windows-api',kind='drive-layout-ex'))
            finally:
                executor.payload_builder=builder;media.quiescent=executor.active_job is None and not executor.poisoned
                media.close();report['all_owned_media_retired']=True
        assert executor.calls==expected['port_calls']==25
        assert len(report['actual_observation_tuples'])==8
        conflict=next(v for v in report['cases'] if v['fixture']['name']=='gpt-conflicting')['native']['projection']
        assert conflict['comparison']==2 and len(conflict['candidates'])==2
        assert report['executables']=={str(path):executable_hash(str(path)) for path in [*probes.values(),api]}
        report.update(status='available_native_api_slice_pass',evidence_status='incomplete',missing_observations=[
            v for v in facts['required_observations'] if v not in report['actual_observation_tuples']],port_calls=executor.calls)
        assert len(report['missing_observations'])==4 and all(v['participant']=='disk-management' for v in report['missing_observations'])
    finally:
        for path in work.glob('*-native.img'):
            info=path.lstat();assert info.st_nlink==1 and not info.st_file_attributes&0x400 and path.parent==work
            path.unlink()

def retain(g,work,result):
    from collector import Output
    report=result['windows_reference'];directory=work/'reference-observations'
    Output(directory).artifact('results.json',(json.dumps(report,indent=2)+'\n').encode())
    entries=[]
    for path in sorted(directory.rglob('*')):
        if not path.is_file():continue
        assert path.stat().st_nlink==1 and not path.is_symlink() and path.stat().st_size<=2097152
        entries.append(dict(path=path.relative_to(directory).as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
    assert len(entries)<=256 and sum(v['bytes'] for v in entries)<=8388608
    archive=work/'retained.tar.xz'
    with archive.open('xb') as raw:
        with lzma.LZMAFile(raw,'w',filters=[dict(id=lzma.FILTER_LZMA2,dict_size=1048576,preset=6)]) as compressed:
            with tarfile.open(fileobj=compressed,mode='w|') as stream:
                for row in entries:stream.add(directory/row['path'],arcname=row['path'],recursive=False)
    assert archive.stat().st_size<=1048576
    with tarfile.open(archive,'r:xz') as stream:
        members=stream.getmembers();assert [v.name for v in members]==[v['path'] for v in entries]
        for member,row in zip(members,entries):
            assert member.isfile() and member.size==row['bytes']
            assert hashlib.sha256(stream.extractfile(member).read(2097153)).hexdigest()==row['sha256']
    shutil.copyfile(archive,g.ROOT/'retained.tar.xz');result['archive_sha256']=sha(archive)
    report['archive']=dict(bytes=archive.stat().st_size,sha256=result['archive_sha256'],entries=entries)

def coordinate(g):
    port=g.load('windows_reference_port',g.ROOT/'native-port.py')
    def extension(work,environment,executor,result):
        try:exercise(g,work,environment,executor,result)
        except BaseException:
            report=result.get('windows_reference')
            if report is not None:
                report.update(status='fail',error=traceback.format_exc()[-16384:])
                if all(v['terminal'] and v['temporary_files_removed'] for v in executor.observations):retain(g,work,result)
            raise
        else:retain(g,work,result)
    try:port.coordinate(g,extension=extension)
    finally:
        path=g.ROOT/'proof-result.json'
        if path.exists():
            value=json.loads(path.read_bytes());report=value.get('windows_reference',{})
            attempted=any(v.get('windows_api',{}).get('attempted') for v in report.get('cases',[]))
            terminal=any('call' in v.get('windows_api',{}) for v in report.get('cases',[]))
            value.update(scope=__doc__,reference_tools_run=True if terminal else None if attempted else False,
                         windows_api_observations=sum(v['participant']=='windows-api' for v in report.get('actual_observation_tuples',[])),
                         all_owned_media_retired=report.get('all_owned_media_retired',True),ui_observations=0,campaign_complete=False)
            path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
