"""Clean source-bound public joined-report qualification on this Windows lane.
Uses installed pinned tools and a fresh local clone; owned native tests run serially.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);a=ap.parse_args()
revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert revision==a.source and len(revision)==40
C=R/('.aide-local/goal-0.1.0/clean-joined-public-'+revision[:8]);E=R/('.aide/evidence/2026-10-10-joined-report-public/reproduction-'+revision[:8]);A=R/('.aide-local/artifacts/DE-W034-joined-public-'+revision[:8])
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'])
assert not C.exists() and not E.exists() and not A.exists();E.mkdir(parents=True);A.mkdir(parents=True);commands=[]

def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def run(name,argv,cwd=C,limit=120):
    argv=[str(x) for x in argv];log=E/('clean-'+name+'.log')
    r=subprocess.run(argv,capture_output=True,cwd=cwd,timeout=limit);log.write_bytes(r.stdout+r.stderr)
    commands.append(dict(command=argv,cwd=str(cwd),exit_code=r.returncode,status='pass' if not r.returncode else 'fail',evidence_path=log.relative_to(R).as_posix()));write(E/'commands.json',commands);print(name+' exit '+str(r.returncode),flush=True)
    if r.returncode:raise RuntimeError(name+' failed; retain actual logs/dependencies')
    return r

host_command="$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$principal=[System.Security.Principal.WindowsPrincipal]::new($identity);$os=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$identity.Name;elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$os.Caption;version=$os.Version;build=$os.BuildNumber;architecture=$os.OSArchitecture}|ConvertTo-Json -Compress"
host=json.loads(run('host',['powershell','-NoProfile','-Command',host_command],R).stdout);assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],R)
run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision
run('configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build','--preset','windows-bootstrap','--parallel','4'],limit=900);P=C/'build/windows-bootstrap/Release'
catalog=json.loads(run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']).stdout);selected=[x['name'] for x in catalog['tests']];assert len(selected)==77 and 'frontend.joined_report' in selected
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1800);assert b'0 tests failed out of 77' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('joined-frontends',[sys.executable,'tests/frontend/test_product_export.py','--product',P/'disked.exe','--fault',P/'disked_report_test.exe','--probe',P/'export_command_probe.exe','--root',C,'--joined','--evidence',E/'joined-frontends.json'],limit=240)
f=json.loads((E/'joined-frontends.json').read_bytes());assert f['passed'] and f['joined'] and f['checks']>=280 and len(f['verified_outputs'])==6
names=[x['name'] for x in f['observations']]
assert names.count('joined-missing-grant-before-effects')==31 and names.count('synthetic-joined-false-grants-zero-ports')==31 and names.count('synthetic-public-producer-contradiction-refused')==9
for name in ('original-image-paths-unavailable','synthetic-exact-joined-grant-one-port','synthetic-preparation-source-mismatch-no-effect-port','bounded-wait-preserves-routing','occupied-slot-refuses-second-effect','late-callback-single-actual-effect','late-effect-never-replayed','selected-collection-unchanged'):assert name in names
source=next(s for s in f['samples'] if s['kind']=='actual-joined-source');body=bytes.fromhex(source['collection_hex']);coll=json.loads(body);assert body==canonical(coll)+b'\n' and coll['original_case']==source['acquisition']
frontend_samples=[s for s in f['samples'] if s['kind']=='actual-frontend-report'];assert {s['frontend'] for s in frontend_samples}=={'cli','stdio','gui','tui','shell'}
for sample in frontend_samples:
    d=sample['definition'];assert d['schema']=='org.disked.report-worker-definition-prototype/2' and d['source_revision']==revision and d['image_digest']==sha(P/'disked.exe')[7:]
    assert sample['header']['definition']==d and sample['header']['grant']['collection_read'] and sample['rows'][-1]['state']==sample['result']['state']
    assert all(sample['result'][key]=='not_established' for key in ('authenticity','custody_authentication','current_image_state','power_loss_persistence'))
    assert bytes.fromhex(sample['support_hex'])==canonical(sample['support'])+b'\n'
run('joined-worker',[sys.executable,'tests/evidence/test_verification_case.py','--probe',P/'verification_case_probe.exe','--fault',P/'verification_case_fault.exe','--product',P/'disked.exe','--worker',P/'report_worker_probe.exe','--worker-fault',P/'report_worker_fault.exe','--root',C,'--evidence',E/'joined-worker.json'],limit=240)
w=json.loads((E/'joined-worker.json').read_bytes());assert w['passed'] and w['checks']>=523 and len(w['actual_exports'])==47
worker_names=[x['name'] for x in w['observations']];assert worker_names.count('joined-public-compatible-observation')==3
joined_workers=[s for s in w['samples'] if s.get('kind','').startswith('actual-joined-worker-')];assert len(joined_workers)==26
check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout);assert check['status']=='PASS' and check['schemas']==76
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
context=json.loads(run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-joined-public','--byte-budget','500000']).stdout);run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-joined-public'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes());assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean' and len(identity['inputs'])==401 and all(sha(C/name)==value for name,value in identity['inputs'].items())
for subject in ('disked','disked_report_test','export_command_probe'):
    project=ET.parse(C/('build/windows-bootstrap/'+subject+'.vcxproj'));deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')];assert deps and all('disked_file_verification_case_export' in x for x in deps)
    (E/(subject+'-link-closure.log')).write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','disked_report_test','export_command_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result'];assert launch['version']=='0.1.0-dev.36' and launch['source_revision']==revision and launch['joined_report_provider']=='provider.report.acquisition-verification.prototype/1'
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert sum(x['availability']=='available' for x in discovery)==20
tool=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],limit=400);assert b'Ran 215 tests' in tool.stderr and b'skipped=2' in tool.stderr
write(E/'native-artifacts.json',[dict(path=p.relative_to(C).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(P.glob('*.exe'))]);artifacts=[]
for name in ('disked.exe','disked_report_test.exe','export_command_probe.exe','gui_model_probe.exe','tui_model_probe.exe','request_channel_probe.exe','disked_file_verification_case_export.lib','disked_report_export.lib'):
    target=A/name;shutil.copyfile(P/name,target);artifacts.append(dict(path=target.relative_to(R).as_posix(),bytes=target.stat().st_size,sha256=sha(target)))
for name in ('bootstrap_registry.h','build-identity.json'):
    target=A/name;shutil.copyfile(C/'build/windows-bootstrap/generated'/name,target);artifacts.append(dict(path=target.relative_to(R).as_posix(),bytes=target.stat().st_size,sha256=sha(target)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,base_revision='ba3d81644c286bbc10a380d901d122f6da3421a5',source=identity,host=host,observed_at=datetime.now(timezone.utc).isoformat(),qualification_recipe_sha256=sha(Path(__file__)),native_ctest_groups_run=77,selected_native_groups=selected,joined_frontend_checks=f['checks'],joined_worker_checks=w['checks'],actual_frontend_report_outputs=6,actual_joined_workers=len(joined_workers),private_actual_exports=len(w['actual_exports']),synthetic_port_and_budget_tests_separate=True,structural_checks=check['checks'],manifest=manifest,context_bytes=context['bytes'],spec_tests=dict(run=215,passed=213,skipped=2),implemented_commands=20,product_selects_joined_public_profile=True,artifacts=artifacts,limitations=['One Windows native ordinary-file prototype; all five joined frontends have actual generated-source evidence.','Synthetic ports/envelope/render fixtures are distinct from real generated-file effects.','Historical evidence does not authenticate custody, qualify current media or prove power-loss persistence.','Full DE-W034 and all 0.1.0 platforms/storage, owner and privilege/release gates remain open.']))
print('Clean DE-W034 public joined report PASS at '+revision,flush=True)
