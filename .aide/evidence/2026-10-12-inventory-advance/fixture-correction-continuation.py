"""Finish exact-source qualification, with the fixture-only correction bound separately."""
import argparse, hashlib, importlib.util, json, re, shutil, subprocess, sys, textwrap, time
from pathlib import Path

root=Path.cwd();source='6e4c20591afb31389b95afe91dfc4037cde2a4e4';fixed='8cf67f0db2b3d0a507f1ce578dded86f3a1272f9'
out=root/'.aide-local/inventory-advance-clean-6e4c2059';checkout=root/'.aide-local/owned-layout-clean-2c731a1c/checkout'
corrected=root/'.aide-local/inventory-port-release-8cf67f0d/checkout';fix=out/'port-release-correction-8cf67f0d';fix.mkdir()
recipe=root/'.aide/evidence/2026-10-12-inventory-advance/reproduce.py';logs=out/'logs'
spec=importlib.util.spec_from_file_location('bound_recipe',recipe);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout).decode().strip()==source
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=corrected).decode().strip()==fixed
assert not subprocess.check_output(['git','status','--porcelain'],cwd=checkout).strip()
assert not subprocess.check_output(['git','status','--porcelain'],cwd=corrected).strip()
inputs=json.loads((out/'source-inputs.json').read_bytes());assert all(module.sha(checkout/n)==d for n,d in inputs.items())
newinputs={n:module.sha(corrected/n) for n in inputs};changed=[n for n in inputs if inputs[n]!=newinputs[n]]
assert changed==['tests/windows/native/observation_frontend_probe.cpp'],changed
identity=json.loads((out/'product-build-identity.json').read_bytes());product_binding=identity['inputs']
assert len(product_binding)==404 and all(module.sha(corrected/n)==d for n,d in product_binding.items())
assert subprocess.check_output(['git','show',source+':'+recipe.relative_to(root).as_posix()])==recipe.read_bytes()
module.save(fix/'source-inputs.json',newinputs)
tree=subprocess.check_output(['git','ls-tree','-r','-z',fixed],cwd=corrected);blobs={}
for row in tree.split(b'\0'):
    if not row:continue
    header,path=row.split(b'\t',1);name=path.decode()
    if name in newinputs:
        blob=header.split()[2].decode();data=(corrected/name).read_bytes()
        assert hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blob,name
        blobs[name]=blob
assert blobs.keys()==newinputs.keys();module.save(fix/'source-blob-bindings.json',blobs)
module.save(fix/'source-comparison.json',dict(primary_source_revision=source,fixture_source_revision=fixed,changed_inputs=changed,production_inputs=404,production_inputs_unchanged=True,product_rebuilt_for_fixture_correction=False))
commands=json.loads((out/'commands.json').read_bytes());fixcommands=[]
def run(name,args,cwd,limit=180,folder=out):
    args=list(map(str,args));local=folder/'logs';local.mkdir(exist_ok=True);log=local/(name+'.log');assert not log.exists(),log
    start=time.monotonic()
    try:result=subprocess.run(args,cwd=cwd,capture_output=True,timeout=limit)
    except subprocess.TimeoutExpired as error:
        log.write_bytes((error.stdout or b'')+(error.stderr or b''));entry=dict(name=name,command=args,cwd=str(cwd),exit_code=None,elapsed_seconds=round(time.monotonic()-start,3),log=log.relative_to(out).as_posix(),error='timeout');commands.append(entry);module.save(out/'commands.json',commands);raise
    log.write_bytes(result.stdout+result.stderr);entry=dict(name=name,command=args,cwd=str(cwd),exit_code=result.returncode,elapsed_seconds=round(time.monotonic()-start,3),log=log.relative_to(out).as_posix());commands.append(entry);module.save(out/'commands.json',commands)
    if folder==fix:fixcommands.append(entry);module.save(fix/'commands.json',fixcommands)
    print(name+' exit '+str(result.returncode),flush=True)
    if result.returncode:raise RuntimeError(name+' failed '+str(log))
    return result.stdout

campaigns=json.loads((out/'campaigns.json').read_bytes())
for c in campaigns:c['source_revision']=source
artifacts=[]
for kind,arch,path in [('product','x64',checkout/'build/windows-bootstrap/Release/disked.exe'),('capture-reducer','x64',checkout/'build/windows-bootstrap/Release/capture_probe.exe')]:
    artifacts.append(dict(kind=kind,architecture=arch,path=str(path),bytes=path.stat().st_size,sha256=module.sha(path),source_revision=source))
targets={'inventory-advance':'nt_inventory_advance_probe','inventory-frontend':'nt_inventory_frontend_probe','identity-frontend':'nt_identity_frontend_probe'}
for c in campaigns:
    if c['kind']=='inventory-port':continue
    path=out/('build-'+c['architecture'])/'Release'/(targets[c['kind']]+'.exe')
    artifacts.append(dict(kind=c['kind'],architecture=c['architecture'],path=str(path),bytes=path.stat().st_size,sha256=module.sha(path),source_revision=source))
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for arch,pointer in [('x64',8),('Win32',4)]:
    build=fix/('build-'+arch)
    run('corrected-port-configure-'+arch,['cmake','-S',corrected/'tests/windows/native','-B',build,'-G','Visual Studio 17 2022','-A',arch+',version=10.0.19041.0','-T','v143,version=14.44.35207,host=x64','-DCMAKE_SYSTEM_VERSION=10.0.19041.0'],corrected,folder=fix)
    run('corrected-port-build-'+arch,['cmake','--build',build,'--config','Release','--target','nt_inventory_port_probe','--parallel','4'],corrected,600,fix)
    campaign=fix/('inventory-port-'+arch);probe=build/'Release/nt_inventory_port_probe.exe'
    run('corrected-inventory-port-'+arch,[sys.executable,corrected/'tests/windows/test_inventory_port.py','--probe',probe,'--output',campaign,'--pointer-bytes',pointer],corrected,360,fix)
    result=json.loads((campaign/'results.json').read_bytes());assert result['status']=='pass' and all(x['passed'] for x in result['checks'])
    assert (result['controller_executions'],result['actual_child_launches'],result['assertions'])==(23,88,7503)
    campaigns=[c for c in campaigns if not (c['kind']=='inventory-port' and c['architecture']==arch)]
    campaigns.append(dict(kind='inventory-port',architecture=arch,controllers=23,child_launches=88,assertions=7503,pointer_bytes=pointer,source_revision=fixed,retained_folder=campaign.relative_to(out).as_posix()))
    artifacts.append(dict(kind='inventory-port',architecture=arch,path=str(probe),bytes=probe.stat().st_size,sha256=module.sha(probe),source_revision=fixed))
    for mode in ('headers','imports','dependents'):run('corrected-port-'+mode+'-'+arch,[dumpbin,'/'+mode,probe],corrected,folder=fix)
    config=fix/('build-configuration-'+arch);config.mkdir();shutil.copyfile(build/'CMakeCache.txt',config/'CMakeCache.txt');shutil.copyfile(build/'nt_inventory_port_probe.vcxproj',config/'nt_inventory_port_probe.vcxproj')
    for f in (build/'CMakeFiles').rglob('CMake*Compiler.cmake'):shutil.copyfile(f,config/f.name)
    module.save(out/'campaigns.json',campaigns)

probe=out/'build-Win32/Release/nt_identity_frontend_probe.exe';campaign=out/'identity-frontend-Win32'
run('identity-frontend-Win32',[sys.executable,checkout/'tests/windows/test_observation_frontend.py','--probe',probe,'--output',campaign,'--pointer-bytes','4','--storage-profile','identity-layout'],checkout,360)
result=json.loads((campaign/'results.json').read_bytes());assert result['status']=='pass' and all(x['passed'] for x in result['checks'])
controllers=result.get('controller_executions',result.get('native_executions',result.get('processes',result.get('executions'))));controllers=len(controllers) if isinstance(controllers,list) else controllers
assert (controllers,result['actual_child_launches'],result['assertions'])==(21,46,7185)
campaigns.append(dict(kind='identity-frontend',architecture='Win32',controllers=21,child_launches=46,assertions=7185,pointer_bytes=4,source_revision=source));module.save(out/'campaigns.json',campaigns)
for mode in ('headers','imports','dependents'):run('identity-frontend-'+mode+'-Win32',[dumpbin,'/'+mode,probe],checkout)
shutil.copyfile(out/'build-Win32/nt_identity_frontend_probe.vcxproj',out/'build-configuration-Win32/nt_identity_frontend_probe.vcxproj')
artifacts.append(dict(kind='identity-frontend',architecture='Win32',path=str(probe),bytes=probe.stat().st_size,sha256=module.sha(probe),source_revision=source))
assert len(campaigns)==8 and len(artifacts)==10

namespace=dict(module.__dict__);namespace.update(a=argparse.Namespace(source_revision=source),root=root,out=out,logs=logs,checkout=checkout,commands=commands,inputs=inputs,product_binding=product_binding,host=json.loads((logs/'host.log').read_bytes()),run=run,campaigns=campaigns,artifacts=artifacts,launch=json.loads((logs/'product-launch.log').read_bytes())['result'],product_build=checkout/'build/windows-bootstrap')
text=recipe.read_text();tail=text[text.index("    run('tooling-tests'"):];tail=tail[:tail.index("\nif __name__=='__main__'")]
exec(compile(textwrap.dedent(tail),str(recipe)+' (final exact-source stages)','exec'),namespace)
summary=json.loads((out/'results.json').read_bytes());summary.update(qualified_repository_revision=fixed,fixture_correction_source_revision=fixed,fixture_correction_evidence=fix.relative_to(out).as_posix(),production_inputs_unchanged_after_fixture_correction=True,source_binding_policy='Each campaign and artifact declares its exact source; product build/test source remains 6e4c2059. Only the private port-test controller changed at 8cf67f0d; all 404 production build inputs are byte-identical.',product_suite_rerun_mode='Full serial 77-group suite after retained parallel attempt76pass1fail and isolated joined-report rerun1pass; unchanged source/artifacts/3000-ms exit wait. Original delay cause unestablished.')
module.save(out/'results.json',summary);print(json.dumps(dict(status='pass',campaigns=len(campaigns),source_inputs=len(inputs),qualified_repository_revision=fixed)),flush=True)
