"""Clean exact-source cached observation frontend, source-ownership migration and product regression qualification."""
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
    run('source-map',[sys.executable,'tools/check-source-map.py'],checkout)
    host=json.loads(run('host',['powershell','-NoProfile','-Command','$diskedIdentity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$diskedPrincipal=[System.Security.Principal.WindowsPrincipal]::new($diskedIdentity);$diskedOS=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$diskedIdentity.Name;elevated=$diskedPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$diskedOS.Caption;version=$diskedOS.Version;architecture=$diskedOS.OSArchitecture}|ConvertTo-Json -Compress'],checkout))
    assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated'];inputs={}
    inputs={n:sha(checkout/n) for n in json.loads((checkout/'tools/build-inputs.json').read_bytes())['files']}
    for folder in ('source/platform/windows/storage','source/providers/windows','source/runtime/graph','tests/windows','source/portable/hash'):
        for f in (checkout/folder).rglob('*'):
            if f.is_file():inputs[f.relative_to(checkout).as_posix()]=sha(f)
    for n in ('source/runtime/command/json.cpp','source/runtime/command/json.h','source/providers/image/local_file.cpp','source/providers/image/local_file.h','spec/catalog/nt-storage-observation-prototype.json','spec/catalog/nt-storage-worker-prototype.json','spec/catalog/nt-namespace-worker-prototype.json','source/platform/windows/worker_files.h',
              'spec/storage/windows.md','spec/operations/inventory.md','spec/catalog/observation-frontend-prototype.json','docs/source-map.md','spec/architecture/repository.md','tools/check-source-map.py','.aide/evidence/2026-10-10-observation-frontend/reproduce.py'):
        inputs[n]=sha(checkout/n)
    # Batch exact Git blobs: compare hashes against checkout bytes without a
    # separate Git subprocess for every source file.
    names=list(inputs);queries=''.join(a.source_revision+':'+n+'\n' for n in names).encode()
    blobs=subprocess.check_output(['git','cat-file','--batch'],input=queries,cwd=checkout)
    cursor=0
    for n in names:
        line=blobs.index(b'\n',cursor);header=blobs[cursor:line].split();assert header[1]==b'blob'
        size=int(header[2]);start=line+1;data=blobs[start:start+size];cursor=start+size+1
        assert 'sha256:'+hashlib.sha256(data).hexdigest()==inputs[n],n
    assert cursor==len(blobs)
    assert sha(Path(__file__).absolute())==inputs['.aide/evidence/2026-10-10-observation-frontend/reproduce.py'];save(out/'source-inputs.json',inputs)
    run('cmake-version',['cmake','--version'],checkout);run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],checkout)
    run('product-configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable],checkout)
    run('product-build',['cmake','--build','--preset','windows-bootstrap','--parallel','4'],checkout,1200)
    catalog=json.loads(run('product-test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1'],checkout));assert len(catalog['tests'])==77
    tests=run('product-native',['ctest','--preset','windows-bootstrap','--output-on-failure'],checkout,2400)
    assert b'0 tests failed out of 77' in tests
    shutil.copyfile(checkout/'build/windows-bootstrap/Testing/Temporary/LastTest.log',out/'native-details.log')
    identity=json.loads((checkout/'build/windows-bootstrap/generated/build-identity.json').read_bytes());save(out/'product-build-identity.json',identity)
    assert identity['identity']['source_revision']==a.source_revision and identity['identity']['source_state']=='clean'
    assert all(sha(checkout/n)==d for n,d in identity['inputs'].items())
    product=checkout/'build/windows-bootstrap/Release/disked.exe'
    launch=json.loads(run('product-launch',[product,'build','inspect','--json'],checkout))['result']
    assert launch['version']=='0.1.0-dev.39' and launch['source_revision']==a.source_revision
    artifacts=[dict(kind='product',architecture='x64',path=str(product),bytes=product.stat().st_size,sha256=sha(product))]
    product_config=out/'product-build-configuration';product_config.mkdir()
    product_build=checkout/'build/windows-bootstrap'
    for n in ('CMakeCache.txt','disked.vcxproj'):shutil.copyfile(product_build/n,product_config/n)
    for f in (product_build/'CMakeFiles').rglob('CMake*Compiler.cmake'):shutil.copyfile(f,product_config/f.name)
    campaigns=[];dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
    for mode in ('headers','imports','dependents'):run('product-'+mode,[dumpbin,'/'+mode,product],checkout)
    cases=[('observation-frontend','nt_observation_frontend_probe','test_observation_frontend.py',15,26,1300),
           ('storage-worker','nt_storage_worker_probe','test_storage_worker.py',43,35,671),
           ('namespace-graph','nt_namespace_graph_probe','test_namespace_graph.py',30,26,1103),
           ('namespace-worker','nt_namespace_worker_probe','test_namespace_worker.py',24,18,116),
           ('capture-lifecycle','nt_capture_lifecycle_probe','test_capture_lifecycle.py',6,6,105),
           ('storage-queries','nt_storage_query_probe','test_storage_queries.py',70,0,1987),
           ('volume-adapter','nt_volume_namespace_probe','test_volume_namespace.py',49,0,258)]
    for arch,pointer in [('x64',8),('Win32',4)]:
        build=out/('build-'+arch);run('configure-'+arch,['cmake','-S',checkout/'tests/windows/native','-B',build,'-G','Visual Studio 17 2022','-A',arch+',version=10.0.19041.0','-T','v143,version=14.44.35207,host=x64','-DCMAKE_SYSTEM_VERSION=10.0.19041.0'],checkout)
        run('build-'+arch,['cmake','--build',build,'--config','Release','--parallel','4'],checkout,600)
        config=out/('build-configuration-'+arch);config.mkdir();shutil.copyfile(build/'CMakeCache.txt',config/'CMakeCache.txt')
        for f in (build/'CMakeFiles').rglob('CMake*Compiler.cmake'):shutil.copyfile(f,config/f.name)
        for kind,target,script,controllers,children,assertions in cases:
            probe=build/('Release/'+target+'.exe');campaign=out/(kind+'-'+arch)
            run(kind+'-'+arch,[sys.executable,checkout/('tests/windows/'+script),'--probe',probe,'--output',campaign,'--pointer-bytes',pointer],checkout)
            result=json.loads((campaign/'results.json').read_bytes());assert result['status']=='pass' and result['pointer_bytes']==pointer and result['assertions']==assertions
            observed_controllers=result.get('controller_executions',result.get('native_executions',result.get('executions')))
            if isinstance(observed_controllers,list):observed_controllers=len(observed_controllers)
            assert observed_controllers==controllers,(kind,observed_controllers)
            assert result.get('actual_child_launches',0)==children
            campaigns.append(dict(kind=kind,architecture=arch,controllers=controllers,child_launches=children,assertions=assertions,pointer_bytes=pointer))
            for mode in ('headers','imports','dependents'):run(kind+'-'+mode+'-'+arch,[dumpbin,'/'+mode,probe],checkout)
            shutil.copyfile(build/(target+'.vcxproj'),config/(target+'.vcxproj'))
            artifacts.append(dict(kind=kind,path=str(probe),architecture=arch,bytes=probe.stat().st_size,sha256=sha(probe)))
    run('tooling-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],checkout,300)
    log=(logs/'tooling-tests.log').read_text(encoding='utf-8');ran=re.search(r'^Ran (\d+) tests? in ',log,re.MULTILINE);passed=re.search(r'^OK(?: \(skipped=(\d+)\))?$',log,re.MULTILINE);assert ran and passed
    count=int(ran.group(1));skip=int(passed.group(1) or 0);check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check'],checkout))
    run('index-freshness',[sys.executable,'spec/tools/specctl.py','index','--check'],checkout)
    run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W030','--output',out/'context','--byte-budget','620000'],checkout)
    run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context',out/'context'],checkout);run('verify-manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest'],checkout)
    assert not run('final-source-status',['git','status','--porcelain'],checkout).strip();assert all(sha(checkout/n)==d for n,d in inputs.items())
    summary=dict(status='pass',source_revision=a.source_revision,host=host,source_inputs=len(inputs),campaigns=campaigns,artifacts=artifacts,tooling_tests=dict(run=count,passed=count-skip,skipped=skip),structural_checks=check['checks'],
        product_inputs=len(identity['inputs']),product_version=launch['version'],native_ctest_groups=77,product_rebuilt=True,product_suite_rerun=True,live_storage_qualified=False,physical_access=False,owned_injected_reader_qualified=True,cached_frontend_model_qualified=True,actual_window_terminal_qualified=False,live_worker_qualified=False,provider_admitted=False,historical_windows_qualified=False,unit_complete=False,owner_accepted=False,remote_writes=False)
    save(out/'results.json',summary);print(json.dumps(summary),flush=True)

if __name__=='__main__':main()
