"""Current-source x64 qualification in the independently proven ordinary guest."""
import ctypes as C
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
    retention=g.load('full_retention',ROOT/'build-driver.py')
    source_setup=g.load('full_source',ROOT/'guest-source.py')
    expected=json.loads((ROOT/'expected.json').read_bytes())['native_x64']
    manifest=json.loads((ROOT/'source.json').read_bytes())
    result=dict(status='running',source_revision=manifest['revision'],full_x64_product_suite_run=False,
                all_owned_processes_retired=False,crypto_device_retired=False,commands=[],tests=[],owner_accepted=False)
    grant,instance,archive,job,child=None,None,None,None,None
    source_prepared=False;quiescent=True
    campaign_started=time.monotonic()

    def stop():
        nonlocal job,child,quiescent
        if job:result.setdefault('job_retirements',[]).append(g.retire_job(job));job=None
        if child:child.wait(timeout=10);child.close();child=None
        quiescent=True

    try:
        data=g.actor();private={k:os.environ.pop(k) for k in list(os.environ) if k.startswith('DISKED_TEST_ACTOR_')}
        state=json.loads((ROOT/'scratch/state.json').read_bytes());assert state['size_mib']==512
        prepared=subprocess.run([sys.executable,'-B',str(ROOT/'guest-source.py'),'prepare'],capture_output=True,timeout=180)
        if prepared.returncode:raise RuntimeError('Source preparation: '+prepared.stderr[-4096:].decode(errors='replace'))
        source_prepared=True
        result['source_prepared']=json.loads((ROOT/'source-prepared.json').read_bytes())
        grant=helper.Grant();grant.apply();grant.started()
        work=g.fresh(g.W.plain_directory(state['work'])/'native-x64');instance=g.worker(work,private,namespace_compat=True)
        # The same freshly owned output now serves the materialized source. Its
        # source-bound marker is required by the existing managed fixture helper.
        (work/'owner.json').write_text(json.dumps(dict(root=str(SOURCE))))
        build=work/'build';archive=retention.Observations(work/'observations.tar.xz')
        env=dict(os.environ,DISKED_WORK_ROOT=str(work),GIT_OPTIONAL_LOCKS='0',GIT_TERMINAL_PROMPT='0',
                 GIT_CONFIG_COUNT='1',GIT_CONFIG_KEY_0='safe.directory',GIT_CONFIG_VALUE_0=str(SOURCE),
                 MSBUILDDISABLENODEREUSE='1',CMAKE_BUILD_PARALLEL_LEVEL='1',DISKED_TEST_OTHER_VOLUME_ROOT='C:\\')
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
                child=instance.launch(list(map(str,command)),env,job,variant='basic-stdio')
                until=started+timeout
                while child.poll() is None:
                    drain();budget()
                    if instance.log_path.stat().st_size>524288:raise RuntimeError('Bounded native command log exceeded')
                    if time.monotonic()>until:raise TimeoutError(label+' deadline')
                    time.sleep(.2)
                code=child.wait();stop();drain(final=True)
                raw=instance.log_path.read_bytes();assert len(raw)<=524288
                archive.writestr('commands/'+label+'.log',raw);saved=True
                result['commands'].append(dict(label=label,arguments=list(map(str,command)),exit_code=code,
                    seconds=time.monotonic()-started,sha256=hashlib.sha256(raw).hexdigest(),tail=raw[-4096:].decode(errors='replace')))
                if code and not allow_failure:raise RuntimeError(label+' failed: '+raw[-2048:].decode(errors='replace'))
                return code,raw
            finally:
                stop()
                if getattr(instance,'log_path',None) and instance.log_path.exists():
                    if not saved:archive.writestr('commands/'+label+'-incomplete.log',instance.log_path.read_bytes()[:524288])
                    retention.retire_file(instance.log_path)

        probe=work/'worker-identity-preflight.py'
        probe.write_text("import sys,json,pathlib\nsys.path.insert(0,sys.argv[1])\nimport target\nr=target.identity()\nassert r['restricted'] and not any(r[k] for k in ('elevated','administrator','appcontainer'))\nassert set(r['restricting_sids'])=={r['user_sid'],'S-1-5-12'}\ntry:pathlib.Path(sys.argv[2]).write_bytes(b'unexpected')\nexcept PermissionError:pass\nelse:raise AssertionError('source writable')\nprint(json.dumps(r))\n")
        _,raw=run('actual-token-and-source-denial',[sys.executable,'-B',probe,ROOT,SOURCE/'forbidden-write'],30)
        result['actual_token']=json.loads(raw);assert result['actual_token']['user_sid']==data['sid']
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
        result['fixture_preflight']=json.loads(raw);assert result['fixture_preflight']['status']=='pass'
        run('configure',[cmake,'--preset','windows-bootstrap','-S',SOURCE,'-B',build,
            '-DCMAKE_GENERATOR_INSTANCE=C:/BuildTools,version=17.14.37516.0','-DPython3_EXECUTABLE='+sys.executable],300)
        run('build',[cmake,'--build',build,'--config','Release','--parallel','1'],1800)
        _,raw=run('registered',[ctest,'--test-dir',build,'-C','Release','--show-only=json-v1'])
        registered=json.loads(raw)['tests'];assert sorted(t['name'] for t in registered)==expected['groups']
        result['registered_native_groups']=len(registered)
        headers=sorted(p for folder in build.glob('*_headers.dir') for p in (folder/'Release').glob('*.obj'))
        assert len(headers)==expected['standalone_headers']==68
        result['standalone_headers']=[dict(path=p.relative_to(work).as_posix(),sha256=retention.sha(p)) for p in headers]
        identity=json.loads((build/'generated/build-identity.json').read_bytes());result['build_identity']=identity
        dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe');result['executables']={}
        for name in expected['executables']:
            path=build/'Release'/(name+'.exe');image=path.read_bytes();offset=struct.unpack_from('<I',image,60)[0]
            assert image[offset:offset+4]==b'PE\0\0' and struct.unpack_from('<H',image,offset+4)[0]==0x8664
            result['executables'][name]=dict(bytes=len(image),sha256=hashlib.sha256(image).hexdigest(),machine='0x8664')
            for mode in ('headers','imports','dependents'):
                _,raw=run(name+'-'+mode,[dumpbin,'/nologo','/'+mode,path],60)
                if mode=='headers':assert all(text in raw for text in (b'Dynamic base',b'NX compatible',b'Control Flow Guard'))
                if mode=='dependents':assert not re.search(rb'(?:MSVCP|VCRUNTIME|UCRTBASE|API-MS-WIN-CRT)[^\s]*\.DLL',raw.upper())
        result['native_build_passed']=True
        for test in expected['groups']:
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
        result['full_x64_product_suite_run']=len(result['tests'])==178 and all(t['passed'] for t in result['tests'])
        assert result['full_x64_product_suite_run']
        result.update(status='pass',qualification='Native groups/build/header/import run only; final W105 expectation/tooling/portability review still required')
    except BaseException:
        result.update(status='fail',error=traceback.format_exc()[-8192:])
        raise
    finally:
        try:
            stop()
            if instance:instance.close()
            if grant:grant.retire(quiescent=quiescent);result['crypto_device']=grant.report;grant.close()
            result.update(all_owned_processes_retired=True,crypto_device_retired=True)
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
