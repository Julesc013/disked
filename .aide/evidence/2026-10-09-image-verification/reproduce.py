"""Clean native read-only acquired-image qualification with owned generated files.
Installed pinned tools only; fresh local clone, no fetch/install/signing/devices.
Run native suites serially because per-user Windows worker jobs are shared.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args()
revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert revision==a.source and len(revision)==40
C=R/('.aide-local/goal-0.1.0/clean-image-verification-'+revision[:8])
E=R/('.aide/evidence/2026-10-09-image-verification/reproduction-'+revision[:8])
A=R/('.aide-local/artifacts/DE-W034-image-verification-'+revision[:8])
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'])
assert not C.exists() and not E.exists() and not A.exists()
E.mkdir(parents=True);A.mkdir(parents=True);commands=[]
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
run('build',['cmake','--build','--preset','windows-bootstrap','--parallel','4'],limit=900)
P=C/'build/windows-bootstrap/Release'
catalog=json.loads(run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']).stdout)
selected=[t['name'] for t in catalog['tests']];assert len(selected)==70 and 'evidence.acquired_image_verification' in selected
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1500);assert b'0 tests failed out of 70' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('image-verification',[sys.executable,'tests/evidence/test_image_verification.py','--probe',P/'acquired_image_verification_probe.exe','--product',P/'disked.exe','--root',C,'--evidence',E/'image-verification.json'])
focused=json.loads((E/'image-verification.json').read_bytes());assert focused['passed'] and focused['checks']==70 and len(focused['samples'])==1
assert focused['source_revision']==revision and not focused['source_dirty'] and all(x['passed'] for x in focused['observations'])
assert focused['probe_sha256']==sha(P/'acquired_image_verification_probe.exe') and focused['product_sha256']==sha(P/'disked.exe')
sample=focused['samples'][0];out=sample['outcome'];definition=sample['definition']
def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
assert sample['definition_digest']=='sha256:'+hashlib.sha256(encode(definition)).hexdigest()
assert out['status']=='matched' and out['matched_bytes']==out['covered_bytes']==out['source_bytes']=='262145' and out['substituted_bytes']=='0'
assert out['sealed'] and not out['pending'] and out['before']==out['after'] and sample['before_binding']==sample['after_binding']
assert sample['case_revalidation']=='passed' and sample['case_binding_before']==sample['case_binding_after']
assert out['claims']['authenticity']=='not_established' and not out['claims']['physical_admission'] and not out['claims']['mutation_authority']
write(E/'sample-independent-check.json',dict(passed=True,definition_digest=sample['definition_digest'],matched_bytes='262145',scope='Independent retained definition/counter/resource checks; native byte/map corpus independently checked in Python. No actor/source-preservation/custody qualification.'))
check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout);assert check['status']=='PASS' and check['schemas']==60
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout)
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
context=json.loads(run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-image-verification','--byte-budget','500000']).stdout)
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-image-verification'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean' and len(identity['inputs'])==338
assert all(sha(C/name)==expected for name,expected in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
assert deps and any('disked_case_evidence' in x for x in deps) and all('disked_file_image_verification' not in x for x in deps)
(E/'product-link-closure.log').write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','acquired_image_verification_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result'];assert launch['version']=='0.1.0-dev.31' and launch['source_revision']==revision
commands_view=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert sum(x['availability']=='available' for x in commands_view)==19
tests=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],limit=300);assert b'Ran 185 tests' in tests.stderr and b'skipped=2' in tests.stderr
write(E/'native-artifacts.json',[dict(path=f.relative_to(C).as_posix(),bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(P.glob('*.exe'))])
artifacts=[]
for name in ('disked.exe','acquired_image_verification_probe.exe','disked_case_evidence.lib','disked_file_image_verification.lib','disked_file_case_source.lib'):
    destination=A/name;shutil.copyfile(P/name,destination);artifacts.append(dict(path=destination.relative_to(R).as_posix(),bytes=destination.stat().st_size,sha256=sha(destination)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,source=identity,base_revision='f4dd128823705031eb6a5bf341723dec370f260e',host=host,observed_at=datetime.now(timezone.utc).isoformat(),
    native_ctest_groups_run=70,selected_native_groups=selected,focused_checks=70,actual_acquisitions=2,actual_empty_acquisition=True,actual_current_image_corruption=True,
    actual_held_sharing_and_rename=True,actual_image_and_case_metadata_changes=True,synthetic_records_and_port_faults_separate=True,
    structural_checks=check['checks'],manifest=manifest,context_bytes=context['bytes'],spec_tests=dict(run=185,passed=183,skipped=2),implemented_commands=19,
    product_links_verification_adapter=False,artifacts=artifacts,limitations=[
        'Private synchronous current-byte read-only verifier/probe. Runtime port is not selected by the product composition; no available command or frozen public ABI is added.',
        'matched concerns current held ordinary-file image chunks matching the recorded map and exact original plan/output generations; it establishes no source preservation, authenticated actor/custody, point-in-time acquisition, physical fencing, worker exit or power-loss persistence.',
        'Finite allocations/ranges/records are not bounded OS-call latency or asynchronous containment. Product worker/watch/frontend integration, case/custody applicability and disclosure remain work; existing acquisition case/support still says current image verification was not performed.',
        'Observed image/map facts and selected case applicability are separate. A later unavailable case binding retains the image outcome without qualifying the current case. Synthetic records/API faults are separate from actual native byte/sharing/metadata effects.',
        'Windows host/compiler/SDK/static imports are exact local evidence, not a complete dynamic DLL closure or other-platform qualification. Full DE-W034/all specified 0.1.0 platforms/storage and owner/physical/elevation/customer/install/signing/publication/release gates remain open.']))
print('Clean private DE-W034 image verification PASS at '+revision,flush=True)
