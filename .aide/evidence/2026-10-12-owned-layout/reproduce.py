"""Clean owned image/layout provenance campaign and shared Windows reader regressions."""
import argparse,hashlib,json,re,shutil,subprocess,sys,time
from pathlib import Path

def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--repository',type=Path,default=Path.cwd());p.add_argument('--source-revision',required=True);p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    assert re.fullmatch('[0-9a-f]{40}',a.source_revision);root=a.repository.absolute();out=a.output.absolute();out.mkdir();logs=out/'logs';logs.mkdir();commands=[]
    def run(name,args,cwd,limit=180):
        args=list(map(str,args));start=time.monotonic();r=subprocess.run(args,cwd=cwd,capture_output=True,timeout=limit);log=logs/(name+'.log');log.write_bytes(r.stdout+r.stderr)
        commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=r.returncode,elapsed_seconds=round(time.monotonic()-start,3),log='logs/'+log.name));save(out/'commands.json',commands);print(name+' exit '+str(r.returncode),flush=True)
        if r.returncode:raise RuntimeError(name+' failed '+str(log))
        return r.stdout
    checkout=out/'checkout';run('clone',['git','clone','--local','--no-hardlinks','--no-checkout',root,checkout],root);run('checkout',['git','checkout','--detach',a.source_revision],checkout)
    assert not run('source-status',['git','status','--porcelain'],checkout).strip();run('source-map',[sys.executable,'tools/check-source-map.py'],checkout)
    host=json.loads(run('host',['powershell','-NoProfile','-Command','$diskedIdentity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$diskedPrincipal=[System.Security.Principal.WindowsPrincipal]::new($diskedIdentity);$diskedOS=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$diskedIdentity.Name;elevated=$diskedPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$diskedOS.Caption;version=$diskedOS.Version;architecture=$diskedOS.OSArchitecture}|ConvertTo-Json -Compress'],checkout))
    assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
    prior=checkout/'.aide/evidence/2026-10-10-identity-frontend/reproduction-829de03c';product=json.loads((prior/'product-build-identity.json').read_bytes())
    assert set(product['inputs'])==set(json.loads((checkout/'tools/build-inputs.json').read_bytes())['files'])
    product_binding={n:sha(checkout/n) for n in product['inputs']};assert product_binding==product['inputs'];save(out/'product-input-reuse.json',dict(source_revision=a.source_revision,evidence_source_revision='829de03cd8652323d7ab8b6f6828a5e410a0b594',exact_inputs=product_binding,product_rebuilt=False,product_suite_rerun=False,native_ctest_groups_reused=77))
    inputs=dict(product_binding)
    for folder in ('source/platform/windows/storage','source/providers/windows','source/providers/image','source/runtime/graph','source/runtime/capture','tests/windows','source/portable/hash','source/portable/primitives','source/portable/mbr','source/portable/ebr','source/portable/gpt'):
        for f in (checkout/folder).rglob('*'):
            if f.is_file():inputs[f.relative_to(checkout).as_posix()]=sha(f)
    for n in ('source/platform/windows/worker_files.h','spec/catalog/nt-owned-layout-prototype.json','spec/storage/windows.md','docs/source-map.md','tools/check-source-map.py','.aide/evidence/2026-10-12-owned-layout/reproduce.py'):
        inputs[n]=sha(checkout/n)
    save(out/'source-inputs.json',inputs);tree=run('source-tree',['git','ls-tree','-r','-z',a.source_revision],checkout);blobs={}
    for row in tree.split(b'\0'):
        if not row:continue
        header,path=row.split(b'\t',1);name=path.decode('utf-8')
        if name in inputs:
            blob=header.split()[2].decode();data=(checkout/name).read_bytes();assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob,name;blobs[name]=blob
    assert set(blobs)==set(inputs);save(out/'source-blob-bindings.json',blobs)
    cases=[('owned-layout','nt_owned_layout_probe','test_owned_layout.py',78,102,1365),('namespace-worker','nt_namespace_worker_probe','test_namespace_worker.py',None,None,None),('namespace-graph','nt_namespace_graph_probe','test_namespace_graph.py',None,None,None),('capture-lifecycle','nt_capture_lifecycle_probe','test_capture_lifecycle.py',None,None,None),('storage-worker','nt_storage_worker_probe','test_storage_worker.py',43,35,671),('identity-frame','nt_identity_frame_probe','test_identity_frame.py',54,41,6980),('observation-frontend','nt_observation_frontend_probe','test_observation_frontend.py',16,26,1339),('identity-frontend','nt_identity_frontend_probe','test_observation_frontend.py',21,46,7185),('raw-layout','nt_raw_layout_probe','test_raw_layout.py',109,0,1342)]
    artifacts=[];campaigns=[];dumpbin=Path(product['compiler_path']).with_name('dumpbin.exe')
    for arch,pointer in [('x64',8),('Win32',4)]:
        build=out/('build-'+arch);run('configure-'+arch,['cmake','-S',checkout/'tests/windows/native','-B',build,'-G','Visual Studio 17 2022','-A',arch+',version=10.0.19041.0','-T','v143,version=14.44.35207,host=x64','-DCMAKE_SYSTEM_VERSION=10.0.19041.0'],checkout)
        run('build-'+arch,['cmake','--build',build,'--config','Release','--target',*[x[1] for x in cases],'--parallel','4'],checkout,600)
        config=out/('build-configuration-'+arch);config.mkdir();shutil.copyfile(build/'CMakeCache.txt',config/'CMakeCache.txt')
        for f in (build/'CMakeFiles').rglob('CMake*Compiler.cmake'):shutil.copyfile(f,config/f.name)
        for name,target,script,wanted_controllers,wanted_children,wanted_assertions in cases:
            probe=build/('Release/'+target+'.exe');campaign=out/(name+'-'+arch);extra=['--storage-profile','identity-layout'] if name=='identity-frontend' else []
            run(name+'-'+arch,[sys.executable,checkout/('tests/windows/'+script),'--probe',probe,'--output',campaign,'--pointer-bytes',pointer,*extra],checkout,240)
            result=json.loads((campaign/'results.json').read_bytes());assert result['status']=='pass' and result['pointer_bytes']==pointer and all(x['passed'] for x in result['checks'])
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
    summary=dict(status='pass',source_revision=a.source_revision,host=host,source_inputs=len(inputs),campaigns=campaigns,artifacts=artifacts,tooling_tests=dict(run=count,passed=count-skip,skipped=skip),structural_checks=check['checks'],product_inputs_reused=len(product_binding),product_evidence_source_revision='829de03cd8652323d7ab8b6f6828a5e410a0b594',product_rebuilt=False,product_suite_rerun=False,live_storage_qualified=False,physical_association='unproven',source_consistency='live-uncoordinated',provider_admitted=False,public_protocol_admitted=False,historical_windows_qualified=False,owner_accepted=False,unit_complete=False)
    save(out/'results.json',summary);print(json.dumps(dict(status='pass',campaigns=len(campaigns),source_inputs=len(inputs))),flush=True)

if __name__=='__main__':main()
