"""Clean native contained-verification/progress/cancel/retention qualification.
Installed pinned tools, fresh local clone, serial native suites, owned images.
No fetch/install/elevation/devices/customer data/signing/publication.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args()
revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert revision==a.source and len(revision)==40
C=R/('.aide-local/goal-0.1.0/clean-verification-worker-'+revision[:8])
E=R/('.aide/evidence/2026-10-10-verification-worker/reproduction-'+revision[:8])
A=R/('.aide-local/artifacts/DE-W034-verification-worker-'+revision[:8])
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
selected=[x['name'] for x in catalog['tests']];assert len(selected)==73 and 'evidence.verification_worker' in selected
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1500);assert b'0 tests failed out of 73' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('verification-worker',[sys.executable,'tests/evidence/test_verification_worker.py','--probe',P/'verification_worker_probe.exe','--fault',P/'verification_worker_fault.exe','--product',P/'disked.exe','--collection',P/'image_verification_collection_probe.exe','--root',C,'--evidence',E/'verification-worker.json'])
f=json.loads((E/'verification-worker.json').read_bytes());assert f['status']=='passed' and f['count']==236 and len(f['samples'])==7 and all(x['passed'] for x in f['checks'])
for name,file in [('probe','verification_worker_probe.exe'),('fault','verification_worker_fault.exe'),('product','disked.exe'),('collection','image_verification_collection_probe.exe')]:assert f['binaries'][name]==sha(P/file)
for sample in f['samples']:
    state=sample['state'];header=sample['header'];verifier=state['binding']['verifier']
    assert verifier['source_revision']==revision and verifier['source_state']=='clean' and verifier['image_digest'] in [f['binaries']['probe'],f['binaries']['fault']]
    assert header['definition']['verifier']==verifier and state['retention']['digest']==sample['collection_sha256'] and state['quiescent'] and state['phase']=='finished'
write(E/'sample-independent-check.json',dict(passed=True,actual_retained_samples=7,source_revision=revision,scope='Independent retained source/binary/definition/verdict/retention identities; native harness additionally reconstructs full rows, observer/PID bindings, collection hashes and pure restore. Historical evidence authenticates no actor or current image.'))
check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout);assert check['status']=='PASS' and check['schemas']==60
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
context=json.loads(run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-image-observation','--byte-budget','500000']).stdout)
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-image-observation'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean' and len(identity['inputs'])==357 and all(sha(C/name)==value for name,value in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
assert deps and all('disked_file_image_verification' not in x for x in deps);(E/'product-link-closure.log').write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','verification_worker_probe','verification_worker_fault','image_verification_collection_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result'];assert launch['version']=='0.1.0-dev.32' and launch['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert sum(x['availability']=='available' for x in discovery)==19
tool=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],limit=300);assert b'Ran 185 tests' in tool.stderr and b'skipped=2' in tool.stderr
write(E/'native-artifacts.json',[dict(path=p.relative_to(C).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(P.glob('*.exe'))]);artifacts=[]
for name in ('disked.exe','verification_worker_probe.exe','verification_worker_fault.exe','image_verification_collection_probe.exe','disked_report_export.lib','disked_file_report_export.lib','disked_case_evidence.lib','disked_file_case_source.lib'):
    target=A/name;shutil.copyfile(P/name,target);artifacts.append(dict(path=target.relative_to(R).as_posix(),bytes=target.stat().st_size,sha256=sha(target)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,base_revision='a16407504f5626a680499cd775620560d82ab12c',source=identity,host=host,observed_at=datetime.now(timezone.utc).isoformat(),native_ctest_groups_run=73,selected_native_groups=selected,focused_checks=236,actual_generated_acquisitions=1,actual_retained_samples=7,actual_admission_timeout=True,actual_cancellation_before_during_and_late=True,actual_retention_and_terminal_faults=True,synthetic_contradictions_separate=True,structural_checks=check['checks'],manifest=manifest,context_bytes=context['bytes'],spec_tests=dict(run=185,passed=183,skipped=2),implemented_commands=19,product_selects_image_verification_adapter=False,artifacts=artifacts,limitations=[
    'Private same-executable ordinary-file verification role, finite history/cursor and typed collection retention. No public image.verify command, negotiated events/frontends or stable ABI.',
    'Admission wait is 3000 ms; synchronous preparation/inspection and all OS filesystem calls do not have universal caller-latency qualification. No replacement, cleanup or exit inference on timeout.',
    'Actual generated acquisition, same-generation byte corruption, replacement identity, unsealed map, cancellation timing, private-metadata grants and collection/terminal faults are distinct from synthetic record edits.',
    'Provider quiescence, OS process exit, verification verdict and retention certainty remain distinct. Hashes authenticate no actor/custody/current image; API flush/readback is not power-loss persistence.',
    'Full DE-W034, all specified platforms/storage and owner/physical/elevation/customer/install/signing/publication gates remain open. Static imports do not prove all dynamic dependencies.']))
print('Clean private DE-W034 contained verification worker PASS at '+revision,flush=True)
