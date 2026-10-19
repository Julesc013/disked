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

ROOT=Path('C:/ProgramData/DiskEd/qualification')
SOURCE=ROOT/'source'


def coordinate(g):
    helper=g.load('full_crypto',ROOT/'crypto-device.py')
    null_helper=g.load('full_null',ROOT/'null-device.py')
    retention=g.load('full_retention',ROOT/'build-driver.py')
    source_setup=g.load('full_source',ROOT/'guest-source.py')
    expected=json.loads((ROOT/'expected.json').read_bytes())['native_x64']
    manifest=json.loads((ROOT/'source.json').read_bytes())
    result=dict(status='running',source_revision=manifest['revision'],full_x64_product_suite_run=False,
                all_owned_processes_retired=False,crypto_device_retired=False,commands=[],tests=[],owner_accepted=False)
    grant,instance,archive,job,child,null_grant=None,None,None,None,None,None
    source_prepared=False;quiescent=True
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
        for key in ('CL','_CL_','LINK','_LINK_','CFLAGS','CXXFLAGS','LDFLAGS'):env.pop(key,None)
        cmake=Path('C:/Program Files/CMake/bin/cmake.exe');ctest=cmake.with_name('ctest.exe')
        active_stem=None

        def budget():
            if time.monotonic()-campaign_started>7200:raise TimeoutError('Guest campaign overall deadline')
            g.S.check(ROOT)
            allocated=g.S.tree_bytes(work,allocated=True,file_limit=20000,allow_links=True)
            result['peak_scratch_allocated_bytes']=max(result.get('peak_scratch_allocated_bytes',0),allocated)
            combined=g.S.tree_bytes(ROOT,allocated=True,file_limit=20000,allow_links=False)
            combined+=g.S.tree_bytes(Path(os.environ['DISKED_WORK_ROOT']),allocated=True,file_limit=20000,allow_links=False)
            if combined>1073741824:raise RuntimeError('Aggregate disposable limit exceeded')
            if archive.path.stat().st_size>32*1024*1024:raise RuntimeError('Retained observations exceed32MiB')

        def drain(final=False):
            if active_stem in ('ntfs-name-order-file-cases','ntfs-name-order-worker-cases'):
                retention.drain_completed_outputs(archive,build,active_stem,final=final)

        def run(label,command,timeout=300,allow_failure=False):
            nonlocal job,child,quiescent
            job=g.S.WindowsJob();quiescent=False;started=time.monotonic();saved=False
            try:
                child=instance.launch(list(map(str,command)),env,job,variant='basic-stdio') if ordinary else instance.launch(list(map(str,command)),env,job)
                process_id=child.pid
                log_path=instance.log_path if ordinary else instance.work/'worker.log'
                until=started+timeout
                while child.poll() is None:
                    drain();budget()
                    if log_path.stat().st_size>524288:raise RuntimeError('Bounded native command log exceeded')
                    if time.monotonic()>until:raise TimeoutError(label+' deadline')
                    time.sleep(.2)
                code=child.wait();stop();drain(final=True)
                raw=log_path.read_bytes();assert len(raw)<=524288
                archive.writestr('commands/'+label+'.log',raw);saved=True
                result['commands'].append(dict(label=label,pid=process_id,execution_profile='ordinary' if ordinary else 'appcontainer-build',arguments=list(map(str,command)),exit_code=code,
                    seconds=time.monotonic()-started,sha256=hashlib.sha256(raw).hexdigest(),tail=raw[-4096:].decode(errors='replace')))
                if code and not allow_failure:raise RuntimeError(label+' failed: '+raw[-2048:].decode(errors='replace'))
                return code,raw
            finally:
                stop()
                if 'log_path' in locals() and log_path.exists():
                    if not saved:archive.writestr('commands/'+label+'-incomplete.log',log_path.read_bytes()[:524288])
                    retention.retire_file(log_path)

        probe=work/'worker-identity-preflight.py'
        probe.write_text("import sys,json,pathlib,ctypes as C\nfrom ctypes import wintypes as T\nif sys.argv[3]=='appcontainer':\n    k=C.WinDLL('kernel32',use_last_error=True);a=C.WinDLL('advapi32',use_last_error=True)\n    k.GetCurrentProcess.restype=T.HANDLE\n    a.OpenProcessToken.argtypes=[T.HANDLE,T.DWORD,C.POINTER(T.HANDLE)]\n    a.GetTokenInformation.argtypes=[T.HANDLE,C.c_int,C.c_void_p,T.DWORD,C.POINTER(T.DWORD)]\n    a.ConvertSidToStringSidW.argtypes=[C.c_void_p,C.POINTER(T.LPWSTR)]\n    k.CloseHandle.argtypes=[T.HANDLE];k.LocalFree.argtypes=[C.c_void_p]\n    t=T.HANDLE();assert a.OpenProcessToken(k.GetCurrentProcess(),8,C.byref(t))\n    try:\n        size=T.DWORD();e=T.DWORD();c=T.DWORD()\n        assert a.GetTokenInformation(t,20,C.byref(e),4,C.byref(size))\n        assert a.GetTokenInformation(t,29,C.byref(c),4,C.byref(size))\n        a.GetTokenInformation(t,1,None,0,C.byref(size));assert 0<size.value<65536\n        data=C.create_string_buffer(size.value);assert a.GetTokenInformation(t,1,data,size,C.byref(size))\n        text=T.LPWSTR();assert a.ConvertSidToStringSidW(C.cast(data,C.POINTER(C.c_void_p))[0],C.byref(text))\n        try:r=dict(user_sid=text.value,elevated=e.value,appcontainer=c.value,administrator=bool(C.windll.shell32.IsUserAnAdmin()))\n        finally:k.LocalFree(C.cast(text,C.c_void_p))\n        assert r['appcontainer']==1\n    finally:k.CloseHandle(t)\nelse:\n    sys.path.insert(0,sys.argv[1]);import target;r=target.identity()\n    assert r['restricted'] and not r['appcontainer']\n    assert set(r['restricting_sids'])=={r['user_sid'],'S-1-5-12'}\nassert not r['elevated'] and not r['administrator']\ntry:pathlib.Path(sys.argv[2]).write_bytes(b'unexpected')\nexcept PermissionError:pass\nelse:raise AssertionError('source writable')\nprint(json.dumps(r))\n")
        _,raw=run('build-token-and-source-denial',[sys.executable,'-B',probe,ROOT,SOURCE/'forbidden-write','appcontainer'],30)
        result['build_token']=json_record(raw);assert result['build_token']['user_sid']==coordinator_sid
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
            null_grant.retire(quiescent=True);result['null_build']=null_grant.report;null_grant.close();null_grant=None
            code,raw=run('package-git-after-null-removal',[git,'--version'],30,allow_failure=True)
            assert code==128 and b'/dev/null' in raw
            result.update(status='pass',qualification='Null-sink build-package setup/recovery/real-Git/revocation only; no CMake build or product tests')
            return
        run('msbuild-version',['C:/BuildTools/MSBuild/Current/Bin/amd64/MSBuild.exe','-nologo','-version'],60)
        run('configure',[cmake,'--preset','windows-bootstrap','-S',SOURCE,'-B',build,
            '-DCMAKE_GENERATOR_INSTANCE=C:/BuildTools,version=17.14.37516.0','-DPython3_EXECUTABLE='+sys.executable],300)
        focused=bool(expected.get('focus_groups'))
        targets=['--target','bootstrap_registry',*expected['focus_targets']] if focused else []
        run('build',[cmake,'--build',build,'--config','Release','--parallel','1',*targets],1800)
        _,raw=run('registered',[ctest,'--test-dir',build,'-C','Release','--show-only=json-v1'])
        registered=json.loads(raw)['tests'];assert sorted(t['name'] for t in registered)==expected['groups']
        result['registered_native_groups']=len(registered)
        headers=sorted(p for folder in build.glob('*_headers.dir') for p in (folder/'Release').glob('*.obj'))
        if not focused:assert len(headers)==expected['standalone_headers']==68
        result['standalone_headers']=[dict(path=p.relative_to(work).as_posix(),sha256=retention.sha(p)) for p in headers]
        identity=json.loads((build/'generated/build-identity.json').read_bytes());result['build_identity']=identity
        dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe');result['executables']={}
        for name in expected['focus_targets'] if focused else expected['executables']:
            path=build/'Release'/(name+'.exe');image=path.read_bytes();offset=struct.unpack_from('<I',image,60)[0]
            assert image[offset:offset+4]==b'PE\0\0' and struct.unpack_from('<H',image,offset+4)[0]==0x8664
            result['executables'][name]=dict(bytes=len(image),sha256=hashlib.sha256(image).hexdigest(),machine='0x8664')
            for mode in ('headers','imports','dependents'):
                _,raw=run(name+'-'+mode,[dumpbin,'/nologo','/'+mode,path],60)
                if mode=='headers':assert all(text in raw for text in (b'Dynamic base',b'NX compatible',b'Control Flow Guard'))
                if mode=='dependents':assert not re.search(rb'(?:MSVCP|VCRUNTIME|UCRTBASE|API-MS-WIN-CRT)[^\s]*\.DLL',raw.upper())
        result['native_build_passed']=True
        null_grant.retire(quiescent=True);result['null_build']=null_grant.report;null_grant.close();null_grant=None
        instance.close();instance=None;shared_read_access(False)
        artifact_handoff(build)
        native_work=g.fresh(work/'native-x64');instance=g.worker(native_work,private,namespace_compat=True);ordinary=True
        (native_work/'owner.json').write_text(json.dumps(dict(root=str(SOURCE))))
        directory_acl(compile_work,shared_acl)
        grant=helper.Grant();grant.apply();grant.started()
        code,raw=run('ordinary-git-before-null',[git,'--version'],30,allow_failure=True)
        if code:
            assert code==128 and b'/dev/null' in raw
            null_grant=null_helper.Grant('user');null_grant.apply();null_grant.started()
            run('ordinary-git-with-null',[git,'--version'],30)
        _,raw=run('test-token-and-source-denial',[sys.executable,'-B',probe,ROOT,SOURCE/'forbidden-write','ordinary'],30)
        result['actual_token']=json_record(raw);assert result['actual_token']['user_sid']==data['sid']
        if focused:
            _,raw=run('native-token-identity',[build/'Release/fat_tree_extraction_worker_probe.exe','--token-identity'],30)
            result['native_token_identity']=json_record(raw)
            assert result['native_token_identity']['integrity_sid']=='S-1-16-8192'
            assert result['native_token_identity']['user_sid']==result['actual_token']['user_sid']
            assert set(result['native_token_identity']['restricting_sids'])==set(result['actual_token']['restricting_sids'])
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
        selected=expected['focus_groups'] if focused else expected['groups']
        assert set(selected)<=set(expected['groups'])
        for test in selected:
            stem='ntfs-'+test.removeprefix('image.ntfs_').replace('_','-')+'-cases'
            active_stem=stem
            before={p.name for p in build.iterdir() if p.is_file()}
            code,_=run('test-'+test,[ctest,'--test-dir',build,'-C','Release','-R','^'+re.escape(test)+'$',
                '--output-on-failure','--output-junit',work/'test.xml'],300,allow_failure=True)
            archive.write(work/'test.xml','junit/'+test+'.xml')
            cases=list(ET.parse(work/'test.xml').getroot().iter('testcase'))
            passed=code==0 and len(cases)==1 and cases[0].get('name')==test and not any(c.tag in ('failure','error','skipped') for c in cases[0])
            result['tests'].append(dict(name=test,exit_code=code,passed=passed))
            for path in sorted(build.iterdir()):
                if not path.is_file() or path.name in before:continue
                info=path.lstat()
                if not stat.S_ISREG(info.st_mode) or getattr(info,'st_file_attributes',0)&0x400 or info.st_nlink!=1:
                    raise RuntimeError('Linked/non-file native observation; preserved')
                archive.write(path,'groups/'+test+'/'+path.name)
                if not path.name.endswith('-cases.json'):retention.retire_file(path)
            if not passed:raise RuntimeError('Native group failed: '+test)
        result['full_x64_product_suite_run']=not focused and len(result['tests'])==178 and all(t['passed'] for t in result['tests'])
        assert focused or result['full_x64_product_suite_run']
        result.update(status='pass',qualification='Focused native regression only; full178 remains required' if focused else 'Native groups/build/header/import run only; final W105 expectation/tooling/portability review still required')
    except BaseException:
        result.update(status='fail',error=traceback.format_exc()[-8192:])
        if archive and 'build' in locals() and build.exists():
            for path in build.rglob('*'):
                if path.name not in ('CMakeConfigureLog.yaml','CMakeError.log','CMakeOutput.log','VCTargetsPath.vcxproj'):continue
                info=path.lstat()
                if stat.S_ISREG(info.st_mode) and not getattr(info,'st_file_attributes',0)&0x400 and info.st_nlink==1 and info.st_size<=1048576:
                    archive.write(path,'diagnostics/'+path.relative_to(build).as_posix())
        raise
    finally:
        try:
            stop()
            if null_grant:
                null_grant.retire(quiescent=quiescent);result['null_'+null_grant.role]=null_grant.report;null_grant.close()
            if instance:instance.close()
            if directory_grant:shared_read_access(False)
            if grant:grant.retire(quiescent=quiescent);result['crypto_device']=grant.report;grant.close()
            result.update(all_owned_processes_retired=True,crypto_device_retired=True,null_device_retired=True)
            if archive:
                entries=json.dumps(archive.entries,sort_keys=True,separators=(',',':')).encode()
                if len(entries)>4*1024*1024 or len(archive.entries)>20000:raise RuntimeError('Evidence entry inventory bound')
                archive.writestr('entry-manifest.json',entries)
                result['entry_manifest_sha256']=hashlib.sha256(entries).hexdigest()
                archive.close_verify()
                assert archive.path.stat().st_size<=32*1024*1024
                shutil.copyfile(archive.path,ROOT/'retained.tar.xz')
                result.update(archive_sha256=retention.sha(ROOT/'retained.tar.xz'),archive_bytes=(ROOT/'retained.tar.xz').stat().st_size,archive_entries=len(archive.entries))
            if source_prepared:
                retired=subprocess.run([sys.executable,'-B',str(ROOT/'guest-source.py'),'retire'],capture_output=True,timeout=180)
                if retired.returncode:raise RuntimeError('Source retirement: '+retired.stderr[-4096:].decode(errors='replace'))
                result['source_retired']=json.loads((ROOT/'source-retired.json').read_bytes())
        except BaseException:
            result.update(status='fail',cleanup_error=traceback.format_exc()[-8192:]);raise
        finally:(ROOT/'proof-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
