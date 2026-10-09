"""Clean native qualification of the private two-source evidence exporter.
Installed pinned tools, fresh local clone, serial native generated-file suites.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);a=ap.parse_args()
revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert revision==a.source and len(revision)==40
C=R/('.aide-local/goal-0.1.0/clean-verification-case-'+revision[:8]);E=R/('.aide/evidence/2026-10-10-verification-case-export/reproduction-'+revision[:8]);A=R/('.aide-local/artifacts/DE-W034-verification-case-'+revision[:8])
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'])
assert not C.exists() and not E.exists() and not A.exists();E.mkdir(parents=True);A.mkdir(parents=True);commands=[]
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def run(name,argv,cwd=C,limit=120):
    argv=[str(x) for x in argv];r=subprocess.run(argv,capture_output=True,cwd=cwd,timeout=limit);log=E/('clean-'+name+'.log');log.write_bytes(r.stdout+r.stderr)
    commands.append(dict(command=argv,cwd=str(cwd),exit_code=r.returncode,status='pass' if not r.returncode else 'fail',evidence_path=log.relative_to(R).as_posix()));write(E/'commands.json',commands);print(name+' exit '+str(r.returncode),flush=True)
    if r.returncode:raise RuntimeError(name+' failed; actual logs and dependencies retained')
    return r
host_command="$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$principal=[System.Security.Principal.WindowsPrincipal]::new($identity);$os=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$identity.Name;elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$os.Caption;version=$os.Version;build=$os.BuildNumber;architecture=$os.OSArchitecture}|ConvertTo-Json -Compress"
host=json.loads(run('host',['powershell','-NoProfile','-Command',host_command],R).stdout);assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],R)
run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision
run('configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build','--preset','windows-bootstrap','--parallel','4'],limit=900);P=C/'build/windows-bootstrap/Release'
catalog=json.loads(run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']).stdout);selected=[x['name'] for x in catalog['tests']];assert len(selected)==76 and 'evidence.verification_case_export' in selected
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1500);assert b'0 tests failed out of 76' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('joined-export',[sys.executable,'tests/evidence/test_verification_case.py','--probe',P/'verification_case_probe.exe','--fault',P/'verification_case_fault.exe','--product',P/'disked.exe','--root',C,'--evidence',E/'joined-export.json'],limit=150)
f=json.loads((E/'joined-export.json').read_bytes());assert f['passed'] and f['checks']>=145 and len(f['samples'])==1 and len(f['actual_exports'])==21
names=[x['name'] for x in f['observations']];assert names.count('actual-sixteen-selected-artifacts')==16 and names.count('synthetic-false-grant-zero-ports')==15 and names.count('actual-false-grant-no-output')==15
for name in ('exact-independent-full-join','exact-original-inputs','synthetic-late-keeps-actual-executor-result','synthetic-contradictory-output-not-completed','actual-held-source-denies-writer','actual-joint-export','actual-separate-final-observations','actual-recreated-source-no-output','actual-original-media-paths-not-followed'):assert name in names
sample=f['samples'][0];request=bytes.fromhex(sample['acquisition_request_hex']);history=bytes.fromhex(sample['acquisition_history_hex']);body=bytes.fromhex(sample['collection_hex']);coll=json.loads(body);state=sample['terminal']['result']['state']
assert coll['request_raw'].encode()==request and bytes.fromhex(coll['history_hex'])==history and sha(P/'disked.exe')==state['binding']['verifier']['image_digest']
assert state['binding']['verifier']['source_revision']==revision and state['binding']['verifier']['source_state']=='clean' and state['retention']['digest']=='sha256:'+hashlib.sha256(body).hexdigest()
assert body==canonical(coll)+b'\n' and len(body)==int(state['retention']['bytes']) and coll['records'][0]['observation']['outcome']==state['outcome']
check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout);assert check['status']=='PASS' and check['schemas']==69
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
context=json.loads(run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-verification-case','--byte-budget','500000']).stdout);run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-verification-case'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes());assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean' and len(identity['inputs'])==387 and all(sha(C/name)==value for name,value in identity['inputs'].items())
for subject in ('disked','verification_case_probe'):
    project=ET.parse(C/('build/windows-bootstrap/'+subject+'.vcxproj'));deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')];assert deps
    assert all(('disked_file_verification_case_export' in x)==(subject=='verification_case_probe') for x in deps)
    (E/(subject+'-link-closure.log')).write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','verification_case_probe','verification_case_fault'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result'];assert launch['version']=='0.1.0-dev.34' and launch['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert sum(x['availability']=='available' for x in discovery)==20
tool=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],limit=300);assert b'Ran 196 tests' in tool.stderr and b'skipped=2' in tool.stderr
write(E/'native-artifacts.json',[dict(path=p.relative_to(C).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(P.glob('*.exe'))]);artifacts=[]
for name in ('disked.exe','verification_case_probe.exe','verification_case_fault.exe','disked_acquisition_verification.lib','disked_file_verification_case_export.lib','disked_report_export.lib'):
    target=A/name;shutil.copyfile(P/name,target);artifacts.append(dict(path=target.relative_to(R).as_posix(),bytes=target.stat().st_size,sha256=sha(target)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,base_revision='8a761a36b0fb6d9804ec137f9cd5ca8691c2d532',source=identity,host=host,observed_at=datetime.now(timezone.utc).isoformat(),native_ctest_groups_run=76,selected_native_groups=selected,focused_checks=f['checks'],actual_exports=len(f['actual_exports']),actual_generated_acquisitions=1,actual_retained_collections=1,synthetic_faults_separate=True,structural_checks=check['checks'],manifest=manifest,context_bytes=context['bytes'],spec_tests=dict(run=196,passed=194,skipped=2),implemented_commands=20,product_selects_joined_report=False,artifacts=artifacts,limitations=f['limitations']))
print('Clean DE-W034 private joined report/export PASS at '+revision,flush=True)
