"""Clean frozen-inventory Windows renderer qualification and relevant port/model/product regressions."""
import argparse,hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',type=Path,default=Path.cwd());p.add_argument('--source-revision',required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--existing-clone',type=Path);a=p.parse_args()
    assert re.fullmatch('[0-9a-f]{40}',a.source_revision);root=a.repository.absolute();out=a.output.absolute();out.mkdir();logs=out/'logs';logs.mkdir();commands=[]
    def run(name,args,cwd,limit=180):
        args=list(map(str,args));start=time.monotonic();log=logs/(name+'.log')
        try:r=subprocess.run(args,cwd=cwd,capture_output=True,timeout=limit)
        except subprocess.TimeoutExpired as error:
            log.write_bytes((error.stdout or b'')+(error.stderr or b''));commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=None,elapsed_seconds=round(time.monotonic()-start,3),log='logs/'+log.name,error='timeout'));save(out/'commands.json',commands);raise
        log.write_bytes(r.stdout+r.stderr)
        commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=r.returncode,elapsed_seconds=round(time.monotonic()-start,3),log='logs/'+log.name));save(out/'commands.json',commands);print(name+' exit '+str(r.returncode),flush=True)
        if r.returncode:raise RuntimeError(name+' failed '+str(log))
        return r.stdout
    checkout=a.existing_clone.resolve() if a.existing_clone else out/'checkout'
    if a.existing_clone:
        assert checkout.is_relative_to((root/'.aide-local').resolve()) and (checkout/'.git').is_dir()
        origin=run('existing-clone-origin',['git','remote','get-url','origin'],checkout).decode().strip();assert Path(origin).resolve()==root.resolve()
        assert not run('existing-clone-status',['git','status','--porcelain'],checkout,600).strip()
        run('existing-clone-fetch',['git','fetch','--no-tags','origin',a.source_revision],checkout,600)
    else:run('clone',['git','clone','--local','--no-hardlinks','--no-checkout',root,checkout],root,600)
    run('checkout',['git','checkout','--detach',a.source_revision],checkout,600)
    assert not run('source-status',['git','status','--porcelain'],checkout).strip();run('source-map',[sys.executable,'tools/check-source-map.py'],checkout)
    host=json.loads(run('host',['powershell','-NoProfile','-Command','$diskedIdentity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$diskedPrincipal=[System.Security.Principal.WindowsPrincipal]::new($diskedIdentity);$diskedOS=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$diskedIdentity.Name;elevated=$diskedPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$diskedOS.Caption;version=$diskedOS.Version;architecture=$diskedOS.OSArchitecture}|ConvertTo-Json -Compress'],checkout))
    assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
    prior=checkout/'.aide/evidence/2026-10-12-inventory-port/reproduction-2e2f1fb8';product=json.loads((prior/'product-build-identity.json').read_bytes())
    assert set(product['inputs'])==set(json.loads((checkout/'tools/build-inputs.json').read_bytes())['files'])
    product_binding={n:sha(checkout/n) for n in product['inputs']};changed=[n for n in product_binding if product_binding[n]!=product['inputs'][n]];save(out/'prior-product-input-comparison.json',dict(source_revision=a.source_revision,prior_source_revision='2e2f1fb84a21c7f0d92d51e72e8d89e33880ce61',inputs=len(product_binding),changed_inputs=changed,evidence_reused=False))
    inputs=dict(product_binding)
    for folder in ('source/platform/windows/storage','source/providers/windows','source/providers/image','source/runtime/graph','source/runtime/capture','tests/windows','source/portable/hash','source/portable/primitives','source/portable/mbr','source/portable/ebr','source/portable/gpt'):
        for f in (checkout/folder).rglob('*'):
            if f.is_file() and '__pycache__' not in f.parts:inputs[f.relative_to(checkout).as_posix()]=sha(f)
    for n in ('source/platform/windows/worker_files.h','spec/catalog/nt-owned-layout-prototype.json','spec/catalog/nt-composite-identity-prototype.json','spec/catalog/nt-capture-domain-prototype.json','spec/catalog/nt-identity-projection-prototype.json','spec/catalog/nt-identity-adapter-prototype.json','spec/catalog/nt-inventory-port-prototype.json','spec/interaction/presentation.md','spec/storage/identity-and-graph.md','spec/storage/windows.md','docs/source-map.md','tools/check-source-map.py','.aide/evidence/2026-10-12-inventory-advance/reproduce.py','spec/catalog/nt-inventory-frontend-prototype.json','spec/catalog/nt-inventory-advance-prototype.json'):
        inputs[n]=sha(checkout/n)
    save(out/'source-inputs.json',inputs);tree=run('source-tree',['git','ls-tree','-r','-z',a.source_revision],checkout);blobs={}
    for row in tree.split(b'\0'):
        if not row:continue
        header,path=row.split(b'\t',1);name=path.decode('utf-8')
        if name in inputs:
            blob=header.split()[2].decode();data=(checkout/name).read_bytes();assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob,name;blobs[name]=blob
    assert set(blobs)==set(inputs);save(out/'source-blob-bindings.json',blobs)
    cases=[('inventory-advance','nt_inventory_advance_probe','test_inventory_advance.py',None,None,None),('inventory-frontend','nt_inventory_frontend_probe','test_inventory_frontend.py',59,36,916),('inventory-port','nt_inventory_port_probe','test_inventory_port.py',23,88,7503),('identity-frontend','nt_identity_frontend_probe','test_observation_frontend.py',21,46,7185)]
    run('cmake-version',['cmake','--version'],checkout);run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],checkout)
    run('product-configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable],checkout)
    run('product-build',['cmake','--build','--preset','windows-bootstrap','--parallel','4'],checkout,1200)
    catalog=json.loads(run('product-test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1'],checkout));assert len(catalog['tests'])==77
    tests=run('product-native',['ctest','--preset','windows-bootstrap','--parallel','4','--output-on-failure'],checkout,2400);assert b'0 tests failed out of 77' in tests
    product_build=checkout/'build/windows-bootstrap';shutil.copyfile(product_build/'Testing/Temporary/LastTest.log',out/'native-details.log')
    shutil.copyfile(product_build/'Testing/capture-domain-results.json',out/'capture-domain-reducer-results.json');reducer=json.loads((out/'capture-domain-reducer-results.json').read_bytes());assert reducer['tests']==25 and reducer['passed']
    identity=json.loads((product_build/'generated/build-identity.json').read_bytes());assert identity['identity']['source_revision']==a.source_revision and identity['identity']['source_state']=='clean' and identity['inputs']==product_binding;save(out/'product-build-identity.json',identity)
    executable=product_build/'Release/disked.exe';launch=json.loads(run('product-launch',[executable,'build','inspect','--json'],checkout))['result'];assert launch['version']=='0.1.0-dev.41' and launch['source_revision']==a.source_revision
    artifacts=[dict(kind='product',architecture='x64',path=str(executable),bytes=executable.stat().st_size,sha256=sha(executable))];campaigns=[];dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
    product_config=out/'product-build-configuration';product_config.mkdir()
    for n in ('CMakeCache.txt','disked.vcxproj'):shutil.copyfile(product_build/n,product_config/n)
    for f in (product_build/'CMakeFiles').rglob('CMake*Compiler.cmake'):shutil.copyfile(f,product_config/f.name)
    for mode in ('headers','imports','dependents'):run('product-'+mode,[dumpbin,'/'+mode,executable],checkout)
    reducer_probe=product_build/'Release/capture_probe.exe';assert reducer['sha256']==sha(reducer_probe)[7:];artifacts.append(dict(kind='capture-reducer',architecture='x64',path=str(reducer_probe),bytes=reducer_probe.stat().st_size,sha256=sha(reducer_probe)))
    for n in ('capture_probe.vcxproj','disked_presentation.vcxproj'):shutil.copyfile(product_build/n,product_config/n)
    for mode in ('headers','imports','dependents'):run('capture-reducer-'+mode,[dumpbin,'/'+mode,reducer_probe],checkout)
    for arch,pointer in [('x64',8),('Win32',4)]:
        build=out/('build-'+arch);run('configure-'+arch,['cmake','-S',checkout/'tests/windows/native','-B',build,'-G','Visual Studio 17 2022','-A',arch+',version=10.0.19041.0','-T','v143,version=14.44.35207,host=x64','-DCMAKE_SYSTEM_VERSION=10.0.19041.0'],checkout)
        run('build-'+arch,['cmake','--build',build,'--config','Release','--target',*[x[1] for x in cases],'--parallel','4'],checkout,600)
        config=out/('build-configuration-'+arch);config.mkdir();shutil.copyfile(build/'CMakeCache.txt',config/'CMakeCache.txt')
        for f in (build/'CMakeFiles').rglob('CMake*Compiler.cmake'):shutil.copyfile(f,config/f.name)
        for name,target,script,wanted_controllers,wanted_children,wanted_assertions in cases:
            probe=build/('Release/'+target+'.exe');campaign=out/(name+'-'+arch);extra=['--storage-profile','identity-layout'] if name=='identity-frontend' else []
            run(name+'-'+arch,[sys.executable,checkout/('tests/windows/'+script),'--probe',probe,'--output',campaign,'--pointer-bytes',pointer,*extra],checkout,360)
            result=json.loads((campaign/'results.json').read_bytes());assert result['status']=='pass' and result['pointer_bytes']==pointer and all(x['passed'] for x in result.get('checks',[])) and result['assertions']>0
            controllers=result.get('controller_executions',result.get('native_executions',result.get('processes',result.get('executions'))));controllers=len(controllers) if isinstance(controllers,list) else controllers
            children=result.get('actual_child_launches',0);assertions=result['assertions']
            if wanted_controllers is not None:assert (controllers,children,assertions)==(wanted_controllers,wanted_children,wanted_assertions),(name,controllers,children,assertions)
            campaigns.append(dict(kind=name,architecture=arch,controllers=controllers,child_launches=children,assertions=assertions,pointer_bytes=pointer));save(out/'campaigns.json',campaigns)
            for mode in ('headers','imports','dependents'):run(name+'-'+mode+'-'+arch,[dumpbin,'/'+mode,probe],checkout)
            shutil.copyfile(build/(target+'.vcxproj'),config/(target+'.vcxproj'));artifacts.append(dict(kind=name,path=str(probe),architecture=arch,bytes=probe.stat().st_size,sha256=sha(probe)))
    run('tooling-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],checkout,300);log=(logs/'tooling-tests.log').read_text(encoding='utf-8');ran=re.search(r'^Ran (\d+) tests? in ',log,re.MULTILINE);passed=re.search(r'^OK(?: \(skipped=(\d+)\))?$',log,re.MULTILINE);assert ran and passed;count=int(ran.group(1));skip=int(passed.group(1) or 0)
    check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check'],checkout));run('index-freshness',[sys.executable,'spec/tools/specctl.py','index','--check'],checkout)
    run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W030','--output',out/'context','--byte-budget','680000'],checkout);run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context',out/'context'],checkout);run('verify-manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest'],checkout)
    assert not run('final-source-status',['git','status','--porcelain'],checkout).strip();assert all(sha(checkout/n)==d for n,d in inputs.items())
    summary=dict(status='pass',source_revision=a.source_revision,host=host,source_inputs=len(inputs),campaigns=campaigns,artifacts=artifacts,tooling_tests=dict(run=count,passed=count-skip,skipped=skip),structural_checks=check['checks'],product_inputs=len(product_binding),product_version=launch['version'],product_source_revision=a.source_revision,product_build_directory=str(product_build),native_ctest_groups=77,product_rebuilt=True,product_suite_rerun=True,live_storage_qualified=False,physical_association='unproven',source_consistency='live-uncoordinated',provider_admitted=False,public_protocol_admitted=False,private_composite_observation_qualified=True,capture_domain_guards_qualified=True,private_identity_projection_qualified=True,private_identity_adapter_qualified=True,private_inventory_port_qualified=True,private_inventory_frontend_qualified=True,private_inventory_advance_qualified=True,native_renderer_scope='Injected serialized application advancement in owned GUI, TUI and linear shell; exact stale reviews, preserved editors/candidates, partial/cancel/late/timeout/startup-error/teardown evidence; separate frozen/port/model regressions, no accessibility or shipped-product/live admission',current_resource_freshness='unknown',historical_windows_qualified=False,owner_accepted=False,unit_complete=False)
    save(out/'results.json',summary);print(json.dumps(dict(status='pass',campaigns=len(campaigns),source_inputs=len(inputs))),flush=True)

if __name__=='__main__':main()
