"""Clean local capture-publication qualification and full selected product regression.
No live namespace, physical access, elevation, installation or network writes.
"""
import argparse
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys
import time


def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def save(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repository',type=Path,default=Path.cwd());p.add_argument('--source-revision',required=True)
    p.add_argument('--output',type=Path,required=True);a=p.parse_args()
    root=a.repository.absolute();out=a.output.absolute();out.mkdir();logs=out/'logs';logs.mkdir();commands=[]
    def run(name,args,cwd,limit=120):
        args=list(map(str,args));start=time.monotonic();r=subprocess.run(args,cwd=cwd,capture_output=True,timeout=limit)
        log=logs/(name+'.log');log.write_bytes(r.stdout+r.stderr)
        commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=r.returncode,elapsed_seconds=round(time.monotonic()-start,3),log='logs/'+log.name))
        save(out/'commands.json',commands);print(name+' exit '+str(r.returncode),flush=True)
        if r.returncode:raise RuntimeError(name+' failed: '+str(log))
        return r.stdout
    checkout=out/'checkout'
    run('clone',['git','clone','--local','--no-hardlinks','--no-checkout',root,checkout],root)
    run('checkout',['git','checkout','--detach',a.source_revision],checkout)
    assert not run('source-status',['git','status','--porcelain'],checkout).strip()
    host=json.loads(run('host',['powershell','-NoProfile','-Command',
        '$diskedIdentity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$diskedPrincipal=[System.Security.Principal.WindowsPrincipal]::new($diskedIdentity);$diskedOS=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$diskedIdentity.Name;elevated=$diskedPrincipal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$diskedOS.Caption;version=$diskedOS.Version;build=$diskedOS.BuildNumber;architecture=$diskedOS.OSArchitecture}|ConvertTo-Json -Compress'],checkout))
    assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
    inputs={n:sha(checkout/n) for n in json.loads((checkout/'tools/build-inputs.json').read_bytes())['files']}
    for folder in ('source/platform/windows/storage','source/providers/windows','tests/windows'):
        for f in sorted((checkout/folder).rglob('*')):
            if f.is_file():inputs[f.relative_to(checkout).as_posix()]=sha(f)
    for n in ('spec/catalog/nt-volume-namespace-prototype.json','spec/catalog/nt-namespace-worker-prototype.json',
              '.aide/evidence/2026-10-10-capture-publication/reproduce.py','spec/safety/degraded-operation.md'):
        inputs[n]=sha(checkout/n)
    for n,value in inputs.items():assert 'sha256:'+hashlib.sha256(subprocess.check_output(['git','show',a.source_revision+':'+n],cwd=checkout)).hexdigest()==value,n
    assert sha(Path(__file__).absolute())==inputs['.aide/evidence/2026-10-10-capture-publication/reproduce.py']
    save(out/'source-inputs.json',inputs)
    run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],checkout)
    run('cmake-version',['cmake','--version'],checkout)
    run('product-configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable],checkout)
    run('product-build',['cmake','--build','--preset','windows-bootstrap','--parallel','4'],checkout,900)
    product=checkout/'build/windows-bootstrap/Release';catalog=json.loads(run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1'],checkout))
    assert len(catalog['tests'])==77 and 'resilience.capture' in [x['name'] for x in catalog['tests']]
    result=run('product-native',['ctest','--preset','windows-bootstrap','--output-on-failure'],checkout,1800)
    assert b'0 tests failed out of 77' in result
    shutil.copyfile(checkout/'build/windows-bootstrap/Testing/Temporary/LastTest.log',out/'native-details.log')
    run('capture-reducer',[sys.executable,checkout/'tests/resilience/test_capture.py','--probe',product/'capture_probe.exe','--evidence',out/'capture-reducer.json'],checkout,120)
    reducer=json.loads((out/'capture-reducer.json').read_bytes());assert reducer['passed'] and reducer['tests']==16
    identity=json.loads((checkout/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
    assert identity['identity']['source_revision']==a.source_revision and identity['identity']['source_state']=='clean'
    assert all(sha(checkout/n)==value for n,value in identity['inputs'].items())
    save(out/'product-build-identity.json',identity)
    launch=json.loads(run('product-launch',[product/'disked.exe','build','inspect','--json'],checkout))['result']
    assert launch['version']=='0.1.0-dev.37' and launch['source_revision']==a.source_revision
    artifacts=[dict(kind='product',architecture='x64',path=str(product/'disked.exe'),bytes=(product/'disked.exe').stat().st_size,sha256=sha(product/'disked.exe')),
               dict(kind='capture-reducer',architecture='x64',path=str(product/'capture_probe.exe'),bytes=(product/'capture_probe.exe').stat().st_size,sha256=sha(product/'capture_probe.exe'))]
    dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe');campaigns=[]
    for arch,pointer in [('x64',8),('Win32',4)]:
        build=out/('build-'+arch)
        run('private-configure-'+arch,['cmake','-S',checkout/'tests/windows/native','-B',build,'-G','Visual Studio 17 2022','-A',arch+',version=10.0.19041.0','-T','v143,version=14.44.35207,host=x64','-DCMAKE_SYSTEM_VERSION=10.0.19041.0'],checkout)
        run('private-build-'+arch,['cmake','--build',build,'--config','Release','--parallel','4'],checkout,300)
        for kind,name,script in [('lifecycle','nt_capture_lifecycle_probe','test_capture_lifecycle.py'),('worker','nt_namespace_worker_probe','test_namespace_worker.py')]:
            binary=build/('Release/'+name+'.exe');e=out/(kind+'-'+arch)
            run(kind+'-'+arch,[sys.executable,checkout/('tests/windows/'+script),'--probe',binary,'--output',e,'--pointer-bytes',str(pointer)],checkout,120)
            v=json.loads((e/'results.json').read_bytes());assert v['status']=='pass' and v['pointer_bytes']==pointer
            assert v['controller_executions']==(6 if kind=='lifecycle' else 24) and v['actual_child_launches']==(6 if kind=='lifecycle' else 18)
            campaigns.append(dict(kind=kind,architecture=arch,controllers=v['controller_executions'],child_launches=v['actual_child_launches'],assertions=v['assertions']))
            artifacts.append(dict(kind=kind,architecture=arch,path=str(binary),bytes=binary.stat().st_size,sha256=sha(binary)))
        config=out/('build-configuration-'+arch);config.mkdir()
        for n in ('CMakeCache.txt','nt_capture_lifecycle_probe.vcxproj','nt_namespace_worker_probe.vcxproj'):shutil.copyfile(build/n,config/n)
        for f in (build/'CMakeFiles').rglob('CMake*Compiler.cmake'):shutil.copyfile(f,config/f.name)
    for artifact in artifacts:
        for mode in ('headers','imports','dependents'):run(artifact['kind']+'-'+artifact['architecture']+'-'+mode,[dumpbin,'/'+mode,artifact['path']],checkout)
    run('tooling-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],checkout,300)
    text=(logs/'tooling-tests.log').read_text(encoding='utf-8');ran=re.search(r'^Ran (\d+) tests? in ',text,re.MULTILINE);ok=re.search(r'^OK(?: \(skipped=(\d+)\))?$',text,re.MULTILINE);assert ran and ok
    n=int(ran.group(1));skip=int(ok.group(1) or 0)
    check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check'],checkout));run('index-freshness',[sys.executable,'spec/tools/specctl.py','index','--check'],checkout)
    run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W030','--output',out/'context','--byte-budget','530000'],checkout)
    run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context',out/'context'],checkout)
    run('verify-manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest'],checkout)
    assert not run('final-source-status',['git','status','--porcelain'],checkout).strip()
    assert all(sha(checkout/n)==value for n,value in inputs.items())
    result=dict(status='pass',source_revision=a.source_revision,host=host,observed_at=datetime.now(timezone.utc).isoformat(),source_inputs=len(inputs),product_inputs=len(identity['inputs']),
        product_version=launch['version'],native_ctest_groups=77,reducer_tests=reducer['tests'],campaigns=campaigns,artifacts=artifacts,
        tooling_tests=dict(run=n,passed=n-skip,skipped=skip),structural_checks=check['checks'],namespace_graph_projection_qualified=False,live_namespace_qualified=False,
        physical_access=False,provider_admitted=False,historical_windows_qualified=False,unit_complete=False,owner_accepted=False,remote_writes=False)
    save(out/'results.json',result);print(json.dumps(result),flush=True)


if __name__=='__main__':main()
