"""Clean source-bound Owned ID/layout frames and every existing private Windows regression."""
import argparse,hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',type=Path,default=Path.cwd())
    p.add_argument('--source-revision',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert re.fullmatch('[0-9a-f]{40}',a.source_revision)
    root=a.repository.absolute();out=a.output.absolute();out.mkdir();logs=out/'logs';logs.mkdir();commands=[]
    def run(name,args,cwd,limit=180):
        args=list(map(str,args));start=time.monotonic();r=subprocess.run(args,cwd=cwd,capture_output=True,timeout=limit)
        log=logs/(name+'.log');log.write_bytes(r.stdout+r.stderr)
        commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=r.returncode,elapsed_seconds=round(time.monotonic()-start,3),log='logs/'+log.name))
        save(out/'commands.json',commands);print(name+' exit '+str(r.returncode),flush=True)
        if r.returncode:raise RuntimeError(name+' failed '+str(log))
        return r.stdout
    checkout=out/'checkout';run('clone',['git','clone','--local','--no-hardlinks','--no-checkout',root,checkout],root)
    run('checkout',['git','checkout','--detach',a.source_revision],checkout)
    assert not run('source-status',['git','status','--porcelain'],checkout).strip()
    run('source-map',[sys.executable,'tools/check-source-map.py'],checkout)
    host=json.loads(run('host',['powershell','-NoProfile','-Command','$diskedIdentity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$diskedPrincipal=[System.Security.Principal.WindowsPrincipal]::new($diskedIdentity);$diskedOS=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$diskedIdentity.Name;elevated=$diskedPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$diskedOS.Caption;version=$diskedOS.Version;architecture=$diskedOS.OSArchitecture}|ConvertTo-Json -Compress'],checkout))
    assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
    prior='8f55d8671a4c8ef936195cf68fa1f601db7eeed7'
    product_identity_path='.aide/evidence/2026-10-10-observation-frontend/reproduction-8f55d867/product-build-identity.json'
    prior_identity=json.loads((checkout/product_identity_path).read_bytes());product_inputs=prior_identity['inputs']
    assert prior_identity['identity']['source_revision']==prior
    assert set(product_inputs)==set(json.loads((checkout/'tools/build-inputs.json').read_bytes())['files'])
    assert all(sha(checkout/n)==d for n,d in product_inputs.items())
    save(out/'unchanged-product-inputs.json',dict(prior_source=prior,inputs=product_inputs,product_rebuilt=False,product_suite_rerun=False))
    inputs=dict(product_inputs)
    for folder in ('source/platform/windows/storage','source/providers/windows','source/runtime/graph','tests/windows','source/portable/hash'):
        for f in (checkout/folder).rglob('*'):
            if f.is_file():inputs[f.relative_to(checkout).as_posix()]=sha(f)
    for n in ('source/runtime/command/json.cpp','source/runtime/command/json.h','source/providers/image/local_file.cpp','source/providers/image/local_file.h',
              'source/platform/windows/worker_files.h','spec/catalog/nt-storage-observation-prototype.json','spec/catalog/nt-storage-worker-prototype.json',
              'spec/catalog/nt-namespace-worker-prototype.json','spec/catalog/observation-frontend-prototype.json','spec/catalog/nt-identity-layout-prototype.json','spec/catalog/nt-identity-frame-prototype.json',
              '.aide/evidence/2026-10-10-identity-queries/reproduction-b853621b/storage-worker-x64/healthy.stdout',
              'spec/storage/windows.md','spec/operations/inventory.md','docs/source-map.md','tools/check-source-map.py',product_identity_path,
              '.aide/evidence/2026-10-10-identity-frame/reproduce.py'):
        inputs[n]=sha(checkout/n)
    names=list(inputs);queries=''.join(a.source_revision+':'+n+'\n' for n in names).encode()
    blobs=subprocess.check_output(['git','cat-file','--batch'],input=queries,cwd=checkout);cursor=0
    for n in names:
        line=blobs.index(b'\n',cursor);header=blobs[cursor:line].split();assert header[1]==b'blob'
        size=int(header[2]);start=line+1;data=blobs[start:start+size];cursor=start+size+1
        assert 'sha256:'+hashlib.sha256(data).hexdigest()==inputs[n],n
    assert cursor==len(blobs)
    assert sha(Path(__file__).absolute())==inputs['.aide/evidence/2026-10-10-identity-frame/reproduce.py']
    save(out/'source-inputs.json',inputs)
    run('cmake-version',['cmake','--version'],checkout)
    run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],checkout)
    dumpbin=Path(prior_identity['compiler_path']).with_name('dumpbin.exe');campaigns=[];artifacts=[]
    cases=[('identity-frame','nt_identity_frame_probe','test_identity_frame.py',54,41,6980),
           ('identity-queries','nt_identity_query_probe','test_identity_queries.py',57,0,197),
           ('storage-queries','nt_storage_query_probe','test_storage_queries.py',70,0,1987),
           ('storage-worker','nt_storage_worker_probe','test_storage_worker.py',43,35,671),
           ('observation-frontend','nt_observation_frontend_probe','test_observation_frontend.py',15,26,1300),
           ('namespace-graph','nt_namespace_graph_probe','test_namespace_graph.py',30,26,1103),
           ('namespace-worker','nt_namespace_worker_probe','test_namespace_worker.py',24,18,116),
           ('capture-lifecycle','nt_capture_lifecycle_probe','test_capture_lifecycle.py',6,6,105),
           ('volume-adapter','nt_volume_namespace_probe','test_volume_namespace.py',49,0,258)]
    for arch,pointer in [('x64',8),('Win32',4)]:
        build=out/('build-'+arch)
        run('configure-'+arch,['cmake','-S',checkout/'tests/windows/native','-B',build,'-G','Visual Studio 17 2022','-A',arch+',version=10.0.19041.0','-T','v143,version=14.44.35207,host=x64','-DCMAKE_SYSTEM_VERSION=10.0.19041.0'],checkout)
        run('build-'+arch,['cmake','--build',build,'--config','Release','--target']+[c[1] for c in cases]+['--parallel','4'],checkout,600)
        config=out/('build-configuration-'+arch);config.mkdir();shutil.copyfile(build/'CMakeCache.txt',config/'CMakeCache.txt')
        for f in (build/'CMakeFiles').rglob('CMake*Compiler.cmake'):shutil.copyfile(f,config/f.name)
        for kind,target,script,controllers,children,assertions in cases:
            probe=build/('Release/'+target+'.exe');campaign=out/(kind+'-'+arch)
            run(kind+'-'+arch,[sys.executable,checkout/('tests/windows/'+script),'--probe',probe,'--output',campaign,'--pointer-bytes',pointer],checkout,300)
            result=json.loads((campaign/'results.json').read_bytes())
            assert result['status']=='pass' and result['pointer_bytes']==pointer and result['assertions']==assertions
            observed=result.get('controller_executions',result.get('native_executions',result.get('executions')))
            if isinstance(observed,list):observed=len(observed)
            assert observed==controllers,(kind,observed);assert result.get('actual_child_launches',0)==children
            campaigns.append(dict(kind=kind,architecture=arch,controllers=controllers,child_launches=children,assertions=assertions,pointer_bytes=pointer))
            for mode in ('headers','imports','dependents'):run(kind+'-'+mode+'-'+arch,[dumpbin,'/'+mode,probe],checkout)
            shutil.copyfile(build/(target+'.vcxproj'),config/(target+'.vcxproj'))
            artifacts.append(dict(kind=kind,path=str(probe),architecture=arch,bytes=probe.stat().st_size,sha256=sha(probe)))
    run('tooling-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],checkout,600)
    log=(logs/'tooling-tests.log').read_text(encoding='utf-8')
    ran=re.search(r'^Ran (\d+) tests? in ',log,re.MULTILINE);passed=re.search(r'^OK(?: \(skipped=(\d+)\))?$',log,re.MULTILINE);assert ran and passed
    count=int(ran.group(1));skip=int(passed.group(1) or 0)
    check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check'],checkout))
    run('index-freshness',[sys.executable,'spec/tools/specctl.py','index','--check'],checkout)
    run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W030','--output',out/'context','--byte-budget','680000'],checkout)
    run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context',out/'context'],checkout)
    run('verify-manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest'],checkout)
    assert not run('final-source-status',['git','status','--porcelain'],checkout).strip()
    assert all(sha(checkout/n)==d for n,d in inputs.items())
    summary=dict(status='pass',source_revision=a.source_revision,host=host,source_inputs=len(inputs),campaigns=campaigns,artifacts=artifacts,
        tooling_tests=dict(run=count,passed=count-skip,skipped=skip),structural_checks=check['checks'],
        prior_product_source=prior,unchanged_product_inputs=len(product_inputs),product_rebuilt=False,product_suite_rerun=False,
        identity_layout_fixture_qualified=True,owned_identity_fixture_qualified=True,raw_metadata_independently_verified=False,
        live_storage_qualified=False,physical_access=False,provider_admitted=False,historical_windows_qualified=False,
        unit_complete=False,owner_accepted=False,remote_writes=False)
    save(out/'results.json',summary);print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
