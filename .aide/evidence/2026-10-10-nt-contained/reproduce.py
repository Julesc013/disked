"""Clean same-file contained injected-reader qualification; no live inventory."""
import argparse,hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',type=Path,default=Path.cwd());p.add_argument('--source-revision',required=True);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();root=a.repository.absolute();out=a.output.absolute();out.mkdir();logs=out/'logs';logs.mkdir();commands=[]
    def run(name,args,cwd):
        args=[str(x) for x in args];start=time.monotonic();r=subprocess.run(args,cwd=cwd,capture_output=True);log=logs/(name+'.log');log.write_bytes(r.stdout+r.stderr)
        commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=r.returncode,elapsed_seconds=round(time.monotonic()-start,3),log='logs/'+log.name));save(out/'commands.json',commands)
        assert r.returncode==0,(name,r.returncode,str(log));return r.stdout
    checkout=out/'checkout';run('clone',['git','clone','--local','--no-hardlinks','--no-checkout',root,checkout],root);run('checkout',['git','checkout','--detach',a.source_revision],checkout)
    assert not run('source-status',['git','status','--porcelain'],checkout).strip()
    host=json.loads(run('host',['powershell','-NoProfile','-Command',
        "$diskedIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent(); $diskedPrincipal = [System.Security.Principal.WindowsPrincipal]::new($diskedIdentity); [ordered]@{identity=$diskedIdentity.Name;elevated=$diskedPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=[Environment]::OSVersion.VersionString} | ConvertTo-Json"],checkout))
    assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
    inputs={}
    for folder in ('source/platform/windows/storage','source/providers/windows','tests/windows'):
        for path in sorted((checkout/folder).rglob('*')):
            if path.is_file():inputs[path.relative_to(checkout).as_posix()]=sha(path)
    for name in ('source/runtime/command/json.cpp','source/runtime/command/json.h','source/platform/windows/worker_files.h','source/providers/image/local_file.cpp','source/providers/image/local_file.h',
        'source/portable/hash/sha256.cpp','source/portable/hash/sha256.h','spec/catalog/ordinary-file-path-profile.json','spec/catalog/nt-volume-namespace-prototype.json',
        'spec/catalog/nt-namespace-worker-prototype.json','.aide/evidence/2026-10-10-nt-contained/reproduce.py'):
        inputs[name]=sha(checkout/name)
    for name,value in inputs.items():
        assert 'sha256:'+hashlib.sha256(subprocess.check_output(['git','show',a.source_revision+':'+name],cwd=checkout)).hexdigest()==value,name
    assert sha(Path(__file__).absolute())==inputs['.aide/evidence/2026-10-10-nt-contained/reproduce.py'];save(out/'source-inputs.json',inputs)
    run('cmake-version',['cmake','--version'],checkout);dumpbin=Path('C:/Program Files/Microsoft Visual Studio/2022/Enterprise/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/dumpbin.exe')
    artifacts=[];campaigns=[]
    for arch,pointer in [('x64',8),('Win32',4)]:
        build=out/('build-'+arch);run('configure-'+arch,['cmake','-S',checkout/'tests/windows/native','-B',build,'-G','Visual Studio 17 2022','-A',arch+',version=10.0.19041.0','-T','v143,version=14.44.35207,host=x64','-DCMAKE_SYSTEM_VERSION=10.0.19041.0'],checkout)
        run('build-'+arch,['cmake','--build',build,'--config','Release'],checkout)
        for kind,program,script in [('adapter','nt_volume_namespace_probe','test_volume_namespace.py'),('worker','nt_namespace_worker_probe','test_namespace_worker.py')]:
            binary=build/('Release/'+program+'.exe');campaign=out/(kind+'-'+arch);run(kind+'-'+arch,[sys.executable,checkout/('tests/windows/'+script),'--probe',binary,'--output',campaign,'--pointer-bytes',str(pointer)],checkout)
            result=json.loads((campaign/'results.json').read_bytes());assert result['status']=='pass' and result['pointer_bytes']==pointer
            if kind=='adapter':assert result['native_executions']==49 and result['assertions']==258
            else:assert result['controller_executions']==23 and result['actual_child_launches']==17 and result['assertions']==110
            campaigns.append(dict(kind=kind,architecture=arch,assertions=result['assertions'],executions=result.get('native_executions',result.get('controller_executions')),child_launches=result.get('actual_child_launches',0),pointer_bytes=pointer))
            imports=run('imports-'+program+'-'+arch,[dumpbin,'/imports',binary],checkout)
            for api in ('FindFirstVolumeW','FindNextVolumeW','FindVolumeClose','GetVolumePathNamesForVolumeNameW'):assert api.encode() in imports
            run('headers-'+program+'-'+arch,[dumpbin,'/headers',binary],checkout);run('dependents-'+program+'-'+arch,[dumpbin,'/dependents',binary],checkout)
            artifacts.append(dict(architecture=arch,kind=kind,path=str(binary),bytes=binary.stat().st_size,sha256=sha(binary)))
        config=out/('build-configuration-'+arch);config.mkdir()
        for name in ('CMakeCache.txt','nt_volume_namespace_probe.vcxproj','nt_namespace_worker_probe.vcxproj'):shutil.copyfile(build/name,config/name)
        for path in (build/'CMakeFiles').rglob('CMake*Compiler.cmake'):shutil.copyfile(path,config/path.name)
    run('tooling-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],checkout)
    text=(logs/'tooling-tests.log').read_text(encoding='utf-8');ran=re.search(r'^Ran (\d+) tests? in ',text,re.MULTILINE);ok=re.search(r'^OK(?: \(skipped=(\d+)\))?$',text,re.MULTILINE);assert ran and ok
    n=int(ran.group(1));skipped=int(ok.group(1) or 0);check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check'],checkout))
    run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W030','--output',out/'context','--byte-budget','530000'],checkout)
    run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context',out/'context'],checkout);run('verify-manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest'],checkout)
    assert not run('final-source-status',['git','status','--porcelain'],checkout).strip();assert all(sha(checkout/name)==value for name,value in inputs.items())
    result=dict(status='pass',source_revision=a.source_revision,host=host,source_inputs=len(inputs),campaigns=campaigns,artifacts=artifacts,
        tooling_tests=dict(run=n,passed=n-skipped,skipped=skipped),structural_checks=check['checks'],
        live_namespace_qualified=False,physical_access=False,product_native_rebuilt=False,XP_qualified=False,provider_admitted=False,durable_reconnect=False,unit_complete=False,owner_accepted=False,remote_writes=False)
    save(out/'results.json',result);print(json.dumps(result))
if __name__=='__main__':main()
