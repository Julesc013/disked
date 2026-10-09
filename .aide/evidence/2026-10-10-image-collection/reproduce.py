"""Clean native historical-collection/retention/reload qualification.
Installed pinned tools, fresh local clone, serial native suites, owned images.
No fetch/install/elevation/devices/customer data/signing/publication.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args()
revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert revision==a.source and len(revision)==40
C=R/('.aide-local/goal-0.1.0/clean-image-collection-'+revision[:8])
E=R/('.aide/evidence/2026-10-10-image-collection/reproduction-'+revision[:8])
A=R/('.aide-local/artifacts/DE-W034-image-collection-'+revision[:8])
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
selected=[x['name'] for x in catalog['tests']];assert len(selected)==72 and 'evidence.image_verification_collection' in selected
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1500);assert b'0 tests failed out of 72' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('image-collection',[sys.executable,'tests/evidence/test_image_collection.py','--probe',P/'image_verification_collection_probe.exe','--observation-probe',P/'image_verification_observation_probe.exe','--product',P/'disked.exe','--root',C,'--evidence',E/'image-collection.json'])
f=json.loads((E/'image-collection.json').read_bytes());assert f['passed'] and f['checks']==374 and f['source_revision']==revision and not f['source_dirty']
assert f['probe_sha256']==sha(P/'image_verification_collection_probe.exe') and f['observation_probe_sha256']==sha(P/'image_verification_observation_probe.exe') and f['product_sha256']==sha(P/'disked.exe') and len(f['samples'])==1 and len(f['exports'])==18 and all(x['passed'] for x in f['observations'])
sys.path.insert(0,str(C/'tests/evidence'));from test_case import encode
s=f['samples'][0];v=s['collection'];assert s['revision']=='sha256:'+hashlib.sha256(encode(v)).hexdigest()
assert s['retention_bytes'].encode()==encode(v)+b'\n' and s['retention']['digest']=='sha256:'+hashlib.sha256(s['retention_bytes'].encode()).hexdigest()
assert len(v['records'])==2 and v['records'][0]['observation']['outcome']['status']=='matched' and v['records'][1]['observation']['outcome']['status']=='mismatch'
assert v['original_case']['claims']['current_image_verification']=='not_performed' and bytes.fromhex(v['history_hex']).endswith(b'\n')
previous='sha256:'+'0'*64
for row in v['records']:
    assert row['previous_digest']==previous and row['digest']=='sha256:'+hashlib.sha256(encode({k:x for k,x in row.items() if k!='digest'})).hexdigest();previous=row['digest']
    o=row['observation'];assert row['observation_revision']=='sha256:'+hashlib.sha256(encode(o)).hexdigest() and o['verifier']['source_revision']==revision and o['verifier']['source_state']=='clean' and o['verifier']['image_digest']==sha(P/'image_verification_observation_probe.exe')
assert len(s['projections'])==16
for row in s['projections']:
    b=encode(row['support'])+b'\n';assert row['artifact_bytes'].encode()==b and row['artifact']['digest']=='sha256:'+hashlib.sha256(b).hexdigest()
assert all(x['outcome']['status']=='completed' and not x['outcome']['uncertain_effect'] for x in f['exports'])
assert sum(x['definition']['effect']['artifact']['scope']=='recorded-image-verification-collection-private' for x in f['exports'])==2
write(E/'sample-independent-check.json',dict(passed=True,revision=s['revision'],records=2,selected_projections=16,actual_completed_exports=18,scope='Independent retained canonical identities and chain/artifact checks; full C++ vs Python projections, native effects and source applicability are tested by the harness. No actor/custody/latest-image/all-platform/physical admission.'))
check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout);assert check['status']=='PASS' and check['schemas']==60
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
context=json.loads(run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-image-observation','--byte-budget','500000']).stdout)
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-image-observation'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean' and len(identity['inputs'])==350 and all(sha(C/name)==value for name,value in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
assert deps and all('disked_file_image_verification' not in x for x in deps);(E/'product-link-closure.log').write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','image_verification_collection_probe','image_verification_observation_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result'];assert launch['version']=='0.1.0-dev.31' and launch['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert sum(x['availability']=='available' for x in discovery)==19
tool=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],limit=300);assert b'Ran 185 tests' in tool.stderr and b'skipped=2' in tool.stderr
write(E/'native-artifacts.json',[dict(path=p.relative_to(C).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(P.glob('*.exe'))]);artifacts=[]
for name in ('disked.exe','image_verification_collection_probe.exe','image_verification_observation_probe.exe','disked_report_export.lib','disked_file_report_export.lib','disked_case_evidence.lib','disked_file_case_source.lib'):
    target=A/name;shutil.copyfile(P/name,target);artifacts.append(dict(path=target.relative_to(R).as_posix(),bytes=target.stat().st_size,sha256=sha(target)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,base_revision='d881f825ffed82235331c799b5561ec5c0cedc90',source=identity,host=host,observed_at=datetime.now(timezone.utc).isoformat(),native_ctest_groups_run=72,selected_native_groups=selected,focused_checks=374,actual_generated_acquisitions=1,actual_completed_exports=18,actual_wrong_inner_and_private_disabled_refusals=True,actual_retention_metadata_change=True,actual_original_paths_unavailable=True,actual_binary_torn_tail=True,synthetic_contradictions_separate=True,structural_checks=check['checks'],manifest=manifest,context_bytes=context['bytes'],spec_tests=dict(run=185,passed=183,skipped=2),implemented_commands=19,product_selects_image_verification_adapter=False,artifacts=artifacts,limitations=[
    'Private bounded historical collection and explicitly granted complete retention/selected support. No new image.verify command or stable persisted/public ABI; current product acquisition-export validation rejects both new scopes.',
    'Actual Windows generated acquisition, image byte mismatch, selected metadata change, private-disabled/wrong/inner grants, existing outputs, binary torn history and fresh-process reload. Synthetic record/clock/code/epoch alterations are separate.',
    'Original acquisition claims remain immutable. Historical records and hashes authenticate no actor or custody and grant no latest-image access, worker restart or source preservation claim. API-confirmed per-file flush/readback does not establish power-loss persistence.',
    'Finite data/range/allocation limits do not bound OS-call latency or worker containment. Bounded reader/store/watch/cancel/frontend, full DE-W034/all specified 0.1.0 storage/platforms and owner/physical/elevation/customer/install/signing/publication gates remain open. Static imports are not a complete dynamic dependency closure.']))
print('Clean private DE-W034 historical collection/retention PASS at '+revision,flush=True)
