"""Clean exact-source private generated-image/raw-layout comparison qualification."""
import argparse,hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',type=Path,default=Path.cwd());p.add_argument('--source-revision',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert re.fullmatch('[0-9a-f]{40}',a.source_revision);root=a.repository.absolute();out=a.output.absolute();out.mkdir();logs=out/'logs';logs.mkdir();commands=[]
    def run(name,args,cwd,limit=180):
        args=list(map(str,args));start=time.monotonic();r=subprocess.run(args,cwd=cwd,capture_output=True,timeout=limit)
        log=logs/(name+'.log');log.write_bytes(r.stdout+r.stderr);commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=r.returncode,elapsed_seconds=round(time.monotonic()-start,3),log='logs/'+log.name))
        save(out/'commands.json',commands);print(name+' exit '+str(r.returncode),flush=True)
        if r.returncode:raise RuntimeError(name+' failed '+str(log))
        return r.stdout
    checkout=out/'checkout';run('clone',['git','clone','--local','--no-hardlinks','--no-checkout',root,checkout],root)
    run('checkout',['git','checkout','--detach',a.source_revision],checkout);assert not run('source-status',['git','status','--porcelain'],checkout).strip()
    run('source-map',[sys.executable,'tools/check-source-map.py'],checkout)
    host=json.loads(run('host',['powershell','-NoProfile','-Command','$diskedIdentity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$diskedPrincipal=[System.Security.Principal.WindowsPrincipal]::new($diskedIdentity);$diskedOS=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$diskedIdentity.Name;elevated=$diskedPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$diskedOS.Caption;version=$diskedOS.Version;architecture=$diskedOS.OSArchitecture}|ConvertTo-Json -Compress'],checkout))
    assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
    inputs={n:sha(checkout/n) for n in json.loads((checkout/'tools/build-inputs.json').read_bytes())['files']}
    for folder in ('source/platform/windows/storage','source/providers/windows','source/runtime/graph','source/runtime/capture','tests/windows','source/portable'):
        for f in (checkout/folder).rglob('*'):
            if f.is_file():inputs[f.relative_to(checkout).as_posix()]=sha(f)
    for n in ('source/providers/image/local_file.cpp','source/providers/image/local_file.h','source/platform/windows/memory_budget.cpp','source/platform/windows/memory_budget.h','tests/corpus/partition_images.py','spec/catalog/nt-raw-layout-prototype.json','spec/storage/windows.md','spec/architecture/repository.md','spec/catalog/input-dependencies.json','spec/work/units.json','docs/source-map.md','tools/check-source-map.py','.aide/evidence/2026-10-10-raw-layout/reproduce.py'):
        inputs[n]=sha(checkout/n)
    names=list(inputs);blobs=subprocess.check_output(['git','cat-file','--batch'],input=''.join(a.source_revision+':'+n+'\n' for n in names).encode(),cwd=checkout);at=0
    for n in names:
        end=blobs.index(b'\n',at);header=blobs[at:end].split();assert header[1]==b'blob';size=int(header[2]);start=end+1
        assert 'sha256:'+hashlib.sha256(blobs[start:start+size]).hexdigest()==inputs[n],n;at=start+size+1
    assert at==len(blobs);assert sha(Path(__file__).absolute())==inputs['.aide/evidence/2026-10-10-raw-layout/reproduce.py'];save(out/'source-inputs.json',inputs)
    prior=checkout/'.aide/evidence/2026-10-10-source-layout/reproduction-67f3cfb0'
    product=json.loads((prior/'product-build-identity.json').read_bytes());assert len(product['inputs'])==404
    assert set(product['inputs'])==set(json.loads((checkout/'tools/build-inputs.json').read_bytes())['files'])
    assert all(sha(checkout/n)==d for n,d in product['inputs'].items())
    old=prior/'product-prior';records=json.loads((old/'commands.json').read_bytes())
    assert all(next(x for x in records if x['name']==name)['exit_code']==0 for name in ('product-build','product-native','product-launch'))
    assert b'0 tests failed out of 77' in (old/'logs/product-native.log').read_bytes()
    save(out/'product-reuse.json',dict(product_source_revision=product['identity']['source_revision'],current_source_revision=a.source_revision,product_inputs=404,prior_evidence='.aide/evidence/2026-10-10-source-layout/reproduction-67f3cfb0',scope='Every product input byte-identical. Prior 77-group product evidence retained at its original revision; no product rebuild, suite rerun or new product feature claim.'))
    shutil.copyfile(prior/'product-build-identity.json',out/'product-build-identity.json')
    run('cmake-version',['cmake','--version'],checkout);run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],checkout)
    cases=[('raw-layout','nt_raw_layout_probe','test_raw_layout.py'),('identity-query','nt_identity_query_probe','test_identity_queries.py'),('storage-query','nt_storage_query_probe','test_storage_queries.py')]
    campaigns=[];artifacts=[];dumpbin=Path(product['compiler_path']).with_name('dumpbin.exe')
    for arch,pointer in [('x64',8),('Win32',4)]:
        build=out/('build-'+arch);run('configure-'+arch,['cmake','-S',checkout/'tests/windows/native','-B',build,'-G','Visual Studio 17 2022','-A',arch+',version=10.0.19041.0','-T','v143,version=14.44.35207,host=x64','-DCMAKE_SYSTEM_VERSION=10.0.19041.0'],checkout)
        run('build-'+arch,['cmake','--build',build,'--config','Release','--target',*[target for _,target,_ in cases],'--parallel','4'],checkout,600)
        config=out/('build-configuration-'+arch);config.mkdir();shutil.copyfile(build/'CMakeCache.txt',config/'CMakeCache.txt')
        for f in (build/'CMakeFiles').rglob('CMake*Compiler.cmake'):shutil.copyfile(f,config/f.name)
        for kind,target,script in cases:
            probe=build/('Release/'+target+'.exe');run(kind+'-'+arch,[sys.executable,checkout/('tests/windows/'+script),'--probe',probe,'--output',out/(kind+'-'+arch),'--pointer-bytes',pointer],checkout)
            result=json.loads((out/(kind+'-'+arch)/'results.json').read_bytes());assert result['status']=='pass' and result['pointer_bytes']==pointer
            count=result.get('processes',result.get('native_executions'));assert count==len(result['executions']);assert result['assertions']==len(result['checks']) and all(x['passed'] for x in result['checks'])
            if kind=='raw-layout':assert count==109 and result['assertions']==1342
            campaigns.append(dict(kind=kind,architecture=arch,processes=count,assertions=result['assertions'],pointer_bytes=pointer))
            for mode in ('headers','imports','dependents'):run(kind+'-'+mode+'-'+arch,[dumpbin,'/'+mode,probe],checkout)
            shutil.copyfile(build/(target+'.vcxproj'),config/(target+'.vcxproj'));artifacts.append(dict(kind=kind,architecture=arch,path=str(probe),bytes=probe.stat().st_size,sha256=sha(probe)))
    run('tooling-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],checkout,300)
    log=(logs/'tooling-tests.log').read_text(encoding='utf-8');ran=re.search(r'^Ran (\d+) tests? in ',log,re.MULTILINE);passed=re.search(r'^OK(?: \(skipped=(\d+)\))?$',log,re.MULTILINE);assert ran and passed
    count=int(ran.group(1));skip=int(passed.group(1) or 0);check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check'],checkout))
    run('index-freshness',[sys.executable,'spec/tools/specctl.py','index','--check'],checkout)
    run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W030','--output',out/'context','--byte-budget','680000'],checkout)
    run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context',out/'context'],checkout);run('verify-manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest'],checkout)
    assert not run('final-source-status',['git','status','--porcelain'],checkout).strip();assert all(sha(checkout/n)==d for n,d in inputs.items())
    save(out/'results.json',dict(status='pass',source_revision=a.source_revision,source_inputs=len(inputs),host=host,campaigns=campaigns,artifacts=artifacts,tooling_tests=dict(run=count,passed=count-skip,skipped=skip),structural_checks=check['checks'],product_inputs=404,product_source_revision=product['identity']['source_revision'],native_product_groups_retained=77,product_rebuilt=False,product_suite_rerun=False,physical_access=False,live_storage_qualified=False,owned_reader_authenticated=False,provider_admitted=False,historical_windows_qualified=False,unit_complete=False,owner_accepted=False,remote_writes=False))
    print('qualification pass',flush=True)
if __name__=='__main__':main()
