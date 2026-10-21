"""Real contained native namespace, immutable inventory and injected regressions."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import json
import lzma
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import traceback
import winreg

HERE=Path(__file__).resolve().parent
ROOT=HERE if HERE==Path('C:/ProgramData/DiskEd/qualification') else HERE.parents[2]
CORE=tuple('source/'+p for p in (
 'platform/windows/storage/identity_queries.cpp','platform/windows/storage/observation_worker.cpp',
 'platform/windows/storage/namespace_worker.cpp','platform/windows/storage/storage_worker.cpp',
 'platform/windows/storage/storage_queries.cpp','platform/windows/storage/volume_namespace.cpp',
 'providers/windows/storage_inventory.cpp','providers/windows/storage_frame_reader.cpp',
 'providers/windows/storage_graph.cpp','providers/windows/storage_identity.cpp',
 'providers/windows/volume_inventory.cpp','providers/windows/namespace_graph.cpp',
 'providers/windows/inventory_session.cpp','providers/image/local_file.cpp',
 'runtime/command/json.cpp','runtime/graph/snapshot.cpp','runtime/graph/capture.cpp','portable/hash/sha256.cpp'))
TESTS=tuple('tests/windows/native/'+p for p in ('native_namespace_probe.cpp','volume_fixture.cpp','volume_namespace_probe.cpp','namespace_worker_probe.cpp','namespace_graph_probe.cpp'))
PYTHON=tuple('tests/windows/'+p for p in ('test_volume_namespace.py','test_namespace_worker.py','test_namespace_graph.py','native_namespace_observations.py','native_volume_observations.py'))+('tests/differential/projections.py','spec/catalog/nt-native-namespace-prototype.json')


def source_closure():
    found=set(CORE+TESTS+PYTHON);pending=list(CORE+TESTS)
    while pending:
        path=ROOT/pending.pop()
        for name in re.findall(r'^\s*#\s*include\s*"([^"\r\n]+)"',path.read_text(),re.MULTILINE):
            candidates=[path.parent/name,ROOT/'source'/name]
            selected=next((p.resolve() for p in candidates if p.is_file()),None)
            if selected is None or not selected.is_relative_to(ROOT.resolve()):raise ValueError('Unresolved owned include: '+name)
            relative=selected.relative_to(ROOT.resolve()).as_posix()
            if relative not in found:found.add(relative);pending.append(relative)
    return tuple(sorted(found))


FILES=source_closure()
def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def identified(path):
    info=path.stat();assert path.is_file() and 0<info.st_size<=67108864
    digest=hashlib.sha256()
    with path.open('rb') as stream:
        for body in iter(lambda:stream.read(65536),b''):digest.update(body)
    return dict(path=str(path),bytes=info.st_size,sha256=digest.hexdigest())


def retire_tree(path,work):
    resolved=path.resolve();assert resolved.is_relative_to(work.resolve()) and resolved!=work.resolve()
    entries=list(path.rglob('*'));assert len(entries)<=2000
    for p in [path,*entries]:
        info=p.lstat();assert not info.st_file_attributes&0x400 and (p.is_dir() or info.st_nlink==1)
    for p in entries:
        if p.is_file():p.unlink()
    for p in sorted((p for p in entries if p.is_dir()),key=lambda p:len(p.parts),reverse=True):p.rmdir()
    path.rmdir()


def exercise(g,work,environment,executor,result):
    sys.path.insert(0,str(g.ROOT/'tests/windows'));sys.path.insert(0,str(g.ROOT/'tests/differential'))
    from native_namespace_observations import validate
    from projections import strict_json
    expected=json.loads((g.ROOT/'expected.json').read_bytes())['contained_namespace'];state=json.loads((g.ROOT/'scratch/state.json').read_bytes())
    report=dict(status='running',source_revision=json.loads((g.ROOT/'source-manifest.json').read_bytes())['base_revision'],
        source_inputs={p:sha(g.ROOT/p) for p in FILES},known_volume=state['volume_unique_id'],known_mount=state['drive'],image_uuid=state['image_uuid'],architectures=[],provider_admitted=False)
    result['contained_namespace']=report
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion') as key:
        report['windows_registry']={name:winreg.QueryValueEx(key,name)[0] for name in ('CurrentBuildNumber','UBR','EditionID','BuildLabEx')}
    assert report['windows_registry']['CurrentBuildNumber']=='19045' and report['windows_registry']['UBR']==7548
    components=[Path('C:/Windows')/folder/name for folder in ('System32','SysWOW64') for name in ('kernel32.dll','KernelBase.dll','advapi32.dll')]
    components += [Path('C:/Program Files (x86)/Windows Kits/10/Include/10.0.19041.0/um')/name for name in ('Windows.h','fileapi.h')]
    report['installed_component_files']=[identified(path) for path in components]
    directory=work/'contained-observations';directory.mkdir()
    def artifact(name,body):
        assert '/' not in name and '\\' not in name and len(body)<=2097152
        path=directory/name
        with path.open('xb') as stream:stream.write(body)
        return dict(path=name,bytes=len(body),sha256=sha(path))
    def call(label,args,timeout=15):
        value=executor(argv=list(map(str,args)),cwd=work,payload=b'',timeout=timeout,output_limit=524288)
        row=dict(label=label,argv=list(map(str,args)),call_index=executor.calls,process_id=executor.observations[-1]['process_id'],outcome=value['outcome'],exit_code=value['exit_code'],terminal=value['terminal'],elapsed_seconds=value['elapsed_seconds'],stdout=artifact(label+'.stdout',value['stdout']),stderr=artifact(label+'.stderr',value['stderr']))
        assert value['terminal'] and executor.observations[-1]['temporary_files_removed'];return row,value
    kernel=C.WinDLL('kernel32',use_last_error=True);query=g.W.bind(kernel,'GetVolumeNameForVolumeMountPointW',T.BOOL,T.LPCWSTR,T.LPWSTR,T.DWORD)
    def witness():
        name=C.create_unicode_buffer(64);g.W.require(query(state['drive'],name,len(name)))
        assert name.value.lower()==state['volume_unique_id'].lower();return name.value
    report['witness_before']=witness()
    for selection in expected['arches']:
        arch=selection['name'];pointer=selection['pointer_bytes'];local=work/('build-'+arch);local.mkdir();obj=local/'obj';obj.mkdir()
        binary=Path('C:/BuildTools/VC/Tools/MSVC/14.44.35207/bin/Hostx64')/selection['tool_subdir']
        env=dict(environment,PATH=str(binary)+os.pathsep+environment['PATH'])
        if pointer==4:env['LIB']=env['LIB'].replace('/x64','/x86').replace('\\x64','\\x86')
        executor.environment=env
        row=dict(name=arch,pointer_bytes=pointer,cases=[],compilation=[],regressions=[],guards=[]);report['architectures'].append(row)
        row['compiler_environment']={key:env[key] for key in ('PATH','INCLUDE','LIB')}
        row['toolchain']=[identified(binary/name) for name in ('cl.exe','link.exe','c1xx.dll','c2.dll','dumpbin.exe')]
        common=['/nologo','/W4','/WX','/MT','/O2','/GS','/sdl','/guard:cf','/std:c++14','/EHsc','/permissive-','/utf-8','/D_WIN32_WINNT=0x0A00','/I'+str(g.ROOT/'source')]
        native=local/'native_namespace_probe.exe'
        def compile_call(label,args):
            response=local/(label+'.rsp');response.write_text(subprocess.list2cmdline(args),encoding='utf-8')
            response_hash=sha(response)
            entry,value=call(arch+'-'+label,[binary/'cl.exe','@'+str(response)],timeout=120);row['compilation'].append(entry)
            entry.update(expanded_arguments=args,response_sha256=response_hash)
            assert sha(response)==response_hash
            assert value['outcome']=='exited' and value['exit_code']==0
            if label=='native':assert b'19.44.35228' in value['stdout']+value['stderr']
        compile_call('native',['/Bv',*common,'/Fo'+str(obj)+'\\','/Fe'+str(native),*[str(g.ROOT/p) for p in CORE],str(g.ROOT/TESTS[0]),'kernel32.lib','advapi32.lib','/link','/DYNAMICBASE','/NXCOMPAT','/guard:cf'])
        row['executable']=dict(bytes=native.stat().st_size,sha256=sha(native))
        for case in expected['cases']:
            entry,value=call(arch+'-'+case,[native,case]);row['cases'].append(entry)
            assert value['outcome']=='exited' and value['exit_code']==0 and not value['stderr']
            validate(strict_json(value['stdout']),case,pointer,row['executable']['sha256'],state['volume_unique_id'],state['drive'])
        for label,mode in [('invalid-role','__disked_nt_native_namespace_worker'),('invalid-command','unknown')]:
            entry,value=call(arch+'-'+label,[native,mode]);row['guards'].append(entry)
            assert value['outcome']=='exited' and value['exit_code']==2 and not value['stdout'] and not value['stderr']
        fixture_obj=obj/'observation_worker_fixture.obj'
        compile_call('fixture-host',[*common,'/DDISKED_NT_NAMESPACE_WORKER_TESTING=1','/c','/Fo'+str(fixture_obj),str(g.ROOT/'source/platform/windows/storage/observation_worker.cpp')])
        objects=[p for p in obj.glob('*.obj') if p.name not in ('native_namespace_probe.obj','observation_worker.obj','observation_worker_fixture.obj')]
        for regression in expected['legacy_regressions']:
            kind=regression['name'];probe=local/(regression['probe']+'.exe')
            sources=[str(g.ROOT/('tests/windows/native/'+regression['probe']+'.cpp'))]
            if kind=='adapter':sources.insert(0,str(g.ROOT/'tests/windows/native/volume_fixture.cpp'))
            else:sources.append(str(obj/'volume_fixture.obj'))
            compile_call('legacy-'+kind,[*common,'/DDISKED_NT_NAMESPACE_WORKER_TESTING=1','/Fo'+str(obj)+'\\','/Fe'+str(probe),*sources,*map(str,objects),str(fixture_obj),'kernel32.lib','advapi32.lib','/link','/DYNAMICBASE','/NXCOMPAT','/guard:cf'])
            output=work/('legacy-'+arch+'-'+kind)
            entry,value=call(arch+'-legacy-'+kind,[sys.executable,'-B',g.ROOT/('tests/windows/'+regression['script']),'--probe',probe,'--output',output,'--pointer-bytes',pointer],timeout=180)
            row['regressions'].append(entry)
            assert value['outcome']=='exited' and value['exit_code']==0
            summary=strict_json((output/'results.json').read_bytes());assert summary['status']=='pass' and summary['pointer_bytes']==pointer and summary['assertions']>=regression['minimum_assertions'] and all(c['passed'] is True for c in summary['checks'])
            count=summary.get('controller_executions',summary.get('native_executions',summary.get('processes',summary.get('executions'))));count=len(count) if isinstance(count,list) else count
            assert count>=regression['minimum_controllers']
            inventory=[];kept={}
            for path in sorted(output.iterdir()):
                assert path.is_file() and path.stat().st_size<=2097152
                body=path.read_bytes();inventory.append(dict(path=path.name,bytes=len(body),sha256=sha(path)))
                if path.name=='results.json' or path.name.startswith(('native_table-binding-refused.','native_error-binding-refused.')):
                    kept[path.name]=body.decode('utf-8')
            bundle=dict(all_entry_hashes=inventory,retained_utf8=kept,other_success_payloads_retained=False)
            entry['regression_evidence']=artifact(arch+'-regression-'+kind+'.json',(json.dumps(bundle,indent=2)+'\n').encode())
            entry['summary']=dict(controllers=count,assertions=summary['assertions'],actual_child_launches=summary.get('actual_child_launches'),checks=len(summary['checks']))
            retire_tree(output,work)
        all_images=[native,*[local/(p['probe']+'.exe') for p in expected['legacy_regressions']]]
        entry,value=call(arch+'-imports',[binary/'dumpbin.exe','/nologo','/headers','/imports',*all_images]);row['imports']=entry
        assert value['outcome']=='exited' and value['exit_code']==0 and not value['stderr']
        row['executables']={p.name:dict(bytes=p.stat().st_size,sha256=sha(p)) for p in all_images}
        assert row['executables'][native.name]==row['executable']
        retire_tree(local,work)
    report['witness_after']=witness();assert report['witness_after']==report['witness_before']
    assert executor.calls==expected['port_calls']==60
    executor.environment=environment
    report.update(status='native_containment_and_publication_pass',port_calls=executor.calls,full_product_qualified=False,owner_accepted=False,release_qualified=False)


def retain(g,work,result):
    report=result['contained_namespace'];directory=work/'contained-observations'
    (directory/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    entries=[]
    for path in sorted(directory.iterdir()):
        info=path.lstat();assert path.is_file() and info.st_nlink==1 and not info.st_file_attributes&0x400 and info.st_size<=2097152
        entries.append(dict(path=path.name,bytes=info.st_size,sha256=sha(path)))
    assert len(entries)<=128 and sum(v['bytes'] for v in entries)<=8388608
    archive=work/'retained.tar.xz'
    with archive.open('xb') as raw:
        with lzma.LZMAFile(raw,'w',filters=[dict(id=lzma.FILTER_LZMA2,dict_size=1048576,preset=6)]) as compressed:
            with tarfile.open(fileobj=compressed,mode='w|') as stream:
                for entry in entries:stream.add(directory/entry['path'],arcname=entry['path'],recursive=False)
    assert archive.stat().st_size<=1048576
    with tarfile.open(archive,'r:xz') as stream:
        members=stream.getmembers();assert [v.name for v in members]==[v['path'] for v in entries]
        for member,entry in zip(members,entries):assert member.isfile() and member.size==entry['bytes'] and hashlib.sha256(stream.extractfile(member).read(2097153)).hexdigest()==entry['sha256']
    shutil.copyfile(archive,g.ROOT/'retained.tar.xz');result['archive_sha256']=sha(archive)
    report['archive']=dict(bytes=archive.stat().st_size,sha256=result['archive_sha256'],entries=entries)


def coordinate(g):
    port=g.load('contained_namespace_port',g.ROOT/'native-port.py')
    def extension(work,environment,executor,result):
        try:exercise(g,work,environment,executor,result)
        except BaseException:
            report=result.get('contained_namespace')
            if report is not None:
                report.update(status='fail',error=traceback.format_exc()[-16384:])
                if all(v['terminal'] and v['temporary_files_removed'] for v in executor.observations) and (work/'contained-observations').is_dir():retain(g,work,result)
            raise
        else:retain(g,work,result)
    port.coordinate(g,extension=extension)
