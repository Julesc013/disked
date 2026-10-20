"""Guest-only32MiB ordinary-worker baseline plus bounded native byte-I/O proof."""
import ctypes as C
from ctypes import wintypes as T
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import time
import traceback

ROOT=Path('C:/ProgramData/DiskEd/qualification')


def coordinate(g, *, extension=None):
    if Path(__file__).resolve().parent!=ROOT:raise ValueError('Fixed guest source required')
    data=g.actor();private={k:v for k,v in os.environ.items() if k.startswith('DISKED_TEST_ACTOR_')}
    state=json.loads((ROOT/'scratch/state.json').read_bytes())
    assert state['size_mib']==32
    expected=json.loads((ROOT/'expected.json').read_bytes())['native_port']
    helper=g.load('port_crypto',ROOT/'crypto-device.py')
    module=g.load('port_executor',ROOT/'windows_executor.py')
    grant,instance,job,child,executor=None,None,None,None,None
    primitive_started=False
    result=dict(status='running',scope='Current32MiB ordinary baseline plus native raw-byte port controls;no product/reference/full-campaign admission',
                all_owned_processes_retired=False,crypto_device_retired=False,controls=[],job_limits=[])
    def new_job():
        selected=g.S.WindowsJob(memory_bytes=expected['limits']['job_commit_bytes'],process_limit=expected['limits']['job_processes'])
        try:
            query=g.W.bind(selected.api,'QueryInformationJobObject',T.BOOL,T.HANDLE,C.c_int,C.c_void_p,T.DWORD,C.c_void_p)
            observed=selected.limit_info_type();g.W.require(query(selected.handle,9,C.byref(observed),C.sizeof(observed),None))
            assert observed.basic.flags&0x2208==0x2208
            assert observed.job_memory==expected['limits']['job_commit_bytes'] and observed.basic.active==expected['limits']['job_processes']
            result['job_limits'].append(dict(flags=hex(observed.basic.flags),job_commit_bytes=observed.job_memory,process_limit=observed.basic.active))
            return selected
        except BaseException:selected.close();raise
    try:
        manifest=json.loads((ROOT/'source-manifest.json').read_bytes())
        inputs={row['path']:row['sha256'].lower() for row in manifest['files']}
        assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==value for path,value in inputs.items())
        result['source_inputs']=inputs
        grant=helper.Grant();grant.apply();grant.started()
        # Same current launcher source, original capacity/write/canary/abrupt
        # controls. No result from an older revision is substituted here.
        primitive_started=True;g.main()
        result['primitive_proof']=json.loads((ROOT/'proof-result.json').read_bytes())
        assert result['primitive_proof']['status']=='pass' and result['primitive_proof']['all_owned_processes_retired']
        work=g.fresh(g.W.plain_directory(state['work'])/'raw-port')
        instance=g.worker(work,private,namespace_compat=True)
        (work/'obj').mkdir()
        assert shutil.disk_usage(work).free>=8*1024*1024
        vc=Path('C:/BuildTools/VC/Tools/MSVC/14.44.35207');sdk=Path('C:/Program Files (x86)/Windows Kits/10');binary=vc/'bin/Hostx64/x64'
        env=dict(os.environ,DISKED_WORK_ROOT=str(work),PATH=str(binary)+os.pathsep+os.environ['PATH'],
            INCLUDE=os.pathsep.join(str(p) for p in [vc/'include',*[sdk/'Include/10.0.19041.0'/name for name in ('ucrt','shared','um')]]),
            LIB=os.pathsep.join(str(p) for p in [vc/'lib/x64',*[sdk/'Lib/10.0.19041.0'/name/'x64' for name in ('ucrt','um')]]))
        for name in ('CL','_CL_'):env.pop(name,None)
        executable=work/'native-port.exe'
        args=['/Bv','/nologo','/std:c++17','/W4','/WX','/MT','/O2','/EHsc','/GS','/sdl','/guard:cf','/permissive-','/utf-8',
              '/D_WIN32_WINNT=0x0A00','/Fo'+str(work/'obj')+'\\','/Fe'+str(executable),str(ROOT/'native-port.cpp'),
              'kernel32.lib','advapi32.lib','/link','/DYNAMICBASE','/NXCOMPAT','/guard:cf']
        response=work/'compile.rsp';response.write_text(subprocess.list2cmdline(args),encoding='utf-8')
        result['compile_arguments']=args;job=new_job();started=time.monotonic()
        child=instance.launch([str(binary/'cl.exe'),'@'+str(response)],env,job)
        code=child.wait(timeout=120);raw=instance.log_path.read_bytes();assert len(raw)<=131072
        result['compile']=dict(exit_code=code,seconds=time.monotonic()-started,stdout_stderr=raw.decode(errors='replace'),launch=instance.last_launch)
        result['compile_retirement']=g.retire_job(job);job=None;child.close();child=None
        assert code==0 and '19.44.35228' in result['compile']['stdout_stderr']
        image=executable.read_bytes();offset=struct.unpack_from('<I',image,60)[0]
        assert image[offset:offset+4]==b'PE\0\0' and struct.unpack_from('<H',image,offset+4)[0]==0x8664
        result['artifact']=dict(bytes=len(image),sha256=hashlib.sha256(image).hexdigest(),pe_machine='0x8664')
        executor=module.WindowsFileExecutor(instance,env,new_job,g.retire_job)
        def run(name,mode,payload=None,timeout=10,limit=1048576):
            value=executor(argv=[str(executable),mode],cwd=work,payload=payload,timeout=timeout,output_limit=limit)
            result['controls'].append(dict(name=name,outcome=value['outcome'],exit_code=value['exit_code'],
                stdout_hex=value['stdout'].hex() if len(value['stdout'])<=4096 else None,
                stderr_hex=value['stderr'].hex() if len(value['stderr'])<=4096 else None,
                stdout_bytes=len(value['stdout']),stderr_bytes=len(value['stderr']),terminal=value['terminal']))
            assert value['terminal'] and executor.observations[-1]['temporary_files_removed']
            return value
        value=run('identity','identity');observed=json.loads(value['stdout']);result['native_identity']=observed
        assert value['outcome']=='exited' and value['exit_code']==0 and not value['stderr']
        assert observed['sid']==data['sid'] and observed['restricted'] and observed['in_job'] and not observed['elevated'] and not observed['appcontainer']
        assert observed['stdio']==[executor.observations[-1]['launch']['stdio_identities'][key] for key in ('stdin','stdout','stderr')]
        assert len({row['identity'] for row in observed['stdio']})==3
        payload=bytes(range(256))*3
        value=run('binary-echo','echo',payload);assert value['exit_code']==0 and value['stdout']==payload and value['stderr']==b'\0ERR\xff\r\n'
        value=run('empty-input','echo',b'');assert value['exit_code']==0 and value['stdout']==b'' and value['stderr']==b'\0ERR\xff\r\n'
        value=run('refusal','refuse');assert value['outcome']=='exited' and value['exit_code']==7 and value['stdout']==b'OUT' and value['stderr']==b'ERR'
        value=run('timeout','sleep',timeout=.1,limit=4096);assert value['outcome']=='timeout' and value['elapsed_seconds']<=2.1
        value=run('descendant','parent');assert value['outcome']=='exited' and value['exit_code']==0 and value['stdout']==b'PARENTCHILD'
        assert executor.observations[-1]['job_retirement']['total_processes']>=2
        (work/'grandchild.ready').unlink()
        value=run('output-limit','overrun',limit=4096);assert value['outcome']=='output_limit' and value['stdout']==b'A'*4096 and not value['stderr']
        assert sum(executor.observations[-1]['produced_bytes'].values())>4096
        value=run('job-memory','memory');memory=json.loads(value['stdout']);result['memory_control']=memory
        assert value['outcome']=='exited' and value['exit_code']==0 and memory['denied'] and memory['error']!=0 and memory['available_commit_before']>=512*1024*1024
        assert len(result['controls'])==8
        if extension is not None:extension(work,env,executor,result)
        assert not list(work.glob('raw-input-*')) and not list(work.glob('raw-*.stdout')) and not list(work.glob('raw-*.stderr'))
        assert hashlib.sha256(executable.read_bytes()).hexdigest()==result['artifact']['sha256']
        assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==value for path,value in inputs.items())
        result['compiler_sha256']=hashlib.sha256((binary/'cl.exe').read_bytes()).hexdigest()
        result['linker_sha256']=hashlib.sha256((binary/'link.exe').read_bytes()).hexdigest()
        result.update(status='pass',source_unchanged=True,stdio_residuals=0,reference_tools_run=False,full_product_qualified=False)
    except BaseException:
        result.update(status='fail',error=traceback.format_exc()[-16384:]);raise
    finally:
        try:
            if executor:executor.close();result['port_observations']=executor.observations
            if job:result['failure_retirement']=g.retire_job(job);job=None
            if child:child.wait(timeout=1);child.close();child=None
            if instance:instance.close()
            if primitive_started and 'primitive_proof' not in result:
                path=ROOT/'proof-result.json'
                if path.exists():result['primitive_proof']=json.loads(path.read_bytes())
            if primitive_started:
                primitive=result.get('primitive_proof',{})
                if (primitive.get('all_owned_processes_retired') is not True or primitive.get('image_uuid')!=state['image_uuid'] or
                        primitive.get('actor',{}).get('sid')!=data['sid']):
                    raise RuntimeError('Primitive worker quiescence unverified;preserve actor/image')
            result['all_owned_processes_retired']=True
            if grant:grant.retire(quiescent=True);result['crypto_device']=grant.report;grant.close()
            result['crypto_device_retired']=True
        except BaseException:
            result.update(status='fail',cleanup_error=traceback.format_exc()[-16384:]);raise
        finally:(ROOT/'proof-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
