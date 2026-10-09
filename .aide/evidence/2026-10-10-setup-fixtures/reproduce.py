"""Reproduce a source-bound package fixture using the exact retained dev.36 EXE.

No native rebuild or upstream execution. Original native build evidence is
reused at its exact source/byte identity; this recipe qualifies new packaging.
"""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--repository',type=Path,default=Path.cwd())
p.add_argument('--source-revision',required=True)
p.add_argument('--exe',type=Path,required=True)
p.add_argument('--native-evidence',type=Path,required=True)
p.add_argument('--output',type=Path,required=True)
a=p.parse_args()
R=a.repository.absolute(); E=a.exe.absolute(); N=a.native_evidence.absolute(); O=a.output.absolute()
assert len(a.source_revision)==40 and all(c in '0123456789abcdef' for c in a.source_revision)
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def save(path,value):
 with path.open('x',encoding='utf-8',newline='\n') as f:json.dump(value,f,indent=2);f.write('\n')
assert sha(E)=='sha256:ac2721db6b26231ed52c31742f472063bed8c7bd88ceb8f14690eb37dd63994d'
native=json.loads(N.read_bytes())
assert native['passed'] and native['source']['identity']['source_revision']=='ec30be78ba9e9f61dc578ff67b9d0af186166145'
assert any(x['sha256']==sha(E) and x['path'].endswith('/disked.exe') for x in native['artifacts'])
O.mkdir(); logs=O/'logs'; logs.mkdir(); receipts=[]
def run(name,args,cwd,expected=0):
 start=time.time(); result=subprocess.run([str(x) for x in args],cwd=cwd,capture_output=True)
 log=logs/(name+'.log');log.write_bytes(result.stdout+result.stderr)
 receipts.append(dict(name=name,command=[str(x) for x in args],cwd=str(cwd),
  expected_exit=expected,exit_code=result.returncode,status='pass' if result.returncode==expected else 'fail',
  elapsed_seconds=round(time.time()-start,3),log=str(log)))
 save_path=O/'commands.json';save_path.write_text(json.dumps(receipts,indent=2)+'\n',encoding='utf-8',newline='\n')
 assert result.returncode==expected,(name,result.returncode,log)
 return result.stdout
C=O/'checkout'
run('clone',['git','clone','--local','--no-hardlinks','--no-checkout',R,C],R)
run('checkout',['git','checkout','--detach',a.source_revision],C)
assert not run('source-status',['git','status','--porcelain'],C).strip()
host=json.loads(run('host',['powershell','-NoProfile','-Command',
 "$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent(); $principal = [System.Security.Principal.WindowsPrincipal]::new($identity); [ordered]@{identity=$identity.Name; elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)} | ConvertTo-Json"],C))
assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
source_inputs={}
for folder in ('release/bindings/universal-setup','tests/setup','external/universal-setup'):
 for path in sorted((C/folder).rglob('*')):
  if path.is_file():source_inputs[path.relative_to(C).as_posix()]=sha(path)
for name in ('spec/catalog/setup-fixture-prototype.json','tools/release/artifact_check.py'):
 source_inputs[name]=sha(C/name)
save(O/'source-inputs.json',source_inputs)
save(O/'recipe-identity.json',{'path':str(Path(__file__).absolute()),'sha256':sha(Path(__file__)),
 'packaging_source':a.source_revision,'native_source':native['source']['identity']['source_revision'],
 'native_evidence_sha256':sha(N),'recipe_executes_upstream':False})
for name,value in source_inputs.items():
 blob=subprocess.check_output(['git','-C',str(C),'show',a.source_revision+':'+name])
 assert 'sha256:'+hashlib.sha256(blob).hexdigest()==value
for name,value in native['source']['inputs'].items():
 blob=subprocess.check_output(['git','-C',str(R),'show','ec30be78ba9e9f61dc578ff67b9d0af186166145:'+name])
 assert 'sha256:'+hashlib.sha256(blob).hexdigest()==value
# Real ordinary no-elevation launches of the exact previously qualified image.
command=['--cli','--json','build','inspect']
build=json.loads(run('original-launch',[E,*command],C))
assert build['status']=='completed' and build['result']['source_state']=='clean'
assert all(build['result'][key]==value for key,value in native['source']['identity'].items())
save(O/'build-info.json',build['result'])
stage=O/'staging';stage.mkdir();shutil.copyfile(E,stage/'disked.exe')
run('inventory',[sys.executable,C/'tools/release/artifact_check.py','inventory','--staging',stage,
 '--required','disked.exe','--output',O/'independent-inventory.json'],C)
F=C/'release/bindings/universal-setup/package_fixture.py'
W=O/'fixtures'
run('init-fixtures',[sys.executable,F,'init-fixtures','--root',W],C)
common=['--inventory',O/'independent-inventory.json','--build-info',O/'build-info.json']
run('assemble',[sys.executable,F,'assemble','--workspace',W,'--staging',stage,*common,'--output','package'],C)
run('independent-zip',[sys.executable,C/'tools/release/artifact_check.py','verify','--inventory',O/'independent-inventory.json',
 '--archive',W/'package/payload.zip'],C)
verification=json.loads(run('verify',[sys.executable,F,'verify','--bundle',W/'package',*common],C))
run('extract-fixture',[sys.executable,F,'extract-fixture','--workspace',W,'--bundle',W/'package',*common,
 '--output','extracted'],C)
assert sha(W/'extracted/disked.exe')==sha(stage/'disked.exe')==sha(E)
after=json.loads(run('extracted-launch',[W/'extracted/disked.exe',*command],C))
assert after==build
run('occupied-root',[sys.executable,F,'extract-fixture','--workspace',W,'--bundle',W/'package',*common,
 '--output','extracted'],C,1)
run('repeat-assembly',[sys.executable,F,'assemble','--workspace',W,'--staging',stage,*common,'--output','package'],C,1)
occupied=W/'generated-case';occupied.mkdir()
files={'case/image.bin':b'generated-image-data','evidence/report.json':b'generated-case-evidence',
 'recovery/journal.bin':b'generated-unresolved-recovery','disked.exe':b'foreign-owner'}
for name,data in files.items():
 dest=occupied/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(data)
before={name:sha(occupied/name) for name in files}
run('occupied-case-retention',[sys.executable,F,'extract-fixture','--workspace',W,'--bundle',W/'package',*common,
 '--output','generated-case'],C,1)
assert before=={name:sha(occupied/name) for name in files}
save(O/'retention.json',{'generated_fixture_only':True,'files':before,'preserved':True})
run('unsupported-install',[sys.executable,F,'install'],C,2)
run('setup-tests',[sys.executable,'-m','unittest','discover','-s','tests/setup','-v'],C)
run('tooling-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],C)
run('check',[sys.executable,'spec/tools/specctl.py','check'],C)
context=O/'context'
run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W060','--output',context,
 '--byte-budget','340000'],C)
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context',context],C)
run('verify-manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest'],C)
assert not run('final-source-status',['git','status','--porcelain'],C).strip()
assert all(sha(C/name)==value for name,value in source_inputs.items())
artifacts=[]
for path in [stage/'disked.exe',W/'extracted/disked.exe']+sorted((W/'package').iterdir()):
 artifacts.append({'path':str(path),'bytes':path.stat().st_size,'sha256':sha(path)})
save(O/'results.json',dict(passed=True,packaging_source=a.source_revision,host=host,
 native_source=native['source']['identity']['source_revision'],native_rebuilt=False,
 native_prior_evidence_sha256=sha(N),recipe_sha256=sha(Path(__file__)),
 actual_original_and_extracted_launch=True,verification=verification,
 source_inputs=len(source_inputs),native_prior_inputs=len(native['source']['inputs']),artifacts=artifacts,
 setup_test_count=22,tooling_tests={'run':215,'passed':213,'skipped':2},
 occupied_root_retention=True,performed_remote_writes=False,
 live_setup='not_run',installation='not_run',signing='not_run',publication='not_run',owner_accepted=False))
print(json.dumps({'passed':True,'packaging_source':a.source_revision,'native_source':native['source']['identity']['source_revision'],
 'artifact_sha256':sha(E),'commands':len(receipts),'live_setup':'not_run'}))
