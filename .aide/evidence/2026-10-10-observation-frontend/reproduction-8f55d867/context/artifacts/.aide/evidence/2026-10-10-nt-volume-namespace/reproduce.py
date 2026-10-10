"""Clean exact-source x64/x86 injected-API qualification; no live inventory."""
import argparse,hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path

def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository',type=Path,default=Path.cwd());p.add_argument('--source-revision',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args();root=a.repository.absolute();out=a.output.absolute()
    out.mkdir();logs=out/'logs';logs.mkdir();receipts=[]
    def run(name,args,cwd):
        command=[str(x) for x in args];started=time.monotonic();result=subprocess.run(command,cwd=cwd,capture_output=True)
        log=logs/(name+'.log');log.write_bytes(result.stdout+result.stderr)
        receipts.append(dict(name=name,command=command,cwd=str(cwd),exit_code=result.returncode,elapsed_seconds=round(time.monotonic()-started,3),log='logs/'+log.name))
        save(out/'commands.json',receipts)
        if result.returncode:raise AssertionError((name,result.returncode,str(log)))
        return result.stdout
    checkout=out/'checkout'
    run('clone',['git','clone','--local','--no-hardlinks','--no-checkout',root,checkout],root)
    run('checkout',['git','checkout','--detach',a.source_revision],checkout)
    assert not run('source-status',['git','status','--porcelain'],checkout).strip()
    host=json.loads(run('host',['powershell','-NoProfile','-Command',
        "$diskedIdentity = [System.Security.Principal.WindowsIdentity]::GetCurrent(); $diskedPrincipal = [System.Security.Principal.WindowsPrincipal]::new($diskedIdentity); [ordered]@{identity=$diskedIdentity.Name;elevated=$diskedPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)} | ConvertTo-Json"],checkout))
    assert host==dict(identity='BLACKGLASS-WIN1\\Jules',elevated=False)
    inputs={}
    for folder in ('source/platform/windows/storage','source/providers/windows','tests/windows'):
        for path in sorted((checkout/folder).rglob('*')):
            if path.is_file():inputs[path.relative_to(checkout).as_posix()]=sha(path)
    for name in ('source/runtime/command/json.cpp','source/runtime/command/json.h','spec/catalog/nt-volume-namespace-prototype.json',
                 '.aide/evidence/2026-10-10-nt-volume-namespace/reproduce.py'):
        inputs[name]=sha(checkout/name)
    for name,value in inputs.items():
        blob=subprocess.check_output(['git','-C',str(checkout),'show',a.source_revision+':'+name])
        assert 'sha256:'+hashlib.sha256(blob).hexdigest()==value,name
    assert sha(Path(__file__).absolute())==inputs['.aide/evidence/2026-10-10-nt-volume-namespace/reproduce.py']
    save(out/'source-inputs.json',inputs);run('cmake-version',['cmake','--version'],checkout)
    dumpbin=Path('C:/Program Files/Microsoft Visual Studio/2022/Enterprise/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/dumpbin.exe')
    artifacts=[];campaigns=[]
    for arch,pointer in [('x64',8),('Win32',4)]:
        build=out/('build-'+arch)
        run('configure-'+arch,['cmake','-S',checkout/'tests/windows/native','-B',build,'-G','Visual Studio 17 2022',
            '-A',arch+',version=10.0.19041.0','-T','v143,version=14.44.35207,host=x64','-DCMAKE_SYSTEM_VERSION=10.0.19041.0'],checkout)
        run('build-'+arch,['cmake','--build',build,'--config','Release'],checkout)
        probe=build/'Release/nt_volume_namespace_probe.exe';campaign=out/('campaign-'+arch)
        run('cases-'+arch,[sys.executable,checkout/'tests/windows/test_volume_namespace.py','--probe',probe,'--output',campaign,'--pointer-bytes',str(pointer)],checkout)
        result=json.loads((campaign/'results.json').read_bytes())
        assert result['status']=='pass' and result['native_executions']==49 and result['assertions']>=228 and result['pointer_bytes']==pointer
        assert not result['live_namespace_qualified'] and not result['physical_access'] and not result['unit_complete']
        import_bytes=run('imports-'+arch,[dumpbin,'/imports',probe],checkout)
        for name in ('FindFirstVolumeW','FindNextVolumeW','FindVolumeClose','GetVolumePathNamesForVolumeNameW'):
            assert name.encode() in import_bytes,name
        run('headers-'+arch,[dumpbin,'/headers',probe],checkout);run('dependents-'+arch,[dumpbin,'/dependents',probe],checkout)
        config=out/('build-configuration-'+arch);config.mkdir()
        for name in ('CMakeCache.txt','nt_volume_namespace_probe.vcxproj'):
            shutil.copyfile(build/name,config/name)
        for path in (build/'CMakeFiles').rglob('CMake*Compiler.cmake'):shutil.copyfile(path,config/path.name)
        artifacts.append(dict(path=str(probe),bytes=probe.stat().st_size,sha256=sha(probe),architecture=arch))
        campaigns.append(dict(architecture=arch,native_executions=result['native_executions'],assertions=result['assertions'],pointer_bytes=pointer))
    run('tooling-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],checkout)
    tooling_log=(logs/'tooling-tests.log').read_text(encoding='utf-8')
    ran=re.search(r'^Ran (\d+) tests? in ',tooling_log,re.MULTILINE)
    passed=re.search(r'^OK(?: \(skipped=(\d+)\))?$',tooling_log,re.MULTILINE)
    assert ran and passed,'Actual unittest completion/count missing'
    tooling_run=int(ran.group(1));tooling_skipped=int(passed.group(1) or 0)
    tooling=dict(run=tooling_run,passed=tooling_run-tooling_skipped,skipped=tooling_skipped)
    check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check'],checkout))
    run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W030','--output',out/'context','--byte-budget','430000'],checkout)
    run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context',out/'context'],checkout)
    run('verify-manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest'],checkout)
    assert not run('final-source-status',['git','status','--porcelain'],checkout).strip()
    assert all(sha(checkout/name)==value for name,value in inputs.items())
    summary=dict(status='pass',source_revision=a.source_revision,host=host,source_inputs=len(inputs),campaigns=campaigns,artifacts=artifacts,
        tooling_tests=tooling,structural_checks=check['checks'],
        native_table_bound=True,live_namespace_qualified=False,physical_access=False,product_native_rebuilt=False,
        XP_qualified=False,provider_admitted=False,unit_complete=False,owner_accepted=False,remote_writes=False)
    save(out/'results.json',summary);print(json.dumps(summary))
if __name__=='__main__':main()
