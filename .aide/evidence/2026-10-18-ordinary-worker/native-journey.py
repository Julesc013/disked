"""One real x64 compile/store journey in the proven32MiB ordinary profile."""
import ctypes as C
from ctypes import wintypes as T
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
    helper=g.load('journey_crypto',ROOT/'crypto-device.py')
    result=dict(status='running',scope='Representative x64 compiler and production store-helper journey only; not full product qualification',all_owned_processes_retired=False,crypto_device_retired=False)
    grant,instance,job,child=None,None,None,None;quiescent=True
    def stop():
        nonlocal job,child,quiescent
        if job:result.setdefault('job_retirements',[]).append(g.retire_job(job));job=None
        if child:child.wait(timeout=10);child.close();child=None
        quiescent=True
    try:
        if Path(__file__).resolve().parent!=ROOT:raise ValueError('Fixed guest source only')
        data=g.actor();private={key:os.environ.pop(key) for key in list(os.environ) if key.startswith('DISKED_TEST_ACTOR_')}
        state=json.loads((ROOT/'scratch/state.json').read_bytes());assert state['size_mib']==32
        expected=json.loads((ROOT/'expected.json').read_bytes())['native_journey']
        source_manifest=json.loads((ROOT/'source-manifest.json').read_bytes())
        inputs={row['path']:row['sha256'].lower() for row in source_manifest['files'] if row['path'].startswith('source/') or row['path']=='native-journey.cpp'}
        assert len(inputs)==8
        for path,sha in inputs.items():assert hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha
        result['source_inputs']=inputs
        grant=helper.Grant();grant.apply();grant.started()
        work=g.fresh(g.W.plain_directory(state['work'])/'native');instance=g.worker(work,private,namespace_compat=True)
        for name in ('obj','records'):(work/name).mkdir()
        outside=ROOT/'scratch/outside';outside.mkdir()
        instance.apply_acl(outside,'D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;'+instance.coordinator_sid+')(A;OICI;0x1301bf;;;BU)')
        vc=Path('C:/BuildTools/VC/Tools/MSVC/14.44.35207');sdk=Path('C:/Program Files (x86)/Windows Kits/10');binary=vc/'bin/Hostx64/x64'
        env=dict(os.environ,DISKED_WORK_ROOT=str(work),PATH=str(binary)+os.pathsep+os.environ['PATH'],
            INCLUDE=os.pathsep.join(str(p) for p in [vc/'include',*[sdk/'Include/10.0.19041.0'/name for name in ('ucrt','shared','um')]]),
            LIB=os.pathsep.join(str(p) for p in [vc/'lib/x64',*[sdk/'Lib/10.0.19041.0'/name/'x64' for name in ('ucrt','um')]]))
        for name in ('CL','_CL_'):env.pop(name,None)
        result['commands']=[]
        def run(label,command,*,original=False):
            nonlocal job,child,quiescent
            job=g.S.WindowsJob();quiescent=False;started=time.monotonic()
            child=instance.launch(list(map(str,command)),env,job,variant='basic-stdio',diagnostic_original=original)
            code=child.wait(timeout=120);raw=instance.log_path.read_bytes();assert len(raw)<=131072
            row=dict(label=label,arguments=list(map(str,command)),exit_code=code,seconds=time.monotonic()-started,output=raw.decode(errors='replace'),launch=instance.last_launch)
            result['commands'].append(row);stop()
            if code:raise RuntimeError(label+' failed: '+hex(code))
            return row['output']
        executable=work/'store-journey.exe'
        arguments=['/Bv','/nologo','/std:c++17','/W4','/WX','/MT','/O2','/EHsc','/GS','/sdl','/guard:cf','/permissive-','/utf-8','/D_WIN32_WINNT=0x0A00','/I'+str(ROOT/'source'),'/Fo'+str(work/'obj')+'\\','/Fe'+str(executable),str(ROOT/'native-journey.cpp'),*[str(ROOT/path) for path in ('source/runtime/command/json.cpp','source/portable/hash/sha256.cpp','source/providers/image/local_file.cpp')],'advapi32.lib','kernel32.lib','/link','/DYNAMICBASE','/NXCOMPAT','/guard:cf']
        response=work/'compile.rsp';response.write_text(subprocess.list2cmdline(arguments),encoding='utf-8')
        result['compile_arguments']=arguments;result['response_sha256']=hashlib.sha256(response.read_bytes()).hexdigest()
        output=run('compile',[binary/'cl.exe','@'+str(response)])
        assert '19.44.35228' in output
        image=executable.read_bytes();pe=struct.unpack_from('<I',image,60)[0]
        assert image[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',image,pe+4)[0]==0x8664
        digest=hashlib.sha256(image).hexdigest();result['artifact']=dict(bytes=len(image),sha256=digest,pe_machine='0x8664')
        aliases=json.loads(run('standard-namespace-aliases',[executable,'--namespace-aliases'],original=True))
        assert aliases['status']=='pass' and aliases['same_local_object'] and aliases['session']==0
        result['standard_namespace_aliases']=aliases
        observed=json.loads(run('store',[executable,work/'records',data['sid'],outside/'native-forbidden']))
        assert observed['status']=='pass' and observed['user_sid']==data['sid'] and observed['restricted'] and observed['elevated']==observed['appcontainer']==0
        assert observed['pointer_bits']==64 and observed['msc_full_ver']==194435228 and observed['outside_error']==5 and observed['lease_reopened']
        assert observed['record_sddl']=='D:P(A;;FA;;;'+data['sid']+')' and observed['record_sha256']==hashlib.sha256(b'TWO').hexdigest() and observed['self_sha256']==digest
        result['native']=observed
        g.W.bind(instance.a,'ImpersonateLoggedOnUser',T.BOOL,T.HANDLE);g.W.bind(instance.a,'RevertToSelf',T.BOOL)
        g.W.require(instance.a.ImpersonateLoggedOnUser(instance.original))
        try:assert (work/'records/record.bin').read_bytes()==b'TWO'
        finally:g.W.require(instance.a.RevertToSelf())
        imports=run('imports',[binary/'dumpbin.exe','/nologo','/dependents',executable])
        assert not any(name in imports.lower() for name in ('vcruntime140.dll','msvcp140.dll','ucrtbase.dll','api-ms-win-crt'))
        assert hashlib.sha256(executable.read_bytes()).hexdigest()==digest
        assert all(hashlib.sha256((ROOT/path).read_bytes()).hexdigest()==sha for path,sha in inputs.items())
        result.update(status='pass',compiler_sha256=hashlib.sha256((binary/'cl.exe').read_bytes()).hexdigest(),linker_sha256=hashlib.sha256((binary/'link.exe').read_bytes()).hexdigest(),independent_record_read=True,source_unchanged=True,full_product_qualified=False)
    except BaseException:
        result.update(status='fail',error=traceback.format_exc()[-8192:]);raise
    finally:
        try:
            stop()
            if instance:instance.close()
            if grant:
                grant.retire(quiescent=quiescent);result['crypto_device']=grant.report;result['crypto_device_retired']=True;grant.close()
            else:result['crypto_device_retired']=True
            result['all_owned_processes_retired']=True
        except BaseException:
            result.update(status='fail',cleanup_error=traceback.format_exc()[-8192:]);raise
        finally:(ROOT/'proof-result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
