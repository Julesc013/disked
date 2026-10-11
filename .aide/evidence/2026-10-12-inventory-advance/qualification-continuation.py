"""Resume the unchanged exact-source recipe after an independently run full serial suite."""
import argparse,hashlib,importlib.util,json,re,shutil,subprocess,textwrap,time
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--serial-exit-code',type=int,required=True);a0=p.parse_args();assert a0.serial_exit_code==0
root=Path.cwd();source='6e4c20591afb31389b95afe91dfc4037cde2a4e4';out=root/'.aide-local/inventory-advance-clean-6e4c2059';checkout=root/'.aide-local/owned-layout-clean-2c731a1c/checkout';logs=out/'logs'
recipe=root/'.aide/evidence/2026-10-12-inventory-advance/reproduce.py';assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=checkout).decode().strip()==source
assert not subprocess.check_output(['git','status','--porcelain'],cwd=checkout).strip()
assert subprocess.check_output(['git','show',source+':'+recipe.relative_to(root).as_posix()])==recipe.read_bytes()
spec=importlib.util.spec_from_file_location('disked_bound_recipe',recipe);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
inputs=json.loads((out/'source-inputs.json').read_bytes());assert all(module.sha(checkout/n)==d for n,d in inputs.items())
serial=root/'.aide-local/inventory-advance-native-serial-6e4c2059.log';payload=serial.read_bytes();assert b'0 tests failed out of 77' in payload and b'77/77' in payload
shutil.copyfile(serial,logs/'product-native.log');commands=json.loads((out/'commands.json').read_bytes())
assert commands[-1]['name']=='product-native-parallel-failure' and commands[-1]['exit_code']==8
for name,argv,log,count in [('joined-report-isolated-pass',['ctest','--preset','windows-bootstrap','-R','^frontend.joined_report$','--output-on-failure'],'joined-report-isolated-pass.log',1),('product-native',['ctest','--preset','windows-bootstrap','--output-on-failure'],'product-native.log',77)]:
 data=(logs/log).read_text();assert '0 tests failed out of '+str(count) in data
 elapsed=float(re.search(r'Total Test time \(real\) =\s*([\d.]+)',data)[1]);commands.append(dict(name=name,command=argv,cwd=str(checkout),exit_code=0,elapsed_seconds=elapsed,elapsed_source='CTest reported real total',log='logs/'+log))
module.save(out/'commands.json',commands)
def run(name,args,cwd,limit=180):
 args=list(map(str,args));start=time.monotonic();log=logs/(name+'.log');assert not log.exists(),name
 try:result=subprocess.run(args,cwd=cwd,capture_output=True,timeout=limit)
 except subprocess.TimeoutExpired as error:
  log.write_bytes((error.stdout or b'')+(error.stderr or b''));commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=None,elapsed_seconds=round(time.monotonic()-start,3),log='logs/'+log.name,error='timeout'));module.save(out/'commands.json',commands);raise
 log.write_bytes(result.stdout+result.stderr);commands.append(dict(name=name,command=args,cwd=str(cwd),exit_code=result.returncode,elapsed_seconds=round(time.monotonic()-start,3),log='logs/'+log.name));module.save(out/'commands.json',commands);print(name+' exit '+str(result.returncode),flush=True)
 if result.returncode:raise RuntimeError(name+' failed '+str(log))
 return result.stdout
identity=json.loads((checkout/'build/windows-bootstrap/generated/build-identity.json').read_bytes());product_binding=identity['inputs'];assert all(module.sha(checkout/n)==d for n,d in product_binding.items())
namespace=dict(module.__dict__);namespace.update(a=argparse.Namespace(source_revision=source),root=root,out=out,logs=logs,checkout=checkout,commands=commands,inputs=inputs,product_binding=product_binding,host=json.loads((logs/'host.log').read_bytes()),run=run,cases=[('inventory-advance','nt_inventory_advance_probe','test_inventory_advance.py',None,None,None),('inventory-frontend','nt_inventory_frontend_probe','test_inventory_frontend.py',59,36,916),('inventory-port','nt_inventory_port_probe','test_inventory_port.py',23,88,7503),('identity-frontend','nt_identity_frontend_probe','test_observation_frontend.py',21,46,7185)])
# Execute only the unchanged, Git-bound recipe's remaining stages. The full
# original failed attempt, focused rerun, serial rerun and this coordinator's
# exact bytes remain retained separately. No source/test expectation changes.
text=recipe.read_text();tail=text[text.index("    product_build=checkout/'build/windows-bootstrap'"):];tail=tail[:tail.index("\nif __name__=='__main__'")]
exec(compile(textwrap.dedent(tail),str(recipe)+' (remaining stages)', 'exec'),namespace)
summary=json.loads((out/'results.json').read_bytes());summary['product_suite_rerun_mode']='Full serial 77-group suite after retained parallel attempt76pass1fail and isolated joined-report rerun1pass; unchanged source/artifacts/3000-ms exit wait. Original delay cause unestablished.';module.save(out/'results.json',summary)
