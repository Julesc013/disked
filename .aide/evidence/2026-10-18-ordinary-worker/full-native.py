"""Pinned x64 AppContainer build followed by ordinary restricted guest tests."""
import ctypes as C
import base64
from ctypes import wintypes as T
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import stat
import struct
import subprocess
import sys
import time
import traceback
import xml.etree.ElementTree as ET
import zipfile
from pathlib import PurePosixPath

ROOT=Path('C:/ProgramData/DiskEd/qualification')
SOURCE=ROOT/'source'


class CampaignStop(InterruptedError):
    """The owning host controller requested retirement, never a product failure."""


def require_uninterrupted(root, nonce, *, allow_probe=False):
    path=Path(root)/'stop-request.json'
    try:info=path.lstat()
    except FileNotFoundError:return
    if not stat.S_ISREG(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400 or info.st_size>4096:
        raise ValueError('Invalid bounded stop request')
    request=json.loads(path.read_bytes())
    if (type(request) is not dict or set(request)!={'schema','nonce','reason','observed_growth_bytes','limit_bytes'} or
            request['schema']!='org.disked.guest-stop/1' or request['nonce']!=nonce or
            request['reason'] not in ('shared_backing_growth','controller_probe','operator_cancel') or
            type(request['limit_bytes']) is not int or request['limit_bytes']!=1073741824 or
            type(request['observed_growth_bytes']) is not int or
            not 0<=request['observed_growth_bytes']<2**64):
        raise ValueError('Stop request identity or bounds differ')
    if request['reason']=='controller_probe':
        if not allow_probe:raise ValueError('Stop proof is not enabled for this campaign')
    elif request['reason']=='shared_backing_growth' and request['observed_growth_bytes']<=request['limit_bytes']:
        raise ValueError('Backing-growth request does not exceed its declared limit')
    raise CampaignStop(request)


def junit_result(path,name,exit_code):
    """A completed command is not a substitute for its exact JUnit receipt."""
    result=dict(passed=False,reason='missing',retain=False)
    try:info=Path(path).lstat()
    except FileNotFoundError:return result
    if (not stat.S_ISREG(info.st_mode) or info.st_nlink!=1
            or getattr(info,'st_file_attributes',0)&0x400 or not 0<=info.st_size<=1048576):
        return dict(result,reason='invalid_receipt_form')
    with Path(path).open('rb') as stream:body=stream.read(1048577)
    if len(body)>1048576:return dict(result,reason='receipt_byte_bound')
    result.update(retain=True,sha256=hashlib.sha256(body).hexdigest(),bytes=len(body))
    if b'<!DOCTYPE' in body.upper() or b'<!ENTITY' in body.upper():return dict(result,reason='dtd_or_entity_refused')
    try:root=ET.fromstring(body)
    except ET.ParseError:return dict(result,reason='malformed_xml')
    if root.tag not in ('testsuite','testsuites'):return dict(result,reason='invalid_root')
    cases=list(root.iter('testcase'));result['case_count']=len(cases)
    if len(cases)!=1 or cases[0].get('name')!=name:return dict(result,reason='case_identity')
    case=cases[0]
    if (case.get('status') not in (None,'run','pass','passed')
            or any(node.tag in ('failure','error','skipped') for node in root.iter())):
        return dict(result,reason='case_failed_or_skipped')
    for suite in (node for node in root.iter() if node.tag in ('testsuite','testsuites')):
        if any(suite.get(key) not in (None,'0') for key in ('failures','errors','skipped','disabled')):
            return dict(result,reason='suite_failure_counter')
        if suite.get('tests') not in (None,'1'):return dict(result,reason='suite_case_counter')
    return dict(result,passed=exit_code==0,reason='passed' if exit_code==0 else 'command_failed')


def coordinate(g):
    helper=g.load('full_crypto',ROOT/'crypto-device.py')
    null_helper=g.load('full_null',ROOT/'null-device.py')
    retention=g.load('full_retention',ROOT/'build-driver.py')
    source_setup=g.load('full_source',ROOT/'guest-source.py')
    fixture_setup=g.load('full_fixture_dacl',ROOT/'fixture-dacl.py')
    capture_setup=g.load('full_owned_window',ROOT/'owned-window.py')
    expected=json.loads((ROOT/'expected.json').read_bytes())['native_x64']
    pixel_setup=g.load('full_pixel_origin',ROOT/'pixel-origin.py') if expected.get('pixel_origin_proof') else None
    manifest=json.loads((ROOT/'source.json').read_bytes())
    result=dict(status='running',source_revision=manifest['revision'],full_x64_product_suite_run=False,
                all_owned_processes_retired=False,crypto_device_retired=False,commands=[],tests=[],owner_accepted=False)
    grant,instance,archive,job,child,null_grant=None,None,None,None,None,None
    source_prepared=False;quiescent=True;fixture_broker=None
    ordinary=False;directory_grant=False
    campaign_started=time.monotonic()

    def stop():
        nonlocal job,child,quiescent
        if job:result.setdefault('job_retirements',[]).append(g.retire_job(job));job=None
        if child:child.wait(timeout=10);child.close();child=None
        quiescent=True

    def json_record(raw):
        lines=raw.decode('utf-8').splitlines()
        warning='Failed to find real location of '+sys.executable
        if lines and lines[0]==warning:
            result.setdefault('python_runtime_diagnostics',[]).append(lines.pop(0))
        return json.loads('\n'.join(lines))

    def shared_read_access(add):
        nonlocal directory_grant
        sid=state['profile_sids'][0]
        paths=[str(Path('C:/')),str(Path('C:/ProgramData')),str(Path('C:/ProgramData/DiskEd')),str(ROOT)]
        journal=ROOT/'scoped-directory-access.json'
        if add:directory_grant=True
        entry=dict(nonce=state['nonce'],sid=sid,paths=paths,phase='pending' if add else 'removing')
        journal.write_text(json.dumps(entry)+'\n')
        script=source_setup.directory_script(sid,paths,add)
        call=subprocess.run([str(Path(os.environ['WINDIR'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),
            '-NoProfile','-EncodedCommand',base64.b64encode(script.encode('utf-16-le')).decode('ascii')],capture_output=True,timeout=30)
        if len(call.stdout)+len(call.stderr)>32768:raise RuntimeError('Directory access observation bound')
        result.setdefault('directory_access',[]).append(dict(add=add,exit_code=call.returncode,output=call.stdout.decode(errors='replace')))
        if call.returncode:raise RuntimeError('Scoped directory read delta failed: '+call.stderr.decode(errors='replace'))
        entry['phase']='active' if add else 'retired';journal.write_text(json.dumps(entry)+'\n');directory_grant=add

    def directory_acl(path,sddl):
        g.W.plain_directory(path)
        a=C.WinDLL('advapi32',use_last_error=True);k=C.WinDLL('kernel32',use_last_error=True);descriptor=C.c_void_p()
        convert=g.W.bind(a,'ConvertStringSecurityDescriptorToSecurityDescriptorW',T.BOOL,T.LPCWSTR,T.DWORD,C.c_void_p,C.c_void_p)
        dacl=g.W.bind(a,'GetSecurityDescriptorDacl',T.BOOL,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p)
        edit=g.W.bind(a,'SetNamedSecurityInfoW',T.DWORD,T.LPWSTR,C.c_int,T.DWORD,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p)
        free=g.W.bind(k,'LocalFree',C.c_void_p,C.c_void_p)
        g.W.require(convert(sddl,1,C.byref(descriptor),None))
        try:
            present,defaulted,acl=T.BOOL(),T.BOOL(),C.c_void_p()
            g.W.require(dacl(descriptor,C.byref(present),C.byref(acl),C.byref(defaulted)))
            error=edit(str(path),1,0x80000004,None,None,acl,None)
            if error:raise C.WinError(error)
        finally:free(descriptor)

    def artifact_handoff(build):
        # Compile jobs are already quiescent. Only this campaign's new executable
        # files enter the ordinary Medium test profile; never relabel inputs,
        # directories, shared tools, product records or other guest objects.
        a=C.WinDLL('advapi32',use_last_error=True);k=C.WinDLL('kernel32',use_last_error=True)
        open_file=g.W.bind(k,'CreateFileW',T.HANDLE,T.LPCWSTR,T.DWORD,T.DWORD,C.c_void_p,T.DWORD,T.DWORD,T.HANDLE)
        close=g.W.bind(k,'CloseHandle',T.BOOL,T.HANDLE)
        read=g.W.bind(a,'GetSecurityInfo',T.DWORD,T.HANDLE,C.c_int,T.DWORD,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p)
        edit=g.W.bind(a,'SetSecurityInfo',T.DWORD,T.HANDLE,C.c_int,T.DWORD,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p)
        convert=g.W.bind(a,'ConvertSecurityDescriptorToStringSecurityDescriptorW',T.BOOL,C.c_void_p,T.DWORD,T.DWORD,C.c_void_p,C.c_void_p)
        descriptor=g.W.bind(a,'ConvertStringSecurityDescriptorToSecurityDescriptorW',T.BOOL,T.LPCWSTR,T.DWORD,C.c_void_p,C.c_void_p)
        get_sacl=g.W.bind(a,'GetSecurityDescriptorSacl',T.BOOL,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p)
        free=g.W.bind(k,'LocalFree',C.c_void_p,C.c_void_p)
        def security(handle,fields):
            sd=C.c_void_p();text=T.LPWSTR();error=read(handle,1,fields,None,None,None,None,C.byref(sd))
            if error:raise C.WinError(error)
            try:
                g.W.require(convert(sd,1,fields,C.byref(text),None));return text.value
            finally:
                if text:free(C.cast(text,C.c_void_p))
                free(sd)
        paths=sorted((build/'Release').glob('*.exe'));assert 1<=len(paths)<=256
        result['artifact_handoff']=[]
        for path in paths:
            info=path.lstat()
            assert stat.S_ISREG(info.st_mode) and info.st_nlink==1 and not getattr(info,'st_file_attributes',0)&0x400
            handle=open_file(str(path),0x800a0000,1,None,3,0x00200000,None)
            if handle==C.c_void_p(-1).value:raise C.WinError(C.get_last_error())
            desired=C.c_void_p()
            try:
                before=security(handle,7);before_label=security(handle,0x10);digest=retention.sha(path)
                assert before_label=='S:AI(ML;ID;NW;;;LW)',before_label
                g.W.require(descriptor('S:(ML;;NW;;;ME)',1,C.byref(desired),None))
                present,defaulted,sacl=T.BOOL(),T.BOOL(),C.c_void_p()
                g.W.require(get_sacl(desired,C.byref(present),C.byref(sacl),C.byref(defaulted)))
                assert present.value and sacl.value
                error=edit(handle,1,0x10,None,None,None,sacl)
                if error:raise C.WinError(error)
                after_label=security(handle,0x10)
                assert after_label in ('S:(ML;;NW;;;ME)','S:AI(ML;;NW;;;ME)')
                assert security(handle,7)==before and retention.sha(path)==digest
                if path.stem in result['executables']:assert digest==result['executables'][path.stem]['sha256']
                result['artifact_handoff'].append(dict(path=path.relative_to(build).as_posix(),sha256=digest,
                    before_label=before_label,after_label=after_label,bytes_unchanged=True,dacl_owner_group_unchanged=True))
            finally:
                if desired:free(desired)
                close(handle)

    try:
        if not __debug__:raise RuntimeError('Qualification coordinator requires active assertions')
        data=g.actor();private={k:os.environ.pop(k) for k in list(os.environ) if k.startswith('DISKED_TEST_ACTOR_')}
        state=json.loads((ROOT/'scratch/state.json').read_bytes());assert state['size_mib']==512
        prepared=subprocess.run([sys.executable,'-B',str(ROOT/'guest-source.py'),'prepare'],capture_output=True,timeout=180)
        if prepared.returncode:raise RuntimeError('Source preparation: '+prepared.stderr[-4096:].decode(errors='replace'))
        source_prepared=True
        result['source_prepared']=json.loads((ROOT/'source-prepared.json').read_bytes())
        assert json.loads((SOURCE/'spec/catalog/native-fixture-timeouts.json').read_bytes())==expected['fixture_io_review']
        work=g.W.plain_directory(state['work']);(work/'owner.json').write_text(json.dumps(dict(root=str(SOURCE))))
        compile_work=g.fresh(work/'compile-x64')
        instance=g.W.Worker(compile_work,control=Path(os.environ['DISKED_WORK_ROOT']),private_station=True,profile_name=state['profile_names'][0])
        assert instance.restricting_sid==state['profile_sids'][0]
        pkg_sid=instance.restricting_sid;coordinator_sid=instance.user_sid
        source_acl='D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;'+coordinator_sid+')(A;OICI;0x1200a9;;;'+pkg_sid+')(A;OICI;0x1200a9;;;'+data['sid']+')'
        shared_acl='D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;'+coordinator_sid+')(A;OICI;0x1301bf;;;'+pkg_sid+')(A;OICI;0x1301bf;;;'+data['sid']+')'
        directory_acl(SOURCE,source_acl);directory_acl(work,shared_acl);shared_read_access(True)
        # The same freshly owned output now serves the materialized source. Its
        # source-bound marker is required by the existing managed fixture helper.
        (compile_work/'owner.json').write_text(json.dumps(dict(root=str(SOURCE))))
        build=compile_work/'build';archive=retention.Observations(work/'observations.tar.xz')
        env=dict(os.environ,DISKED_WORK_ROOT=str(work),GIT_OPTIONAL_LOCKS='0',GIT_TERMINAL_PROMPT='0',
                 GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='safe.directory',GIT_CONFIG_VALUE_0=str(SOURCE),
                 MSBUILDDISABLENODEREUSE='1',CMAKE_BUILD_PARALLEL_LEVEL='1',DISKED_TEST_OTHER_VOLUME_ROOT='C:\\',
                 PYTHONOPTIMIZE='0',PYTHONDONTWRITEBYTECODE='1')
        if not expected.get('null_proof_only'):
            dependency=json.loads((ROOT/'pydeps.json').read_bytes())
            assert dependency['requirements_sha256']==retention.sha(SOURCE/'spec/tools/requirements.txt')
            assert dependency['archive_sha256']==retention.sha(ROOT/'pydeps.zip')
            assert 0<len(dependency['files'])<=2000 and 0<dependency['bytes']<=16*1024*1024
            deps=work/'schema-dependencies';deps.mkdir();total=0
            entries={row['path']:row for row in dependency['files']};assert len(entries)==len(dependency['files'])
            with zipfile.ZipFile(ROOT/'pydeps.zip') as payload:
                assert len(payload.infolist())==len(entries) and {p.filename for p in payload.infolist()}==set(entries)
                for info in payload.infolist():
                    name=PurePosixPath(info.filename);row=entries[info.filename]
                    assert not name.is_absolute() and '..' not in name.parts and not any(c in info.filename for c in '\\:*?[]\0')
                    assert not info.is_dir() and not stat.S_ISLNK(info.external_attr>>16) and info.file_size==row['bytes']<=4*1024*1024
                    content=payload.read(info);total+=len(content);assert total<=16*1024*1024
                    assert hashlib.sha256(content).hexdigest()==row['sha256']
                    path=deps/str(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
            assert total==dependency['bytes']
            directory_acl(deps,source_acl);env['PYTHONPATH']=str(deps)
            result['schema_dependencies']=dependency
        for key in ('CL','_CL_','LINK','_LINK_','CFLAGS','CXXFLAGS','LDFLAGS'):env.pop(key,None)
        if expected.get('trace_fat_history'):env['DISKED_TEST_TRACE_FAT_HISTORY']='1'
        cmake=Path('C:/Program Files/CMake/bin/cmake.exe');ctest=cmake.with_name('ctest.exe')
        active_stem=None;active_group=None;active_before=set()

        def stage_powershell7():
            metadata=json.loads((ROOT/'pwsh7.json').read_bytes())
            assert metadata['archive_sha256']==retention.sha(ROOT/'pwsh7.zip')
            entries={row['path']:row for row in metadata['files']}
            assert 0<len(entries)==len(metadata['files'])<=1024 and 0<metadata['bytes']<=256*1024*1024
            tool=work/'powershell7';tool.mkdir();total=0
            with zipfile.ZipFile(ROOT/'pwsh7.zip') as payload:
                assert len(payload.infolist())==len(entries) and {p.filename for p in payload.infolist()}==set(entries)
                for info in payload.infolist():
                    name=PurePosixPath(info.filename);row=entries[info.filename]
                    assert not name.is_absolute() and '..' not in name.parts and not any(c in info.filename for c in '\\:*?[]\0')
                    assert not info.is_dir() and not stat.S_ISLNK(info.external_attr>>16) and info.file_size==row['bytes']<=64*1024*1024
                    content=payload.read(info);total+=len(content);assert total<=256*1024*1024
                    assert hashlib.sha256(content).hexdigest()==row['sha256']
                    path=tool/str(name);path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(content)
            assert total==metadata['bytes'] and (tool/'pwsh.exe').is_file()
            directory_acl(tool,source_acl)
            env['PATH']=str(tool)+os.pathsep+env.get('PATH',os.defpath)
            env['PSModulePath']=str(tool/'Modules')
            result['powershell7_tool']=metadata
            member='recipe/pwsh7.json'
            expected_entry=dict(bytes=(ROOT/'pwsh7.json').stat().st_size,sha256=retention.sha(ROOT/'pwsh7.json'))
            if member in archive.entries:
                assert archive.entries[member]==expected_entry
            else:archive.write(ROOT/'pwsh7.json',member)
            budget()
            return tool/'pwsh.exe'

        def retire_shell_tool():
            tool=work/'powershell7'
            g.S.remove_owned_work(tool,work,'powershell7')
            env['PATH']=original_path
            env.pop('PSModulePath',None)
            assert not tool.exists()

        def release_build_binaries():
            assert quiescent
            keep={'disked.exe','disked_provider_guard.exe'}
            kept={name:retention.sha(build/'Release'/name) for name in keep}
            rows=[]
            for path in build.rglob('*'):
                if path.suffix.lower() not in ('.exe','.obj','.lib','.pdb','.exp','.ilk','.pch'):continue
                if path.parent==build/'Release' and path.name in keep:continue
                for parent in [path.parent,*path.parent.parents]:
                    g.W.plain_directory(parent)
                    if parent==build:break
                info=path.lstat()
                assert path.resolve().is_relative_to(build.resolve()) and stat.S_ISREG(info.st_mode) and info.st_nlink==1 and not getattr(info,'st_file_attributes',0)&0x400
                retention.retire_file(path);rows.append(dict(path=path.relative_to(build).as_posix(),bytes=info.st_size))
            assert kept=={name:retention.sha(build/'Release'/name) for name in keep}
            result['build_binaries_retired_before_invocations']=dict(files=len(rows),logical_bytes=sum(row['bytes'] for row in rows),kept=kept)
            budget()

        def budget():
            if time.monotonic()-campaign_started>7200:raise TimeoutError('Guest campaign overall deadline')
            g.S.check(ROOT)
            allocated=g.S.tree_bytes(work,allocated=True,file_limit=20000,allow_links=True)
            result['peak_scratch_allocated_bytes']=max(result.get('peak_scratch_allocated_bytes',0),allocated)
            capacity=shutil.disk_usage(work)
            assert 0<capacity.total<=512*1024*1024
            result['scratch_filesystem_capacity_bytes']=capacity.total
            result['peak_scratch_filesystem_used_bytes']=max(result.get('peak_scratch_filesystem_used_bytes',0),capacity.used)
            result['minimum_scratch_filesystem_free_bytes']=min(result.get('minimum_scratch_filesystem_free_bytes',capacity.free),capacity.free)
            combined=g.S.tree_bytes(ROOT,allocated=True,file_limit=20000,allow_links=False)
            combined+=g.S.tree_bytes(Path(os.environ['DISKED_WORK_ROOT']),allocated=True,file_limit=20000,allow_links=False)
            combined+=expected.get('host_disposable_reserved_bytes',0)
            if combined>1073741824:raise RuntimeError('Aggregate disposable limit exceeded')
            if archive.path.stat().st_size>32*1024*1024:raise RuntimeError('Retained observations exceed32MiB')

        def drain(final=False):
            if active_stem in ('ntfs-name-order-file-cases','ntfs-name-order-worker-cases'):
                retention.drain_completed_outputs(archive,build,active_stem,final=final)

        def print_control():
            endpoint=env.get('DISKED_OWNED_PRINT_PROBE')
            if not endpoint:return
            request=Path(endpoint+'.json');response=Path(endpoint+'-response.json')
            if not Path(endpoint+'.ready').exists() or response.exists():return
            info=request.lstat()
            if (request.parent!=instance.native_temp or not stat.S_ISREG(info.st_mode) or
                    info.st_nlink!=1 or getattr(info,'st_file_attributes',0)&0x400 or not 0<info.st_size<=4096):
                raise ValueError('Print control request confinement')
            value=json.loads(request.read_bytes())
            if (set(value)!={'window','pid','desktop'} or type(value['pid']) is not int or
                    not 0<value['pid']<2**32 or type(value['window']) is not int or not 0<value['window']<2**64 or
                    value['desktop']!=instance.desktop_name.split('\\')[-1]):
                raise ValueError('Print control request identity')
            k=instance.k
            g.W.bind(k,'OpenProcess',T.HANDLE,T.DWORD,T.BOOL,T.DWORD)
            g.W.bind(k,'IsProcessInJob',T.BOOL,T.HANDLE,T.HANDLE,C.POINTER(T.BOOL))
            g.W.bind(k,'QueryFullProcessImageNameW',T.BOOL,T.HANDLE,T.DWORD,T.LPWSTR,C.POINTER(T.DWORD))
            process=g.W.require(k.OpenProcess(0x1000,False,value['pid']))
            try:
                member=T.BOOL();g.W.require(k.IsProcessInJob(process,job.handle,C.byref(member)))
                image=C.create_unicode_buffer(1024);size=T.DWORD(len(image))
                g.W.require(k.QueryFullProcessImageNameW(process,0,image,C.byref(size)))
                if not member.value or Path(image.value).resolve()!=Path(sys.executable).resolve():
                    raise ValueError('Only the active job owned Python control may be printed')
                observed=subprocess.run([sys.executable,'-B',str(ROOT/'owned-window.py'),str(value['window']),str(value['pid']),value['desktop']],
                    capture_output=True,timeout=10)
                if observed.returncode or len(observed.stdout)+len(observed.stderr)>4096:
                    raise RuntimeError('Owned capture control: '+observed.stderr[-2048:].decode(errors='replace'))
                observation=json.loads(observed.stdout)
                with response.open('x',encoding='utf-8') as stream:json.dump(observation,stream)
                Path(endpoint+'-response.ready').touch(exist_ok=False)
            finally:k.CloseHandle(process)

        def run(label,command,timeout=300,allow_failure=False):
            nonlocal job,child,quiescent
            job=g.S.WindowsJob();quiescent=False;started=time.monotonic();saved=False;stop_request=None
            window_broker=None
            try:
                for key in ('DISKED_WINDOW_CAPTURE_ROOT','DISKED_WINDOW_CAPTURE_NONCE','DISKED_WINDOW_CAPTURE_COORDINATOR_SID'):env.pop(key,None)
                if ordinary and fixture_broker:fixture_broker.start_job(env)
                else:
                    env.pop('DISKED_DACL_FIXTURE_CONTROL',None);env.pop('DISKED_DACL_FIXTURE_NONCE',None)
                if ordinary and (label=='test-frontend.gui_capture' or label=='ordinary-private-ui-diagnostic'):
                    window_broker=capture_setup.Broker(instance,fixture_broker,
                        build/'Release/disked.exe' if label=='test-frontend.gui_capture' else sys.executable,env,
                        expected_sha256=result['executables']['disked']['sha256'] if label=='test-frontend.gui_capture' else retention.sha(Path(sys.executable)))
                if ordinary and label=='pixel-origin-control':
                    window_broker=pixel_setup.Broker(instance,fixture_broker,sys.executable,env,archive,
                        expected_sha256=retention.sha(Path(sys.executable)),retire_job=g.retire_job,
                        check=lambda:(require_uninterrupted(ROOT,state['nonce']),budget()))
                child=instance.launch(list(map(str,command)),env,job,variant='basic-stdio') if ordinary else instance.launch(list(map(str,command)),env,job)
                if window_broker:result['owned_window_scope_controls']=window_broker.prove_refusals(job,child.pid,different_image=label=='test-frontend.gui_capture')
                process_id=child.pid
                log_path=instance.log_path if ordinary else instance.work/'worker.log'
                until=started+timeout
                while child.poll() is None:
                    require_uninterrupted(ROOT,state['nonce'],allow_probe=expected.get('controller_stop_proof') is True)
                    if ordinary and fixture_broker:fixture_broker.poll()
                    if window_broker:window_broker.poll(job)
                    print_control()
                    drain();budget()
                    if log_path.stat().st_size>524288:raise RuntimeError('Bounded native command log exceeded')
                    if time.monotonic()>until:raise TimeoutError(label+' deadline')
                    time.sleep(.2)
                code=child.wait();stop();drain(final=True)
                raw=log_path.read_bytes();assert len(raw)<=524288
                archive.writestr('commands/'+label+'.log',raw);saved=True
                result['commands'].append(dict(label=label,pid=process_id,execution_profile='ordinary' if ordinary else 'appcontainer',arguments=list(map(str,command)),exit_code=code,
                    seconds=time.monotonic()-started,sha256=hashlib.sha256(raw).hexdigest(),tail=raw[-4096:].decode(errors='replace')))
                if code and not allow_failure:raise RuntimeError(label+' failed: '+raw[-2048:].decode(errors='replace'))
                return code,raw
            except CampaignStop as error:
                stop_request=error.args[0]
                result['controller_interruption']=dict(request=stop_request,command=label,product_failure=False)
                raise
            finally:
                stop()
                if window_broker:
                    if label=='pixel-origin-control':result['pixel_origin_preflight']=window_broker.report()
                    records=window_broker.finish(quiescent=quiescent)
                    result.setdefault('owned_window_captures',[]).extend(records)
                    for key in ('DISKED_WINDOW_CAPTURE_ROOT','DISKED_WINDOW_CAPTURE_NONCE','DISKED_WINDOW_CAPTURE_COORDINATOR_SID'):env.pop(key,None)
                if ordinary and fixture_broker:
                    retired=fixture_broker.finish_job(quiescent=quiescent)
                    if retired['requests']:result.setdefault('fixture_dacl_jobs',[]).append(dict(command=label,**retired))
                if stop_request:
                    (ROOT/'stop-acknowledged.json').write_text(json.dumps(dict(
                        nonce=state['nonce'],owned_job_processes_retired=True,command=label))+'\n',encoding='utf-8',newline='\n')
                if 'log_path' in locals() and log_path.exists():
                    if not saved:archive.writestr('commands/'+label+'-incomplete.log',log_path.read_bytes()[:524288])
                    retention.retire_file(log_path)

        def test_group(test):
            nonlocal active_stem,active_group,active_before
            active_stem='ntfs-'+test.removeprefix('image.ntfs_').replace('_','-')+'-cases'
            before={p.name for p in build.iterdir() if p.is_file()}
            active_group=test;active_before=before
            diagnostic=bool(expected.get('diagnose_fat_history'))
            if diagnostic:
                assert focused and test=='evidence.fat_tree_history' and expected['history_diagnostic_seconds']==600
                command=[sys.executable,SOURCE/'tests/evidence/test_fat_tree_history.py',
                    '--probe',build/'Release/fat_tree_history_probe.exe',
                    '--writer',build/'Release/fat_tree_extraction_probe.exe',
                    '--worker',build/'Release/fat_tree_extraction_worker_probe.exe',
                    '--worker-fault',build/'Release/fat_tree_extraction_worker_fault.exe',
                    '--output',build/'fat-tree-history-cases.json']
                observed_command=next(row['command'] for row in registered if row['name']==test)
                normalize=lambda values:[os.path.normcase(os.path.normpath(str(value))) for value in values]
                assert normalize(observed_command)==normalize(command)
                code,_=run('diagnose-fat-history-complete',command,expected['history_diagnostic_seconds'],allow_failure=True)
                observed=json.loads((build/'fat-tree-history-cases.json').read_bytes())
                summary=dict(methods=observed['methods'],cases=observed['cases'],
                    native_histories=len(observed['native_histories']),owned_histories=len(observed['owned_histories']))
                passed=code==0 and observed['passed'] is True and summary['methods']==13 and summary['native_histories']==16 and summary['owned_histories']==3 and summary['cases']==len(observed['records'])>0
                result.setdefault('diagnostics',[]).append(dict(name=test,exit_code=code,passed=passed,
                    deadline_seconds=600,original_ctest_deadline_seconds=300,original_ctest_qualified=False,
                    observations=summary,scope='Original assertion body outside CTest for elapsed-time diagnosis only; no full/native-group qualification'))
            else:
                properties=next(row['properties'] for row in registered if row['name']==test)
                ctest_seconds=next((row['value'] for row in properties if row['name']=='TIMEOUT'),expected['bounds']['group_seconds'])
                configured=expected.get('aggregate_fixture_timeouts',{}).get(test)
                assert ctest_seconds==int(ctest_seconds) and 0<ctest_seconds<=(configured or 300)
                if configured:assert ctest_seconds==configured
                # CTest owns its test timeout. Leave a bounded interval for its
                # termination/JUnit output; an equal outer deadline can discard
                # the very failure evidence the runner is required to retain.
                grace=expected['bounds']['ctest_reporting_grace_seconds'];assert grace==30
                command_seconds=int(ctest_seconds)+grace
                receipt=build/'qualification-junit'/(test+'.xml')
                if receipt.exists():retention.retire_file(receipt)
                code,_=run('test-'+test,[ctest,'--test-dir',build,'-C','Release','-R','^'+re.escape(test)+'$',
                    '--timeout',str(expected['bounds']['group_seconds']),
                    '--verbose','--output-on-failure','--output-junit',receipt],command_seconds,allow_failure=True)
                observed=junit_result(receipt,test,code)
                if observed['retain']:
                    archive.write(receipt,'junit/'+test+'.xml');retention.retire_file(receipt)
                passed=observed['passed']
                methods=None
                if test in expected.get('invocation_method_coverage',{}):
                    wanted=expected['invocation_method_coverage'][test]
                    methods=json.loads((build/wanted['summary']).read_bytes())
                    passed=passed and methods['passed'] is True and methods['partition']==wanted['partition'] and methods['methods']==wanted['methods'] and methods['tests_run']==len(wanted['methods']) and methods['skipped']==0
                result['tests'].append(dict(name=test,exit_code=code,passed=passed,execution_profile='ordinary' if ordinary else 'appcontainer',
                    ctest_timeout_seconds=ctest_seconds,controller_timeout_seconds=command_seconds,invocation_methods=methods,junit_receipt=observed))
            for path in sorted(build.iterdir()):
                if not path.is_file() or path.name in before:continue
                info=path.lstat()
                if not stat.S_ISREG(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400 or info.st_nlink!=1:
                    raise RuntimeError('Linked/non-file native observation; preserved')
                archive.write(path,'groups/'+test+'/'+path.name)
                if not path.name.endswith('-cases.json'):retention.retire_file(path)
            if not passed:
                result.setdefault('failed_native_groups',[]).append(test)
                if focused and len(expected['focus_groups'])==1:raise RuntimeError('Native group failed: '+test)
            if ordinary:
                _,raw=run('retire-temp-'+test,[sys.executable,'-B',ROOT/'retire-temp.py',instance.native_temp],60)
                retired=json_record(raw);assert retired['root_recreated_empty']
                result.setdefault('group_temp_retirements',[]).append(dict(group=test,**retired))
            active_group=None;active_before=set()

        def receipt_control():
            folder=g.fresh(instance.work/'receipt-control')
            definition=folder/'CTestTestfile.cmake';receipt=folder/'receipt.xml'
            definition.write_text('add_test(qualification.receipt "'+Path(sys.executable).as_posix()+'" "-c" "raise SystemExit(0)")\n',encoding='utf-8',newline='\n')
            archive.write(definition,'recipe/junit-receipt-control.cmake')
            code,_=run('junit-receipt-control',[ctest,'--test-dir',folder,'-C','Release','-R','^qualification[.]receipt$',
                '--timeout','10','--output-junit',receipt],30,allow_failure=True)
            observed=junit_result(receipt,'qualification.receipt',code)
            if observed['retain']:archive.write(receipt,'controls/junit-receipt.xml')
            result['junit_publication_control']=dict(observed,scope='One private Python exit0 case,not a native product group')
            if not observed['passed']:raise RuntimeError('JUnit publication control failed: '+observed['reason'])

        probe=work/'worker-identity-preflight.py'
        probe.write_text("import sys,json,pathlib,ctypes as C\nfrom ctypes import wintypes as T\nif sys.argv[3]=='appcontainer':\n    k=C.WinDLL('kernel32',use_last_error=True);a=C.WinDLL('advapi32',use_last_error=True)\n    k.GetCurrentProcess.restype=T.HANDLE\n    a.OpenProcessToken.argtypes=[T.HANDLE,T.DWORD,C.POINTER(T.HANDLE)]\n    a.GetTokenInformation.argtypes=[T.HANDLE,C.c_int,C.c_void_p,T.DWORD,C.POINTER(T.DWORD)]\n    a.ConvertSidToStringSidW.argtypes=[C.c_void_p,C.POINTER(T.LPWSTR)]\n    k.CloseHandle.argtypes=[T.HANDLE];k.LocalFree.argtypes=[C.c_void_p]\n    t=T.HANDLE();assert a.OpenProcessToken(k.GetCurrentProcess(),8,C.byref(t))\n    try:\n        size=T.DWORD();e=T.DWORD();c=T.DWORD()\n        assert a.GetTokenInformation(t,20,C.byref(e),4,C.byref(size))\n        assert a.GetTokenInformation(t,29,C.byref(c),4,C.byref(size))\n        a.GetTokenInformation(t,1,None,0,C.byref(size));assert 0<size.value<65536\n        data=C.create_string_buffer(size.value);assert a.GetTokenInformation(t,1,data,size,C.byref(size))\n        text=T.LPWSTR();assert a.ConvertSidToStringSidW(C.cast(data,C.POINTER(C.c_void_p))[0],C.byref(text))\n        try:r=dict(user_sid=text.value,elevated=e.value,appcontainer=c.value,administrator=bool(C.windll.shell32.IsUserAnAdmin()))\n        finally:k.LocalFree(C.cast(text,C.c_void_p))\n        assert r['appcontainer']==1\n    finally:k.CloseHandle(t)\nelse:\n    sys.path.insert(0,sys.argv[1]);import target;r=target.identity()\n    assert r['restricted'] and not r['appcontainer']\n    assert set(r['restricting_sids'])=={r['user_sid'],'S-1-5-12'}\nassert not r['elevated'] and not r['administrator']\ntry:pathlib.Path(sys.argv[2]).write_bytes(b'unexpected')\nexcept PermissionError:pass\nelse:raise AssertionError('source writable')\nprint(json.dumps(r))\n")
        _,raw=run('build-token-and-source-denial',[sys.executable,'-B',probe,ROOT,SOURCE/'forbidden-write','appcontainer'],30)
        result['build_token']=json_record(raw);assert result['build_token']['user_sid']==coordinator_sid
        if expected.get('pixel_origin_proof'):
            # A small test fixture only: no product/CMake build or native suite.
            null_grant=null_helper.Grant('build');null_grant.apply();null_grant.started()
            vc=Path('C:/BuildTools/VC/Tools/MSVC/14.44.35207')
            sdk=Path('C:/Program Files (x86)/Windows Kits/10');binary=vc/'bin/Hostx64/x64'
            env.update(PATH=str(binary)+os.pathsep+env.get('PATH',os.defpath),
                INCLUDE=os.pathsep.join(str(p) for p in [vc/'include',*[sdk/'Include/10.0.19041.0'/name for name in ('ucrt','shared','um')]]),
                LIB=os.pathsep.join(str(p) for p in [vc/'lib/x64',*[sdk/'Lib/10.0.19041.0'/name/'x64' for name in ('ucrt','um')]]))
            build.mkdir();render_source=SOURCE/'.aide/evidence/2026-10-18-ordinary-worker/pixel-render.c'
            render_dll=build/'pixel-render.dll'
            arguments=['/Bv','/nologo','/LD','/MT','/O2','/W4','/WX','/GS','/sdl','/guard:cf',
                '/DUNICODE','/D_UNICODE','/Fo'+str(build/'pixel-render.obj'),'/Fe'+str(render_dll),
                str(render_source),'user32.lib','gdi32.lib','/link','/DYNAMICBASE','/NXCOMPAT','/guard:cf',
                '/IMPLIB:'+str(build/'pixel-render.lib')]
            response=build/'pixel-render.rsp';response.write_text(subprocess.list2cmdline(arguments),encoding='utf-8')
            archive.write(response,'recipe/pixel-render.rsp')
            _,raw=run('pixel-fixture-compile',[binary/'cl.exe','@'+str(response)],120)
            assert b'19.44.35228' in raw and 0<render_dll.stat().st_size<=524288
            _,raw=run('pixel-fixture-imports',[binary/'dumpbin.exe','/headers','/imports',render_dll],30)
            result['pixel_render_fixture']=dict(source_sha256=retention.sha(render_source),
                compiler_sha256=retention.sha(binary/'cl.exe'),linker_sha256=retention.sha(binary/'link.exe'),
                dll_sha256=retention.sha(render_dll),dll_bytes=render_dll.stat().st_size,
                imports_observation_sha256=hashlib.sha256(raw).hexdigest(),
                scope='Test-only x64 UI-thread renderer;not a product component or capture admission')
            env.update(DISKED_PIXEL_RENDER_DLL=str(render_dll),DISKED_PIXEL_RENDER_SHA256=retention.sha(render_dll))
            null_grant.retire(quiescent=True);null_grant.close();null_grant=None
            stop();instance.close();instance=None;shared_read_access(False)
            native_work=g.fresh(work/'native-x64');instance=g.worker(native_work,private,namespace_compat=True);ordinary=True
            (native_work/'owner.json').write_text(json.dumps(dict(root=str(SOURCE))))
            fixture_broker=fixture_setup.Broker(native_work,instance.native_temp,instance.user_sid)
            grant=helper.Grant();grant.apply();grant.started()
            _,raw=run('pixel-origin-control',[sys.executable,'-B',ROOT/'pixel-window.py'],35)
            result['pixel_origin_control']=json_record(raw)
            assert result['pixel_origin_control']['passed'] and result['pixel_origin_preflight']['passed']
            result.update(status='pass',qualification='Known-pixel control only;actual product GUI and full suite remain unqualified')
            return
        if expected.get('controller_stop_proof'):
            null_grant=null_helper.Grant('build');null_grant.apply();null_grant.started()
            (ROOT/'stop-ready.json').write_text(json.dumps(dict(nonce=state['nonce']))+'\n',encoding='utf-8',newline='\n')
            run('owned-stop-proof-wait',[sys.executable,'-B','-c','import time; time.sleep(60)'],90)
            raise AssertionError('Controller did not interrupt the declared proof child')
        if not expected.get('null_proof_only'):
            schema_probe="import sys,json;sys.path.insert(0,sys.argv[1]);from specctl import Bundle;b=Bundle(sys.argv[2]);print(json.dumps(dict(schemas=len(b.schemas))))"
            _,raw=run('schema-tools-and-source-closure',[sys.executable,'-B','-c',schema_probe,SOURCE/'spec/tools',SOURCE/'spec'],30)
            result['schema_source_closure']=json_record(raw);assert result['schema_source_closure']['schemas']==95
        fixture_root=work/'symlink-fixture';fixture_root.mkdir()
        target,link=fixture_root/'source.img',fixture_root/'leaf.img';target.write_bytes(b'');os.symlink(target,link)
        assert link.is_symlink() and link.resolve()==target
        env['DISKED_TEST_SYMLINK_ROOT']=str(fixture_root)
        fixture_probe=work/'fixture-preflight.py'
        fixture_probe.write_text('''import json,pathlib,sys
sys.path.insert(0,sys.argv[1]);sys.path.insert(0,sys.argv[2])
from support.tempdir import managed_directory
from test_ntfs_file import size_fixture,record_sparse_fixture,prepared_symlink,file_digest,SPARSE_OBSERVATIONS,PREPARED_SYMLINK_OBSERVATIONS
with managed_directory(prefix='native-preflight-') as directory:
    source=pathlib.Path(directory)/'source.img'
    with source.open('wb') as stream:
        size_fixture(stream,5*1024*1024*1024+4096)
        stream.seek(5*1024*1024*1024);stream.write(b'owned high data')
        record_sparse_fixture(stream,5*1024*1024*1024+4096)
    with source.open('rb') as stream:
        assert stream.read(32)==bytes(32)
        stream.seek(5*1024*1024*1024);assert stream.read(15)==b'owned high data'
    source.unlink()
    for iteration in range(2):
        with source.open('wb') as stream:
            size_fixture(stream,40960000)
            stream.seek(4096);stream.write(b'original independent source '+bytes([iteration]))
            if not iteration:stream.seek(40959996);stream.write(b'tail')
        before=file_digest(source);target,link=prepared_symlink(source)
        assert link.is_symlink() and link.resolve()==target
        assert file_digest(source)==before==file_digest(target)
        assert PREPARED_SYMLINK_OBSERVATIONS[-1]['allocated_bytes']<=16777216
        assert PREPARED_SYMLINK_OBSERVATIONS[-1]['copied_nonzero_block_bytes']<=131072
assert not source.exists() and len(PREPARED_SYMLINK_OBSERVATIONS)==2
print(json.dumps(dict(status='pass',sparse=SPARSE_OBSERVATIONS,prepared=PREPARED_SYMLINK_OBSERVATIONS,source_removed=True)))
''')
        archive.write(fixture_probe,'recipe/fixture-preflight.py')
        _,raw=run('sparse-and-two-generation-symlink-preflight',[sys.executable,'-B',fixture_probe,SOURCE/'tests',SOURCE/'tests/images'],60)
        result['fixture_preflight']=json_record(raw);assert result['fixture_preflight']['status']=='pass'
        git=Path('C:/Program Files/Git/cmd/git.exe')
        code,raw=run('package-git-before-null',[git,'--version'],30,allow_failure=True)
        assert code==128 and b'/dev/null' in raw
        interrupted=subprocess.run([sys.executable,'-B',str(ROOT/'null-device.py'),'--build-apply-and-exit'],capture_output=True,timeout=15)
        assert interrupted.returncode==19
        null_grant=null_helper.Grant('build',recovery=True);null_grant.retire(quiescent=True)
        result['null_interruption_recovery']=null_grant.report;null_grant.close();null_grant=None
        null_grant=null_helper.Grant('build');null_grant.apply();null_grant.started()
        run('package-git-version',[git,'--version'],30)
        _,raw=run('package-git-revision',[git,'-C',SOURCE,'rev-parse','HEAD'],30)
        assert raw.decode().strip()==manifest['revision']
        _,raw=run('package-git-clean',[git,'-C',SOURCE,'status','--porcelain','--untracked-files=normal'],30);assert not raw
        if expected.get('null_proof_only'):
            if expected.get('powershell_proof'):
                shell=stage_powershell7() if expected.get('powershell7_proof') else Path(os.environ['WINDIR'])/'System32/WindowsPowerShell/v1.0/powershell.exe'
                command="[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);@{sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;clr=[Environment]::Version.ToString();version=$PSVersionTable.PSVersion.ToString()}|ConvertTo-Json -Compress"
                _,raw=run('package-powershell-clr-startup',[shell,'-NoLogo','-NoProfile','-NonInteractive','-Command',command],30)
                observed=json.loads(raw.decode('utf-8-sig'))
                assert observed['sid']==coordinator_sid and observed['clr'] and observed['version']
                result['package_powershell']=dict(executable_sha256=retention.sha(shell),observation=observed,
                    scope='Actual confined AppContainer startup only; ordinary restricted CLR remains unqualified')
            null_grant.retire(quiescent=True);result['null_build']=null_grant.report;null_grant.close();null_grant=None
            code,raw=run('package-git-after-null-removal',[git,'--version'],30,allow_failure=True)
            assert code==128 and b'/dev/null' in raw
            if expected.get('cleanup_proof') or expected.get('ui_proof'):
                instance.close();instance=None;shared_read_access(False)
                native_work=g.fresh(work/'native-x64');instance=g.worker(native_work,private,namespace_compat=True);ordinary=True
                (native_work/'owner.json').write_text(json.dumps(dict(root=str(SOURCE))))
                fixture_broker=fixture_setup.Broker(native_work,instance.native_temp,instance.user_sid)
                result['fixture_dacl_scope_controls']=fixture_broker.prove_refusals(SOURCE/'AGENTS.md')
                grant=helper.Grant();grant.apply();grant.started()
                if expected.get('ui_proof'):
                    env['DISKED_OWNED_PRINT_PROBE']=str(instance.native_temp/'owned-print-probe')
                    _,raw=run('ordinary-private-ui-diagnostic',[sys.executable,'-B',ROOT/'ui-probe.py'],30)
                    result['private_ui_diagnostic']=json_record(raw)
                    env.pop('DISKED_OWNED_PRINT_PROBE')
                    # Compare only owned control windows on an owned station.
                    # This does not grant READSCREEN on the shared WinSta0.
                    previous=instance
                    private_work=g.fresh(work/'owned-station-printing')
                    try:
                        instance=g.O.Worker(g.W,private_work,Path(os.environ['DISKED_WORK_ROOT']),
                            private['DISKED_TEST_ACTOR_NAME'],private['DISKED_TEST_ACTOR_PASS'],
                            private['DISKED_TEST_ACTOR_SID'],namespace_compat=True,interactive_ui=False)
                        _,raw=run('ordinary-owned-station-printing',[sys.executable,'-B',ROOT/'ui-probe.py','--printing-only'],30)
                        result['owned_station_printing']=dict(security=instance.ui_security,observation=json_record(raw))
                    finally:
                        if instance is not previous:instance.close()
                        instance=previous
                    _,raw=run('ordinary-owned-dacl-fixture-proof',[sys.executable,'-B',SOURCE/'tests/support/file_dacl.py','--fixture-proof'],30)
                    result['owned_dacl_fixture_proof']=json_record(raw);assert result['owned_dacl_fixture_proof']['passed']
                    code,_=run('ordinary-dacl-interruption-proof',[sys.executable,'-B',SOURCE/'tests/support/file_dacl.py','--fixture-interrupt-proof'],30,allow_failure=True)
                    assert code==19
                    restored=result['fixture_dacl_jobs'][-1]
                    assert restored['command']=='ordinary-dacl-interruption-proof' and restored['all_held_fixtures_restored']
                    assert sum(row.get('abandoned',False) for row in restored['audit'])==1
                    result['owned_dacl_interruption_recovered']=True
                    receipt_control()
                else:
                    _,raw=run('ordinary-cleanup-attribute-diagnostic',[sys.executable,'-B',ROOT/'cleanup-probe.py',instance.native_temp],30)
                    result['cleanup_attribute_diagnostic']=json_record(raw)
            result.update(status='pass',qualification='Confined PowerShell startup plus Null setup/recovery/real-Git/revocation; no product tests' if expected.get('powershell_proof') else 'Null-sink build-package setup/recovery/real-Git/revocation only; no CMake build or product tests')
            if expected.get('cleanup_proof'):result['qualification']='Owned attribute/deletion observations only; no product qualification'
            if expected.get('ui_proof'):result['qualification']='Private-desktop and console API observations only; no product or GUI qualification'
            return
        selected=expected.get('focus_groups',expected['groups'])
        if any(name in selected for name in expected.get('appcontainer_test_groups',[])):
            original_path=env.get('PATH',os.defpath)
            shell=stage_powershell7()
            command="[Console]::OutputEncoding=[Text.UTF8Encoding]::new($false);@{version=$PSVersionTable.PSVersion.ToString();clr=[Environment]::Version.ToString()}|ConvertTo-Json -Compress"
            _,raw=run('required-shell-tool-preflight',[shell,'-NoLogo','-NoProfile','-NonInteractive','-Command',command],30)
            result['powershell7_preflight']=json.loads(raw.decode('utf-8-sig'))
            retire_shell_tool()
        run('msbuild-version',['C:/BuildTools/MSBuild/Current/Bin/amd64/MSBuild.exe','-nologo','-version'],60)
        run('configure',[cmake,'--preset','windows-bootstrap','-S',SOURCE,'-B',build,
            '-DCMAKE_GENERATOR_INSTANCE=C:/BuildTools,version=17.14.37516.0','-DPython3_EXECUTABLE='+sys.executable],300)
        focused=bool(expected.get('focus_groups'))
        targets=['--target','bootstrap_registry',*expected['focus_targets']] if focused else []
        parallel=expected['bounds'].get('build_parallelism',1)
        assert type(parallel) is int and 1<=parallel<=2
        run('build',[cmake,'--build',build,'--config','Release','--parallel',str(parallel),*targets],1800)
        (build/'qualification-junit').mkdir()
        _,raw=run('registered',[ctest,'--test-dir',build,'-C','Release','--show-only=json-v1'])
        registered=json.loads(raw)['tests'];assert sorted(t['name'] for t in registered)==expected['groups']
        result['registered_native_groups']=len(registered)
        headers=sorted(p for folder in build.glob('*_headers.dir') for p in (folder/'Release').glob('*.obj'))
        if not focused:assert len(headers)==expected['standalone_headers']==68
        result['standalone_headers']=[dict(path=p.relative_to(work).as_posix(),sha256=retention.sha(p)) for p in headers]
        identity=json.loads((build/'generated/build-identity.json').read_bytes());result['build_identity']=identity
        dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe');result['executables']={}
        observed_executables=expected.get('focus_executables',expected['focus_targets']) if focused else expected['executables']
        assert observed_executables and (not focused or set(observed_executables)<=set(expected['focus_targets']))
        for name in observed_executables:
            path=build/'Release'/(name+'.exe');image=path.read_bytes();offset=struct.unpack_from('<I',image,60)[0]
            assert image[offset:offset+4]==b'PE\0\0' and struct.unpack_from('<H',image,offset+4)[0]==0x8664
            result['executables'][name]=dict(bytes=len(image),sha256=hashlib.sha256(image).hexdigest(),machine='0x8664')
            for mode in ('headers','imports','dependents'):
                _,raw=run(name+'-'+mode,[dumpbin,'/nologo','/'+mode,path],60)
                if mode=='headers':assert all(text in raw for text in (b'Dynamic base',b'NX compatible',b'Control Flow Guard'))
                if mode=='dependents':assert not re.search(rb'(?:MSVCP|VCRUNTIME|UCRTBASE|API-MS-WIN-CRT)[^\s]*\.DLL',raw.upper())
        result['native_build_passed']=True
        selected=expected['focus_groups'] if focused else expected['groups']
        package_tests=expected.get('appcontainer_test_groups',[])
        assert len(set(package_tests))==len(package_tests) and set(package_tests)<=set(expected['groups'])
        package_selection=[test for test in package_tests if test in selected]
        if focused and all(test in package_tests for test in selected):
            release_build_binaries();stage_powershell7()
            for test in selected:test_group(test)
            assert len(result['tests'])==len(selected) and all(test['passed'] for test in result['tests'])
            result.update(status='pass',qualification='Focused invocation partitions only; full current native inventory remains required')
            return
        null_grant.retire(quiescent=True);result['null_build']=null_grant.report;null_grant.close();null_grant=None
        instance.close();instance=None;shared_read_access(False)
        artifact_handoff(build)
        native_work=g.fresh(work/'native-x64');instance=g.worker(native_work,private,namespace_compat=True);ordinary=True
        (native_work/'owner.json').write_text(json.dumps(dict(root=str(SOURCE))))
        fixture_broker=fixture_setup.Broker(native_work,instance.native_temp,instance.user_sid)
        result['fixture_dacl_scope_controls']=fixture_broker.prove_refusals(SOURCE/'AGENTS.md')
        directory_acl(compile_work,shared_acl)
        grant=helper.Grant();grant.apply();grant.started()
        if expected.get('ui_fixture_preflight'):
            _,raw=run('ordinary-ui-fixture-preflight',[sys.executable,'-B',ROOT/'ui-probe.py'],30)
            result['private_ui_diagnostic']=json_record(raw)
            console=result['private_ui_diagnostic']['console_child']
            assert console['exit_code']==0 and not console['stderr']
            observed=json.loads(console['stdout'])
            assert observed['configure_passed'] and all(row['success'] for row in observed['configure_steps'])
            geometry=observed['configured_geometry'];largest=observed['largest_viewport']
            assert geometry['buffer']==[240,1000]
            assert geometry['viewport']==[0,0,min(240,largest[0])-1,min(25,largest[1])-1]
            assert all(row['loaded'] for row in observed['libraries'])
        code,raw=run('ordinary-git-before-null',[git,'--version'],30,allow_failure=True)
        if code:
            assert code==128 and b'/dev/null' in raw
            null_grant=null_helper.Grant('user');null_grant.apply();null_grant.started()
            run('ordinary-git-with-null',[git,'--version'],30)
        _,raw=run('test-token-and-source-denial',[sys.executable,'-B',probe,ROOT,SOURCE/'forbidden-write','ordinary'],30)
        result['actual_token']=json_record(raw);assert result['actual_token']['user_sid']==data['sid']
        assert result['actual_token']['integrity_sid']=='S-1-16-8192'
        _,raw=run('ordinary-owned-dacl-fixture-proof',[sys.executable,'-B',SOURCE/'tests/support/file_dacl.py','--fixture-proof'],30)
        result['owned_dacl_fixture_proof']=json_record(raw);assert result['owned_dacl_fixture_proof']['passed']
        code,_=run('ordinary-dacl-interruption-proof',[sys.executable,'-B',SOURCE/'tests/support/file_dacl.py','--fixture-interrupt-proof'],30,allow_failure=True)
        assert code==19
        restored=result['fixture_dacl_jobs'][-1]
        assert restored['command']=='ordinary-dacl-interruption-proof' and restored['all_held_fixtures_restored']
        assert sum(row.get('abandoned',False) for row in restored['audit'])==1
        result['owned_dacl_interruption_recovered']=True
        receipt_control()
        _,raw=run('native-token-identity',[build/'Release/fat_tree_extraction_worker_probe.exe','--token-identity'],30)
        result['native_token_identity']=json_record(raw)
        assert result['native_token_identity']['integrity_sid']=='S-1-16-8192'
        assert result['native_token_identity']['user_sid']==result['actual_token']['user_sid']
        assert set(result['native_token_identity']['restricting_sids'])==set(result['actual_token']['restricting_sids'])
        assert result['native_token_identity']['appcontainer']=='0' and result['native_token_identity']['elevated']=='0'
        if focused:
            a=C.WinDLL('advapi32',use_last_error=True);k=C.WinDLL('kernel32',use_last_error=True)
            read=g.W.bind(a,'GetNamedSecurityInfoW',T.DWORD,T.LPWSTR,C.c_int,T.DWORD,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p)
            convert=g.W.bind(a,'ConvertSecurityDescriptorToStringSecurityDescriptorW',T.BOOL,C.c_void_p,T.DWORD,T.DWORD,C.c_void_p,C.c_void_p)
            free=g.W.bind(k,'LocalFree',C.c_void_p,C.c_void_p)
            result['artifact_labels']=[]
            for path in [Path(sys.executable),*(build/'Release'/(name+'.exe') for name in expected['focus_targets'])]:
                sd=C.c_void_p();label=T.LPWSTR()
                error=read(str(path),1,0x10,None,None,None,None,C.byref(sd))
                if error:raise C.WinError(error)
                try:
                    g.W.require(convert(sd,1,0x10,C.byref(label),None))
                    result['artifact_labels'].append(dict(path=str(path),label=label.value,sha256=retention.sha(path)))
                finally:
                    if label:free(C.cast(label,C.c_void_p))
                    free(sd)
            parent_probe=work/'parent-read-diagnostic.py'
            parent_probe.write_text('''import ctypes as C,json,pathlib,tempfile,shutil
from ctypes import wintypes as T
k=C.WinDLL('kernel32',use_last_error=True);a=C.WinDLL('advapi32',use_last_error=True)
k.CreateFileW.argtypes=[T.LPCWSTR,T.DWORD,T.DWORD,C.c_void_p,T.DWORD,T.DWORD,T.HANDLE];k.CreateFileW.restype=T.HANDLE
k.CloseHandle.argtypes=[T.HANDLE];k.LocalFree.argtypes=[C.c_void_p]
a.GetNamedSecurityInfoW.argtypes=[T.LPWSTR,C.c_int,T.DWORD,C.c_void_p,C.c_void_p,C.c_void_p,C.c_void_p,C.POINTER(C.c_void_p)];a.GetNamedSecurityInfoW.restype=T.DWORD
a.ConvertSecurityDescriptorToStringSecurityDescriptorW.argtypes=[C.c_void_p,T.DWORD,T.DWORD,C.POINTER(T.LPWSTR),C.c_void_p]
sample=pathlib.Path(tempfile.mkdtemp(prefix='owned-parent-read-'));rows=[]
try:
    for path in reversed([sample,*sample.parents]):
        row=dict(path=str(path),opens=[])
        for access,share in ((0x80000000,1),(0x80000000,7),(0x20080,7)):
            C.set_last_error(0);h=k.CreateFileW(str(path),access,share,None,3,0x02200000,None);error=C.get_last_error()
            opened=h!=C.c_void_p(-1).value;row['opens'].append(dict(access=hex(access),share=share,opened=opened,error=0 if opened else error))
            if opened:k.CloseHandle(h)
        sd=C.c_void_p();error=a.GetNamedSecurityInfoW(str(path),1,7,None,None,None,None,C.byref(sd));row['security_error']=error
        if error==0:
            text=T.LPWSTR()
            try:
                assert a.ConvertSecurityDescriptorToStringSecurityDescriptorW(sd,1,7,C.byref(text),None)
                row['sddl']=text.value
            finally:
                if text:k.LocalFree(C.cast(text,C.c_void_p))
                k.LocalFree(sd)
        rows.append(row)
finally:shutil.rmtree(sample)
print(json.dumps(dict(scope='Read-only parent-open observations,not qualification',rows=rows)))
''')
            archive.write(parent_probe,'recipe/parent-read-diagnostic.py')
            _,raw=run('ordinary-parent-read-diagnostic',[sys.executable,'-B',parent_probe],30)
            result['parent_read_diagnostic']=json_record(raw)
        selected=[name for name in selected if name not in package_tests]
        assert set(selected)<=set(expected['groups'])
        if not focused:
            build_checks=['build.boundaries','build.boundary_checker']
            selected=build_checks+[name for name in selected if name not in build_checks]
        for test in selected:
            # No group consumes another group's temporary image tree. Retire it
            # only after its complete process tree exits and its observations are
            # archived. This also applies to mkdtemp callers without finalizers.
            test_group(test)
            if not focused and test=='build.boundary_checker':
                # The build/header checks have consumed these files. Runtime
                # tests execute the linked binaries and read retained CMake
                # metadata; reproducible compiler objects are disposable now.
                removed_count=removed_bytes=0
                for path in build.rglob('*.obj'):
                    for parent in [path.parent,*path.parent.parents]:
                        g.W.plain_directory(parent)
                        if parent==build:break
                    info=path.lstat()
                    assert path.resolve().is_relative_to(build.resolve()) and stat.S_ISREG(info.st_mode) and info.st_nlink==1 and not getattr(info,'st_file_attributes',0)&0x400
                    retention.retire_file(path);removed_count+=1;removed_bytes+=info.st_size
                result['compiler_objects_retired_before_runtime_tests']=dict(count=removed_count,logical_bytes=removed_bytes)
        if expected.get('diagnose_fat_history'):
            assert focused and not result['tests'] and len(result['diagnostics'])==1 and result['diagnostics'][0]['passed']
            result.update(status='pass',qualification='Elapsed-time diagnosis only; original300-second group remains unqualified')
            return
        if package_selection:
            # Retire the ordinary worker and all its jobs before reusing this
            # campaign's package identity for the two shell/console groups.
            # Remove reproducible binaries first, so the temporary shell and
            # linked compiler output never compete for the fixed512MiB volume.
            stop();release_build_binaries()
            if null_grant:
                null_grant.retire(quiescent=True);result['null_user']=null_grant.report;null_grant.close();null_grant=None
            instance.close();instance=None
            grant.retire(quiescent=True);result['crypto_device']=grant.report;grant.close();grant=None
            ordinary=False
            package_work=g.fresh(work/'invoke-x64')
            instance=g.W.Worker(package_work,control=Path(os.environ['DISKED_WORK_ROOT']),private_station=True,profile_name=state['profile_names'][0])
            assert instance.restricting_sid==pkg_sid and instance.user_sid==coordinator_sid
            (package_work/'owner.json').write_text(json.dumps(dict(root=str(SOURCE))))
            shared_read_access(True)
            result['initial_null_build']=result['null_build']
            null_grant=null_helper.Grant('build');null_grant.apply();null_grant.started()
            _,raw=run('invocation-token-and-source-denial',[sys.executable,'-B',probe,ROOT,SOURCE/'forbidden-write','appcontainer'],30)
            result['invocation_token']=json_record(raw)
            stage_powershell7()
            for test in package_selection:test_group(test)
        # Assertion failures do not discard unrelated evidence from this exact
        # build. Each group is a separate retired job. Infrastructure, resource
        # or timeout failures still abort immediately in run(). Any failed group
        # keeps the whole qualification failed; no skipped/reclassified pass.
        result['attempted_native_groups']=len(result['tests'])
        assert sorted(t['name'] for t in result['tests'])==sorted(expected['focus_groups'] if focused else expected['groups'])
        result['full_x64_product_suite_run']=not focused and len(result['tests'])==len(expected['groups'])==180 and all(t['passed'] for t in result['tests'])
        if result.get('failed_native_groups'):raise RuntimeError('Native groups failed: '+','.join(result['failed_native_groups']))
        assert focused or result['full_x64_product_suite_run']
        result.update(status='pass',qualification='Focused native regression only; full current native inventory remains required' if focused else 'Native groups/build/header/import run only; final W105 expectation/tooling/portability review still required')
    except BaseException:
        result.update(status='fail',error=traceback.format_exc()[-8192:])
        if archive and 'build' in locals() and build.exists():
            if 'active_group' in locals() and active_group:
                try:
                    # run() has retired the whole job before raising. Keep
                    # closed raw requests/replies even when no JUnit exists.
                    for path in sorted(build.iterdir()):
                        if not path.is_file() or path.name in active_before:continue
                        info=path.lstat();member='groups/'+active_group+'/'+path.name
                        if member in archive.entries:continue
                        if stat.S_ISREG(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400 and info.st_nlink==1 and info.st_size<=16*1024*1024:
                            archive.write(path,member)
                except BaseException:
                    result['failed_group_retention_error']=traceback.format_exc()[-4096:]
            for path in build.rglob('*'):
                if path.name not in ('CMakeConfigureLog.yaml','CMakeError.log','CMakeOutput.log','VCTargetsPath.vcxproj'):continue
                info=path.lstat()
                if stat.S_ISREG(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400 and info.st_nlink==1 and info.st_size<=1048576:
                    archive.write(path,'diagnostics/'+path.relative_to(build).as_posix())
        raise
    finally:
        try:
            stop()
            if ordinary and instance and 'native_work' in locals() and (native_work/'temp').exists():
                try:
                    _,raw=run('final-test-temp-cleanup',[sys.executable,'-B',ROOT/'retire-temp.py',instance.native_temp],60)
                    result['final_group_temp_cleanup']=json_record(raw)
                except BaseException:
                    result.update(status='fail',temp_cleanup_error=traceback.format_exc()[-8192:])
            if null_grant:
                null_grant.retire(quiescent=quiescent);result['null_'+null_grant.role]=null_grant.report;null_grant.close()
            if fixture_broker:
                try:
                    fixture_broker.close(quiescent=quiescent);result['fixture_dacl_coordinator_retired']=True
                except BaseException:
                    result.update(status='fail',fixture_dacl_cleanup_error=traceback.format_exc()[-8192:])
            if instance:instance.close()
            if directory_grant:shared_read_access(False)
            if grant:grant.retire(quiescent=quiescent);result['crypto_device']=grant.report;grant.close()
            result.update(all_owned_processes_retired=True,crypto_device_retired=True,null_device_retired=True)
            if source_prepared:
                retired=subprocess.run([sys.executable,'-B',str(ROOT/'guest-source.py'),'retire'],capture_output=True,timeout=180)
                if retired.returncode:raise RuntimeError('Source retirement: '+retired.stderr[-4096:].decode(errors='replace'))
                result['source_retired']=json.loads((ROOT/'source-retired.json').read_bytes())
            if archive:
                entries=json.dumps(archive.entries,sort_keys=True,separators=(',',':')).encode()
                if len(entries)>4*1024*1024 or len(archive.entries)>20000:raise RuntimeError('Evidence entry inventory bound')
                archive.writestr('entry-manifest.json',entries)
                result['entry_manifest_sha256']=hashlib.sha256(entries).hexdigest()
                archive.close_verify()
                assert archive.path.stat().st_size<=32*1024*1024
                shutil.copyfile(archive.path,ROOT/'retained.tar.xz')
                result.update(archive_sha256=retention.sha(ROOT/'retained.tar.xz'),archive_bytes=(ROOT/'retained.tar.xz').stat().st_size,archive_entries=len(archive.entries))
        except BaseException:
            result.update(status='fail',cleanup_error=traceback.format_exc()[-8192:]);raise
        finally:(ROOT/'proof-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
