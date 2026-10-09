"""Clean local DE-W063 reproduction at the matching source checkpoint.

Requires the recorded Windows compiler/SDK and existing Python dependencies.
No remote fetch/install, elevation, media access, publication or archive execution.
Retained after the source checkpoint: reference this script from the evidence commit.
Destinations must not exist. No byte-for-byte claim across build paths/timestamps.
"""
import hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
C=R/('.aide-local/goal-0.1.0/clean-artifact-'+revision[:8])
E=R/('.aide/evidence/2026-10-09-artifact-checker/reproduction-'+revision[:8])
A=R/('.aide-local/artifacts/DE-W063-'+revision[:8]);recipe=Path(__file__).with_name('make_zip.py')
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no']) and not C.exists()
E.mkdir(parents=True,exist_ok=False);A.mkdir(parents=True,exist_ok=False);commands=[]
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def run(name,args,cwd=C,limit=420):
    argv=[str(x) for x in args];print('Running clean '+name,flush=True)
    try:p=subprocess.run(argv,cwd=cwd,capture_output=True,timeout=limit)
    except subprocess.TimeoutExpired as error:
        path=E/('clean-'+name+'.log');path.write_bytes((error.stdout or b'')+(error.stderr or b''))
        commands.append(dict(command=subprocess.list2cmdline(argv),cwd=str(cwd),exit_code=None,status='fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands);raise
    path=E/('clean-'+name+'.log');path.write_bytes(p.stdout+p.stderr)
    commands.append(dict(command=subprocess.list2cmdline(argv),cwd=str(cwd),exit_code=p.returncode,status='pass' if p.returncode==0 else 'fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands)
    print(name+' exit '+str(p.returncode),flush=True)
    if p.returncode:raise RuntimeError(name+' failed; log retained')
    return p
host_command="""$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$principal=[System.Security.Principal.WindowsPrincipal]::new($identity);$os=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$identity.Name;elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$os.Caption;version=$os.Version;build=$os.BuildNumber;architecture=$os.OSArchitecture}|ConvertTo-Json -Compress"""
host=json.loads(run('host',['powershell','-NoProfile','-Command',host_command],R).stdout)
assert host['identity']=='BLACKGLASS-WIN1\\Jules' and host['elevated'] is False
run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m,zlib;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"));print("zlib="+zlib.ZLIB_RUNTIME_VERSION)'],R)
run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision and not subprocess.check_output(['git','status','--porcelain'],cwd=C)
run('configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build','--preset','windows-bootstrap','--target','disked','provider_guard_probe'])
P=C/'build/windows-bootstrap/Release'
catalog=run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']);assert len(json.loads(catalog.stdout)['tests'])==54
native=run('focused-native',['ctest','--preset','windows-bootstrap','--output-on-failure','-R','^(artifacts.archive_completeness|disked.invocation|disked.acceptance|provider_guard.positive_control)$'])
assert b'0 tests failed out of 4' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('artifact-cases',[sys.executable,'tests/artifacts/test_artifact_check.py','--evidence',E/'artifact-cases.json'])
cases=json.loads((E/'artifact-cases.json').read_bytes());assert cases['passed'] and cases['tests']==51 and cases['skipped']==0 and all(x['status']=='pass' for x in cases['observations'])
assert not any(cases[k] for k in ('archive_execution','publication','authenticity'))
check=run('check',[sys.executable,'spec/tools/specctl.py','check']);assert json.loads(check.stdout)['checks']==933
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);assert manifest['files']==249 and manifest['bytes']==1549196
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W063','--output','.aide-local/context/DE-W063-artifact','--byte-budget','350000'])
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W063-artifact'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
assert identity['identity']['source_state']=='clean' and identity['identity']['source_revision']==revision
assert len(identity['inputs'])==253 and all(sha(C/name)==digest for name,digest in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
assert deps and all(not any(lib in x for lib in ('disked_journal_prototype','disked_plan_prototype','disked_guarded_model','disked_journal_semantics','disked_model_journal_producer')) for x in deps)
(E/'product-link-closure.log').write_bytes(('\n'.join(deps)+'\n').encode())
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run('disked-'+kind.lower(),[dumpbin,'/'+kind,P/'disked.exe'])
run('launch',[P/'disked.exe','build','inspect','--json']);assert json.loads((E/'clean-launch.log').read_bytes())['result']['source_revision']==revision
stage=A/'stage';stage.mkdir();shutil.copyfile(P/'disked.exe',stage/'disked.exe');assert sha(P/'disked.exe')==sha(stage/'disked.exe')
expected=A/'expected.json';archive=A/'disked.zip';tool=C/'tools/release/artifact_check.py'
run('inventory',[sys.executable,tool,'inventory','--staging',stage,'--required','disked.exe','--output',expected])
inventory=json.loads(expected.read_bytes());assert inventory['required_entrypoints']==['disked.exe'] and inventory['files']==[dict(path='disked.exe',type='regular',bytes=str((P/'disked.exe').stat().st_size),sha256=sha(P/'disked.exe'))]
write(E/'staging-review.json',dict(source_revision=revision,composition='windows.native.image.prototype',selection=['disked.exe'],inventory_sha256=sha(expected),reviewer='implementing agent',owner_accepted=False,archive_already_created=archive.exists(),comment='Independent local staging selection matches the clean native build; probes/private libraries excluded. Local review is not owner acceptance, runtime/release qualification or publication authority.'))
assert not archive.exists()
run('package-fixture',[sys.executable,recipe,stage,archive])
verification=json.loads(run('verify-archive',[sys.executable,tool,'verify','--inventory',expected,'--archive',archive]).stdout)
assert verification['status']=='pass' and verification['files']=='1' and verification['archive_sha256']==sha(archive) and verification['inventory_file_sha256']==sha(expected)
assert all(verification[x]=='not_run' for x in ('authenticity','publication','runtime','extraction'))
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v']);assert b'Ran 175 tests' in spec.stderr and b'skipped=2' in spec.stderr
artifacts=[dict(path=p.relative_to(R).as_posix(),sha256=sha(p),bytes=p.stat().st_size) for p in (stage/'disked.exe',expected,archive)]
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(source=identity,host=host,observed_at=datetime.now(timezone.utc).isoformat(),passed=True,native_ctest_groups_run=4,native_ctest_groups_available=54,artifact_tests=51,artifact_skipped=0,structural_checks=933,manifest_files=249,manifest_bytes=1549196,spec_tests=dict(run=175,passed=173,skipped=2),staging_inventory=inventory,archive_verification=verification,artifacts=artifacts,product_links_prototypes=False,
    limitations=['Focused validation: other 50 native groups not rerun at this revision; historical journal/runtime evidence remains source-bound.',
    'Current Windows x64 host and private strict ZIP subset only; no other-platform/carrier qualification, hostile concurrent staging isolation or measured allocator/time guarantee.',
    'No archive extraction or execution, authenticity, owner acceptance, installation, signing, remote write, publication or delivered-byte check.',
    'Product launch/import observations concern the trusted clean build separately; archive completeness does not confer runtime or release qualification.',
    'DE-W040 production journal decisions/physical writer gates remain pending; local artifact tooling does not qualify them.']))
print('Clean DE-W063 PASS at '+revision,flush=True)
