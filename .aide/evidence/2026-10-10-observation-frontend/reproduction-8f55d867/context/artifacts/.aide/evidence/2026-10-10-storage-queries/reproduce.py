"""Clean exact-source private Win32 metadata/extent fixture qualification."""
import argparse,hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',type=Path,default=Path.cwd())
    p.add_argument('--source-revision',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert re.fullmatch('[0-9a-f]{40}',a.source_revision);root=a.repository.absolute();out=a.output.absolute();out.mkdir();logs=out/'logs';logs.mkdir();commands=[]
    def run(name,args,cwd,limit=180):
        args=list(map(str,args));start=time.monotonic();r=subprocess.run(args,cwd=cwd,capture_output=True,timeout=limit)
        log=logs/(name+'.log');log.write_bytes(r.stdout+r.stderr);commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=r.returncode,elapsed_seconds=round(time.monotonic()-start,3),log='logs/'+log.name))
        save(out/'commands.json',commands);print(name+' exit '+str(r.returncode),flush=True)
        if r.returncode:raise RuntimeError(name+' failed '+str(log))
        return r.stdout
    checkout=out/'checkout';run('clone',['git','clone','--local','--no-hardlinks','--no-checkout',root,checkout],root)
    run('checkout',['git','checkout','--detach',a.source_revision],checkout);assert not run('source-status',['git','status','--porcelain'],checkout).strip()
    host=json.loads(run('host',['powershell','-NoProfile','-Command','$diskedIdentity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$diskedPrincipal=[System.Security.Principal.WindowsPrincipal]::new($diskedIdentity);$diskedOS=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$diskedIdentity.Name;elevated=$diskedPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$diskedOS.Caption;version=$diskedOS.Version;architecture=$diskedOS.OSArchitecture}|ConvertTo-Json -Compress'],checkout))
    assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated'];inputs={}
    for folder in ('source/platform/windows/storage','source/providers/windows','source/runtime/graph','tests/windows','source/portable/hash'):
        for f in (checkout/folder).rglob('*'):
            if f.is_file():inputs[f.relative_to(checkout).as_posix()]=sha(f)
    for n in ('source/runtime/command/json.cpp','source/runtime/command/json.h','spec/catalog/nt-storage-observation-prototype.json',
              'spec/storage/windows.md','spec/operations/inventory.md','.aide/evidence/2026-10-10-storage-queries/reproduce.py'):
        inputs[n]=sha(checkout/n)
    for n,d in inputs.items():assert 'sha256:'+hashlib.sha256(subprocess.check_output(['git','show',a.source_revision+':'+n],cwd=checkout)).hexdigest()==d,n
    assert sha(Path(__file__).absolute())==inputs['.aide/evidence/2026-10-10-storage-queries/reproduce.py'];save(out/'source-inputs.json',inputs)
    prior='3463fb238c38f4dbe085061c7980aaf7eaab53d2';product_inputs=json.loads((checkout/'.aide/evidence/2026-10-10-namespace-graph/reproduction-3463fb23/product-build-identity.json').read_bytes())['inputs']
    assert all(sha(checkout/n)==d for n,d in product_inputs.items());save(out/'unchanged-product-inputs.json',dict(qualified_source_revision=prior,inputs=product_inputs,scope='Exact product input bytes unchanged; no new product build or native full-suite claim.'))
    run('cmake-version',['cmake','--version'],checkout);run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],checkout)
    campaigns=[];artifacts=[];dumpbin=Path('C:/Program Files/Microsoft Visual Studio/2022/Enterprise/VC/Tools/MSVC/14.44.35207/bin/Hostx64/x64/dumpbin.exe')
    for arch,pointer in [('x64',8),('Win32',4)]:
        build=out/('build-'+arch);run('configure-'+arch,['cmake','-S',checkout/'tests/windows/native','-B',build,'-G','Visual Studio 17 2022','-A',arch+',version=10.0.19041.0','-T','v143,version=14.44.35207,host=x64','-DCMAKE_SYSTEM_VERSION=10.0.19041.0'],checkout)
        run('build-'+arch,['cmake','--build',build,'--config','Release','--target','nt_storage_query_probe','--parallel','4'],checkout)
        probe=build/'Release/nt_storage_query_probe.exe';campaign=out/('campaign-'+arch)
        run('cases-'+arch,[sys.executable,checkout/'tests/windows/test_storage_queries.py','--probe',probe,'--output',campaign,'--pointer-bytes',pointer],checkout)
        result=json.loads((campaign/'results.json').read_bytes());assert result['status']=='pass' and result['native_executions']==70 and result['assertions']==1987 and result['pointer_bytes']==pointer
        campaigns.append(dict(architecture=arch,native_executions=result['native_executions'],assertions=result['assertions'],pointer_bytes=pointer))
        for mode in ('headers','imports','dependents'):run(mode+'-'+arch,[dumpbin,'/'+mode,probe],checkout)
        assert b'DeviceIoControl' in (logs/('imports-'+arch+'.log')).read_bytes()
        config=out/('build-configuration-'+arch);config.mkdir()
        for n in ('CMakeCache.txt','nt_storage_query_probe.vcxproj'):shutil.copyfile(build/n,config/n)
        for f in (build/'CMakeFiles').rglob('CMake*Compiler.cmake'):shutil.copyfile(f,config/f.name)
        artifacts.append(dict(path=str(probe),architecture=arch,bytes=probe.stat().st_size,sha256=sha(probe)))
    run('tooling-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],checkout,300)
    log=(logs/'tooling-tests.log').read_text(encoding='utf-8');ran=re.search(r'^Ran (\d+) tests? in ',log,re.MULTILINE);passed=re.search(r'^OK(?: \(skipped=(\d+)\))?$',log,re.MULTILINE);assert ran and passed
    count=int(ran.group(1));skip=int(passed.group(1) or 0);check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check'],checkout))
    run('index-freshness',[sys.executable,'spec/tools/specctl.py','index','--check'],checkout)
    run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W030','--output',out/'context','--byte-budget','530000'],checkout)
    run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context',out/'context'],checkout);run('verify-manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest'],checkout)
    assert not run('final-source-status',['git','status','--porcelain'],checkout).strip();assert all(sha(checkout/n)==d for n,d in inputs.items())
    summary=dict(status='pass',source_revision=a.source_revision,host=host,source_inputs=len(inputs),campaigns=campaigns,artifacts=artifacts,tooling_tests=dict(run=count,passed=count-skip,skipped=skip),structural_checks=check['checks'],
        prior_product_source=prior,unchanged_product_inputs=len(product_inputs),product_rebuilt=False,product_suite_rerun=False,live_storage_qualified=False,physical_access=False,worker_containment_qualified=False,provider_admitted=False,historical_windows_qualified=False,unit_complete=False,owner_accepted=False,remote_writes=False)
    save(out/'results.json',summary);print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
