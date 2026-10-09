"""Clean native immutable-observation/disclosure/export qualification.
Installed pinned tools, fresh local clone, serial native suites, owned images.
No fetch/install/elevation/devices/customer data/signing/publication.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args()
revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert revision==a.source and len(revision)==40
C=R/('.aide-local/goal-0.1.0/clean-image-observation-'+revision[:8])
E=R/('.aide/evidence/2026-10-10-image-observation/reproduction-'+revision[:8])
A=R/('.aide-local/artifacts/DE-W034-image-observation-'+revision[:8])
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'])
assert not C.exists() and not E.exists() and not A.exists();E.mkdir(parents=True);A.mkdir(parents=True);commands=[]
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def run(name,argv,cwd=C,limit=120):
    argv=[str(x) for x in argv];start=datetime.now(timezone.utc).isoformat();r=subprocess.run(argv,capture_output=True,cwd=cwd,timeout=limit)
    log=E/('clean-'+name+'.log');log.write_bytes(r.stdout+r.stderr)
    commands.append(dict(command=argv,cwd=str(cwd),started_at=start,exit_code=r.returncode,status='pass' if not r.returncode else 'fail',evidence_path=log.relative_to(R).as_posix()))
    write(E/'commands.json',commands);print(name+' exit '+str(r.returncode),flush=True)
    if r.returncode:raise RuntimeError(name+' failed; actual logs/dependencies retained')
    return r
host_command="$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$principal=[System.Security.Principal.WindowsPrincipal]::new($identity);$os=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$identity.Name;elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$os.Caption;version=$os.Version;build=$os.BuildNumber;architecture=$os.OSArchitecture}|ConvertTo-Json -Compress"
host=json.loads(run('host',['powershell','-NoProfile','-Command',host_command],R).stdout);assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],R)
run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision and not subprocess.check_output(['git','status','--porcelain'],cwd=C)
run('configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build','--preset','windows-bootstrap','--parallel','4'],limit=900);P=C/'build/windows-bootstrap/Release'
catalog=json.loads(run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']).stdout)
selected=[x['name'] for x in catalog['tests']];assert len(selected)==71 and 'evidence.image_verification_observation' in selected
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1500);assert b'0 tests failed out of 71' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('image-observation',[sys.executable,'tests/evidence/test_image_observation.py','--probe',P/'image_verification_observation_probe.exe','--product',P/'disked.exe','--root',C,'--evidence',E/'image-observation.json'])
f=json.loads((E/'image-observation.json').read_bytes());assert f['passed'] and f['checks']==449 and f['source_revision']==revision and not f['source_dirty']
assert f['probe_sha256']==sha(P/'image_verification_observation_probe.exe') and f['product_sha256']==sha(P/'disked.exe') and len(f['samples'])==1 and len(f['exports'])==16 and all(x['passed'] for x in f['observations'])
def encode(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
s=f['samples'][0];v=s['observation'];assert s['revision']=='sha256:'+hashlib.sha256(encode(v)).hexdigest()
assert v['outcome']['status']=='matched' and v['outcome']['matched_bytes']=='262145' and v['attachment_applicability']=='applicable' and v['case_revalidation']=='passed' and v['image_binding_revalidation']=='passed'
assert v['verifier']['source_revision']==revision and v['verifier']['source_state']=='clean' and v['verifier']['image_digest']==sha(P/'image_verification_observation_probe.exe')
assert len(s['projections'])==16 and s['original_case_claims']['current_image_verification']=='not_performed'
for row in s['projections']:
    b=encode(row['support'])+b'\n';assert row['artifact_bytes'].encode()==b and row['artifact']['digest']=='sha256:'+hashlib.sha256(b).hexdigest()
assert all(x['outcome']['status']=='completed' and not x['outcome']['uncertain_effect'] for x in f['exports'])
write(E/'sample-independent-check.json',dict(passed=True,revision=s['revision'],matched_bytes='262145',selected_projections=16,actual_completed_exports=16,scope='Independent retained identity/canonical-byte/resource checks, not an authenticated observer/custody or latest-image admission. Full C++ vs Python projections and actual exports are independently tested in the native harness.'))
check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout);assert check['status']=='PASS' and check['schemas']==60
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
context=json.loads(run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-image-observation','--byte-budget','500000']).stdout)
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-image-observation'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean' and len(identity['inputs'])==343 and all(sha(C/name)==value for name,value in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
assert deps and all('disked_file_image_verification' not in x for x in deps);(E/'product-link-closure.log').write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','image_verification_observation_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result'];assert launch['version']=='0.1.0-dev.31' and launch['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert sum(x['availability']=='available' for x in discovery)==19
tool=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],limit=300);assert b'Ran 185 tests' in tool.stderr and b'skipped=2' in tool.stderr
write(E/'native-artifacts.json',[dict(path=p.relative_to(C).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(P.glob('*.exe'))]);artifacts=[]
for name in ('disked.exe','image_verification_observation_probe.exe','disked_report_export.lib','disked_file_report_export.lib','disked_case_evidence.lib','disked_file_case_source.lib'):
    target=A/name;shutil.copyfile(P/name,target);artifacts.append(dict(path=target.relative_to(R).as_posix(),bytes=target.stat().st_size,sha256=sha(target)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,base_revision='ad011cdedcb23e11a1f826a98ba167e97b5c3e61',source=identity,host=host,observed_at=datetime.now(timezone.utc).isoformat(),native_ctest_groups_run=71,selected_native_groups=selected,focused_checks=449,actual_generated_acquisitions=2,actual_completed_support_exports=16,actual_wrong_and_inner_digest_refusals=True,actual_source_change_before_creation=True,actual_image_and_case_changes=True,synthetic_contradictions_separate=True,structural_checks=check['checks'],manifest=manifest,context_bytes=context['bytes'],spec_tests=dict(run=185,passed=183,skipped=2),implemented_commands=19,product_selects_image_verification_adapter=False,artifacts=artifacts,limitations=[
    'Private immutable historical observation/projection and synchronous explicitly granted ordinary-file support exports; new artifact scope/wrapper is not admitted by the existing product acquisition-report command schemas. No image.verify availability or stable persisted/public ABI.',
    'Original acquisition case claims remain immutable. Matching bytes, attachment applicability, clock/code declarations and output receipts are separate; historical facts do not qualify the latest files, source preservation, authenticated actor/custody, worker exit or physical fencing.',
    'Finite allocation/record/range budgets are not bounded OS-call latency or async worker containment. Durable custody collections, bounded reader/store/watch/cancellation and all product frontend journeys remain work.',
    'Actual generated-file effects are separate from synthetic receipt alterations/API conditions. Static imports are not a full dynamic DLL closure; full DE-W034/all specified 0.1.0 platforms/storage and owner/physical/elevation/customer/install/signing/publication/release gates remain open.']))
print('Clean private DE-W034 immutable image observation PASS at '+revision,flush=True)
