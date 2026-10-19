"""Small exact-production x64 memory-budget component proof in32MiB guest."""
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import sys
import time
import traceback

ROOT=Path('C:/ProgramData/DiskEd/qualification')

def coordinate(g):
    result=dict(status='running',scope=__doc__,all_owned_processes_retired=False,
                crypto_device_retired=False,full_product_qualified=False,commands=[])
    grant=instance=job=child=None
    def stop():
        nonlocal job,child
        if job:result.setdefault('job_retirements',[]).append(g.retire_job(job));job=None
        if child:child.wait(timeout=10);child.close();child=None
    try:
        data=g.actor();private={key:os.environ.pop(key) for key in list(os.environ) if key.startswith('DISKED_TEST_ACTOR_')}
        state=json.loads((ROOT/'scratch/state.json').read_bytes());assert state['size_mib']==32
        expected=json.loads((ROOT/'expected.json').read_bytes())['native_memory']
        manifest=json.loads((ROOT/'source-manifest.json').read_bytes())
        inputs={row['path']:row['sha256'].lower() for row in manifest['files'] if row['path'].startswith('source/') or row['path'] in ('memory-journey.cpp','memory-desktop-driver.py','tests/frontend/gui_fixture.py')}
        assert set(inputs)==set(expected['inputs'])
        assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha for name,sha in inputs.items())
        result['source_inputs']=inputs
        grant=g.load('memory_crypto',ROOT/'crypto-device.py').Grant();grant.apply();grant.started()
        work=g.fresh(g.W.plain_directory(state['work'])/'memory-native');instance=g.worker(work,private,namespace_compat=True)
        (work/'obj').mkdir()
        vc=Path('C:/BuildTools/VC/Tools/MSVC/14.44.35207');sdk=Path('C:/Program Files (x86)/Windows Kits/10');binary=vc/'bin/Hostx64/x64'
        env=dict(os.environ,DISKED_WORK_ROOT=str(work),PATH=str(binary)+os.pathsep+os.environ['PATH'],
            INCLUDE=os.pathsep.join(str(p) for p in [vc/'include',*[sdk/'Include/10.0.19041.0'/n for n in ('ucrt','shared','um')]]),
            LIB=os.pathsep.join(str(p) for p in [vc/'lib/x64',*[sdk/'Lib/10.0.19041.0'/n/'x64' for n in ('ucrt','um')]]))
        for name in ('CL','_CL_'):env.pop(name,None)
        def run(label,command):
            nonlocal job,child
            job=g.S.WindowsJob();started=time.monotonic();child=instance.launch(list(map(str,command)),env,job,variant='basic-stdio')
            code=child.wait(timeout=120);raw=instance.log_path.read_bytes();assert len(raw)<=65536
            result['commands'].append(dict(label=label,arguments=list(map(str,command)),exit_code=code,seconds=time.monotonic()-started,output=raw.decode(errors='replace'),launch=instance.last_launch))
            stop()
            if code:raise RuntimeError(label+' failed: '+str(code))
            return raw.decode()
        exe=work/'memory-budget.exe'
        arguments=['/Bv','/nologo','/std:c++14','/W4','/WX','/MT','/O2','/EHsc','/GS','/sdl','/guard:cf','/permissive-','/utf-8','/D_WIN32_WINNT=0x0A00',
            '/I'+str(ROOT/'source'),'/Fo'+str(work/'obj')+'\\','/Fe'+str(exe),str(ROOT/'memory-journey.cpp'),str(ROOT/'source/platform/windows/memory_budget.cpp'),
            'kernel32.lib','/link','/DYNAMICBASE','/NXCOMPAT','/guard:cf']
        response=work/'compile.rsp';response.write_text(subprocess.list2cmdline(arguments),encoding='utf-8')
        result['response_sha256']=hashlib.sha256(response.read_bytes()).hexdigest()
        assert '19.44.35228' in run('compile',[binary/'cl.exe','@'+str(response)])
        payload=exe.read_bytes();offset=struct.unpack_from('<I',payload,60)[0]
        assert payload[:2]==b'MZ' and payload[offset:offset+4]==b'PE\0\0' and struct.unpack_from('<H',payload,offset+4)[0]==0x8664
        result['artifact']=dict(bytes=len(payload),sha256=hashlib.sha256(payload).hexdigest(),pe_machine='0x8664')
        observed=json.loads(run('production-memory-budget',[exe]));result['native']=observed
        assert observed['ready'] and observed['platform_error']==0 and observed['error']=='' and observed['process_limit_bytes']=='268435456'
        imports=run('dependents',[binary/'dumpbin.exe','/nologo','/dependents',exe])
        assert not any(name in imports.lower() for name in ('vcruntime140.dll','msvcp140.dll','ucrtbase.dll','api-ms-win-crt'))
        result['fixture_desktop_comparison']=json.loads(run('paired-fixture-desktops',[sys.executable,'-B',ROOT/'memory-desktop-driver.py',exe,data['sid']]))
        assert hashlib.sha256(exe.read_bytes()).hexdigest()==result['artifact']['sha256']
        assert all(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==sha for name,sha in inputs.items())
        result.update(status='pass',source_unchanged=True,compiler_sha256=hashlib.sha256((binary/'cl.exe').read_bytes()).hexdigest(),linker_sha256=hashlib.sha256((binary/'link.exe').read_bytes()).hexdigest())
    except BaseException:
        result.update(status='fail',error=traceback.format_exc()[-8192:]);raise
    finally:
        try:
            stop()
            if instance:instance.close()
            if grant:grant.retire(quiescent=True);result['crypto_device']=grant.report;grant.close()
            result.update(all_owned_processes_retired=True,crypto_device_retired=True)
        except BaseException:
            result.update(status='fail',cleanup_error=traceback.format_exc()[-8192:]);raise
        finally:(ROOT/'proof-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
