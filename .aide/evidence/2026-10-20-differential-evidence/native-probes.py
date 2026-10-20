"""Guest diagnostic: real private parsers through the confined byte-I/O port.

No reference participant is fabricated. This is not a finalized comparison packet.
"""
import hashlib
import importlib.util
import json
import lzma
import os
from pathlib import Path
import shutil
import struct
import sys
import tarfile
import traceback


PROBE_FILES = (
    'source/portable/primitives/checked.c', 'source/portable/primitives/checked.h',
    'source/portable/primitives/view.c', 'source/portable/primitives/view.h',
    'source/portable/primitives/extent.c', 'source/portable/primitives/extent.h',
    'source/portable/mbr/mbr.c', 'source/portable/mbr/mbr.h',
    'source/portable/ebr/ebr.c', 'source/portable/ebr/ebr.h',
    'source/portable/gpt/encoding.c', 'source/portable/gpt/gpt.c', 'source/portable/gpt/gpt.h',
    'source/runtime/command/json.cpp', 'source/runtime/command/json.h',
    'tests/unit/mbr_probe.cpp', 'tests/unit/gpt_probe.cpp',
    'tests/differential/collector.py', 'tests/differential/evidence.py',
    'tests/differential/projections.py', 'tests/corpus/partition_images.py')


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def exercise(g, work, environment, executor, result):
    sys.path.insert(0, str(g.ROOT/'tests/differential'))
    from collector import Output, executable_hash, process_result
    from evidence import Artifacts, digest
    from projections import field, native_projection, native_request, strict_json
    corpus=g.load('native_probe_corpus',g.ROOT/'tests/corpus/partition_images.py')
    expected=json.loads((g.ROOT/'expected.json').read_bytes())['native_probes']
    recipes=corpus.recipes()
    assert sha(g.ROOT/'tests/corpus/partition_images.py')==expected['generator_sha256']
    facts=[dict(name=v['name'],family=v['family'],bytes=len(v['data']),sha256=digest(v['data']),checks=v['checks']) for v in recipes]
    assert facts==expected['cases'] and len(recipes)==35
    observations=work/'probe-observations';observations.mkdir()
    output=Output(observations);report=dict(status='running',cases=[],compilation=[],guards=[],reference_tools_run=False,
        finalized_comparison_packet=False,full_campaign_qualified=False)
    result['probe_run']=report
    (work/'probe-obj').mkdir()
    binary=Path(environment['PATH'].split(os.pathsep)[0]);cl=binary/'cl.exe';link=binary/'link.exe'
    common=['/nologo','/W4','/WX','/MT','/O2','/GS','/sdl','/guard:cf','/I'+str(g.ROOT/'source'),'/Fo'+str(work/'probe-obj')+'\\']
    c_sources=[path for path in PROBE_FILES if path.endswith('.c')]
    cpp_sources=['source/runtime/command/json.cpp','tests/unit/mbr_probe.cpp','tests/unit/gpt_probe.cpp']
    compile_commands=[
        [str(cl),*common,'/TC','/c',*[str(g.ROOT/path) for path in c_sources]],
        [str(cl),*common,'/std:c++14','/EHsc','/permissive-','/utf-8','/c',*[str(g.ROOT/path) for path in cpp_sources]]]
    probes={family:work/(family+'-probe.exe') for family in ('mbr','gpt')}
    for family in probes:
        names=['checked','view','extent','json',family+'_probe',*(['mbr','ebr'] if family=='mbr' else ['encoding','gpt'])]
        compile_commands.append([str(link),'/nologo','/INCREMENTAL:NO','/MACHINE:X64','/DYNAMICBASE','/NXCOMPAT','/guard:cf',
            '/SUBSYSTEM:CONSOLE','/OUT:'+str(probes[family]),*[str(work/'probe-obj'/(name+'.obj')) for name in names],'kernel32.lib'])
    for index,argv in enumerate(compile_commands):
        value=executor(argv=argv,cwd=work,payload=b'',timeout=120,output_limit=1048576)
        status=process_result(value,dict(timeout_seconds=120))
        raw={name:output.artifact('compile/'+str(index)+'.'+name,value[name]) for name in ('stdout','stderr')}
        report['compilation'].append(dict(argv=argv,status=status,raw=raw,exit_code=value['exit_code']))
        assert status=='completed'
    report['artifacts']={}
    for family,path in probes.items():
        body=path.read_bytes();offset=struct.unpack_from('<I',body,60)[0]
        assert body[offset:offset+4]==b'PE\0\0' and struct.unpack_from('<H',body,offset+4)[0]==0x8664
        report['artifacts'][family]=dict(bytes=len(body),sha256=executable_hash(str(path)),pe_machine='0x8664')
        value=executor(argv=[str(path),'--guard'],cwd=work,payload=b'',timeout=15,output_limit=65536)
        status=process_result(value,dict(timeout_seconds=15))
        raw={name:output.artifact('guards/'+family+'.'+name,value[name]) for name in ('stdout','stderr')}
        report['guards'].append(dict(family=family,status=status,raw=raw))
        assert status=='completed' and not value['stderr'] and value['stdout'].rstrip()==expected['guard_stdout'][family].encode()
    for recipe in recipes:
        case={k:v for k,v in recipe.items() if k!='data'};data=recipe['data'];name=case['name']
        fixture=output.artifact('cases/'+name+'.img',data)
        source=observations/fixture['path'];identity_before=source.stat()
        payload=(json.dumps(native_request(data,case),separators=(',',':'))+'\n').encode()
        request=output.artifact('cases/'+name+'.request',payload)
        probe=probes[case['family']];executable_before=executable_hash(str(probe))
        assert executable_before==report['artifacts'][case['family']]['sha256']
        value=executor(argv=[str(probe)],cwd=work,payload=payload,timeout=15,output_limit=1048576)
        status=process_result(value,dict(timeout_seconds=15))
        raw={stream:output.artifact('cases/'+name+'.'+stream,value[stream]) for stream in ('stdout','stderr')}
        row=dict(name=name,family=case['family'],fixture=fixture,request=request,raw=raw,status=status,checks=[],
            call_index=executor.calls,executable_before_sha256=executable_before,
            file_before=dict(volume=str(identity_before.st_dev),identity=str(identity_before.st_ino),bytes=identity_before.st_size),
            execution={key:value[key] for key in ('outcome','exit_code','elapsed_seconds','terminal')})
        report['cases'].append(row)
        assert status=='completed' and not value['stderr']
        observed=strict_json(value['stdout'])
        for path,wanted in case['checks'].items():
            actual=field(observed,path);matched=type(actual) is type(wanted) and actual==wanted
            row['checks'].append(dict(path=path,expected=wanted,actual=actual,matched=matched));assert matched,(name,path,wanted,actual)
        row['projection']=native_projection(observed,case['family'])
        identity_after=source.stat();after_descriptor,after=Artifacts(observations).capture(fixture['path'])
        row['input_after']=after_descriptor
        row['file_after']=dict(volume=str(identity_after.st_dev),identity=str(identity_after.st_ino),bytes=identity_after.st_size)
        row['executable_after_sha256']=executable_hash(str(probe))
        row['input_unchanged']=after==data and (identity_before.st_dev,identity_before.st_ino)==(identity_after.st_dev,identity_after.st_ino)
        assert row['input_unchanged'] and row['executable_after_sha256']==row['executable_before_sha256']
    checks=sum(len(row['checks']) for row in report['cases']);assert checks==64 and len(report['cases'])==35
    conflict=next(row for row in report['cases'] if row['name']=='gpt-valid-disagreement')['projection']
    assert conflict['comparison']==2 and len(conflict['candidates'])==2 and conflict['candidates'][0]['rows']!=conflict['candidates'][1]['rows']
    report.update(status='pass',checks=checks,scope='Actual private native probe diagnostics;no reference or finalized comparison',
                  source_inputs={path:sha(g.ROOT/path) for path in PROBE_FILES})


def retain(g, work, executor, result):
    from collector import Output
    assert all(row['terminal'] and row['temporary_files_removed'] for row in executor.observations)
    observations=work/'probe-observations';report=result['probe_run']
    output=Output(observations)
    output.artifact('native-results.json',(json.dumps(report,indent=2)+'\n').encode())
    entries=[]
    for path in sorted(observations.rglob('*')):
        if not path.is_file():continue
        assert path.stat().st_nlink==1 and not path.is_symlink() and path.stat().st_size<=2097152
        entries.append(dict(path=path.relative_to(observations).as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
    assert len(entries)<=256 and sum(row['bytes'] for row in entries)<=16*1024*1024
    archive=work/'retained.tar.xz'
    with archive.open('xb') as raw:
        with lzma.LZMAFile(raw,'w',filters=[dict(id=lzma.FILTER_LZMA2,dict_size=1048576,preset=6)]) as compressed:
            with tarfile.open(fileobj=compressed,mode='w|') as stream:
                for row in entries:stream.add(observations/row['path'],arcname=row['path'],recursive=False)
    assert archive.stat().st_size<=1048576
    with tarfile.open(archive,'r:xz') as stream:
        members=stream.getmembers();assert [v.name for v in members]==[v['path'] for v in entries]
        for member,row in zip(members,entries):
            assert member.isfile() and member.size==row['bytes']
            body=stream.extractfile(member).read(2097153);assert hashlib.sha256(body).hexdigest()==row['sha256']
    # Every executor call has retired its owned job. Export only this bounded,
    # hash-verified receipt archive before the capped image is removed.
    shutil.copyfile(archive,g.ROOT/'retained.tar.xz')
    report['archive']=dict(bytes=archive.stat().st_size,sha256=sha(archive),entries=entries)
    result['archive_sha256']=report['archive']['sha256']
    result['probe_archive_verified']=True


def coordinate(g):
    port=g.load('native_probe_port',g.ROOT/'native-port.py')
    def extension(work,environment,executor,result):
        try:exercise(g,work,environment,executor,result)
        except BaseException:
            report=result.get('probe_run')
            if report is not None:
                report.update(status='fail',error=traceback.format_exc()[-16384:])
                if all(row['terminal'] and row['temporary_files_removed'] for row in executor.observations):
                    retain(g,work,executor,result)
            raise
        else:retain(g,work,executor,result)
    port.coordinate(g,extension=extension)
