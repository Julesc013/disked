"""Explicit actual namespace queries in the existing capped ordinary guest worker."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import json
import lzma
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tarfile
import traceback
import winreg

FILES=('source/platform/windows/storage/volume_namespace.cpp','source/platform/windows/storage/volume_namespace.h',
       'source/providers/windows/volume_inventory.cpp','source/providers/windows/volume_inventory.h',
       'source/runtime/command/json.cpp','source/runtime/command/json.h','tests/windows/native/volume_native_probe.cpp',
       'tests/windows/native_volume_observations.py','tests/differential/projections.py')


def sha(path):return hashlib.sha256(path.read_bytes()).hexdigest()


def exercise(g,work,environment,executor,result):
    sys.path.insert(0,str(g.ROOT/'tests/windows'));sys.path.insert(0,str(g.ROOT/'tests/differential'))
    from native_volume_observations import validate
    from projections import strict_json
    expected=json.loads((g.ROOT/'expected.json').read_bytes())['volume_namespace']
    state=json.loads((g.ROOT/'scratch/state.json').read_bytes())
    report=dict(status='running',source_revision=json.loads((g.ROOT/'source-manifest.json').read_bytes())['base_revision'],
                cases=[],source_inputs={path:sha(g.ROOT/path) for path in FILES},known_volume=state['volume_unique_id'],
                known_mount=state['drive'],image_uuid=state['image_uuid'],provider_admitted=False,physical_devices_opened=False)
    result['volume_namespace']=report
    with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,r'SOFTWARE\Microsoft\Windows NT\CurrentVersion') as key:
        report['windows_registry']={name:winreg.QueryValueEx(key,name)[0] for name in ('CurrentBuildNumber','UBR','EditionID','BuildLabEx')}
    assert report['windows_registry']['CurrentBuildNumber']=='19045' and report['windows_registry']['UBR']==7548
    directory=work/'volume-observations';directory.mkdir()
    def artifact(name,body):
        assert '/' not in name and '\\' not in name and len(body)<=524288
        path=directory/name
        with path.open('xb') as stream:stream.write(body)
        return dict(path=name,bytes=len(body),sha256=sha(path))
    def call(label,args,*,timeout=15):
        value=executor(argv=args,cwd=work,payload=b'',timeout=timeout,output_limit=524288)
        row=dict(label=label,argv=args,call_index=executor.calls,process_id=executor.observations[-1]['process_id'],
            outcome=value['outcome'],exit_code=value['exit_code'],elapsed_seconds=value['elapsed_seconds'],terminal=value['terminal'],
            stdout=artifact(label+'.stdout',value['stdout']),stderr=artifact(label+'.stderr',value['stderr']))
        assert value['terminal'] and executor.observations[-1]['temporary_files_removed']
        return row,value
    kernel=C.WinDLL('kernel32',use_last_error=True)
    query=g.W.bind(kernel,'GetVolumeNameForVolumeMountPointW',T.BOOL,T.LPCWSTR,T.LPWSTR,T.DWORD)
    def witness():
        name=C.create_unicode_buffer(64);g.W.require(query(state['drive'],name,len(name)))
        assert name.value.lower()==state['volume_unique_id'].lower()
        return dict(volume=name.value,mount=state['drive'])
    report['witness_before']=witness()
    binary=Path(environment['PATH'].split(os.pathsep)[0]);probe=work/'volume-native-probe.exe'
    args=['/nologo','/W4','/WX','/MT','/O2','/GS','/sdl','/guard:cf','/std:c++14','/EHsc','/permissive-','/utf-8',
        '/D_WIN32_WINNT=0x0A00','/I'+str(g.ROOT/'source'),'/Fo'+str(work/'obj')+'\\','/Fe'+str(probe),
        *[str(g.ROOT/path) for path in FILES if path.endswith('.cpp')],
        'kernel32.lib','advapi32.lib','/link','/DYNAMICBASE','/NXCOMPAT','/guard:cf']
    response=work/'volume-compile.rsp';response.write_text(subprocess.list2cmdline(args),encoding='utf-8')
    row,value=call('compile',[str(binary/'cl.exe'),'@'+str(response)],timeout=120);report['compile']=row;report['compile_arguments']=args
    assert value['outcome']=='exited' and value['exit_code']==0
    report['executable']=dict(bytes=probe.stat().st_size,sha256=sha(probe))
    for case in expected['cases']:
        mode=case['mode'];label=mode[2:]
        row,value=call(label,[str(probe),mode]);report['cases'].append(row)
        assert value['outcome']=='exited' and value['exit_code']==case['exit_code'] and not value['stderr']
        actual=strict_json(value['stdout'])
        row['review']=validate(actual,mode,result['native_identity']['sid'],row['process_id'],state['volume_unique_id'],state['drive'])
    row,value=call('imports',[str(binary/'dumpbin.exe'),'/nologo','/headers','/imports',str(probe)])
    report['imports']=row;assert value['outcome']=='exited' and value['exit_code']==0 and not value['stderr']
    report['witness_after']=witness();assert report['witness_after']==report['witness_before']
    assert sha(probe)==report['executable']['sha256'] and executor.calls==expected['port_calls']==16
    report.update(status='known_guest_volume_observed',namespace_complete=report['cases'][1]['review']['namespace_complete'],
                  port_calls=executor.calls,full_work_unit_complete=False,owner_accepted=False,release_qualified=False)


def retain(g,work,result):
    report=result['volume_namespace'];directory=work/'volume-observations'
    (directory/'results.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    entries=[]
    for path in sorted(directory.iterdir()):
        info=path.lstat();assert path.is_file() and info.st_nlink==1 and not info.st_file_attributes&0x400 and info.st_size<=524288
        entries.append(dict(path=path.name,bytes=info.st_size,sha256=sha(path)))
    assert len(entries)<=32 and sum(v['bytes'] for v in entries)<=4194304
    archive=work/'retained.tar.xz'
    with archive.open('xb') as raw:
        with lzma.LZMAFile(raw,'w',filters=[dict(id=lzma.FILTER_LZMA2,dict_size=1048576,preset=6)]) as compressed:
            with tarfile.open(fileobj=compressed,mode='w|') as stream:
                for row in entries:stream.add(directory/row['path'],arcname=row['path'],recursive=False)
    assert archive.stat().st_size<=1048576
    with tarfile.open(archive,'r:xz') as stream:
        members=stream.getmembers();assert [v.name for v in members]==[v['path'] for v in entries]
        for member,row in zip(members,entries):
            assert member.isfile() and member.size==row['bytes'] and hashlib.sha256(stream.extractfile(member).read(524289)).hexdigest()==row['sha256']
    shutil.copyfile(archive,g.ROOT/'retained.tar.xz');result['archive_sha256']=sha(archive)
    report['archive']=dict(bytes=archive.stat().st_size,entries=entries,sha256=result['archive_sha256'])


def coordinate(g):
    port=g.load('volume_native_port',g.ROOT/'native-port.py')
    def extension(work,environment,executor,result):
        try:exercise(g,work,environment,executor,result)
        except BaseException:
            report=result.get('volume_namespace')
            if report is not None:
                report.update(status='fail',error=traceback.format_exc()[-16384:])
                if all(v['terminal'] and v['temporary_files_removed'] for v in executor.observations) and (work/'volume-observations').is_dir():retain(g,work,result)
            raise
        else:retain(g,work,result)
    port.coordinate(g,extension=extension)
