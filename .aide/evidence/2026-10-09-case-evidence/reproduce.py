"""Clean local reproduction of the private immutable case/custody/support model.

Requires the recorded installed Windows compiler/SDK and Python dependencies.
No remote fetch/install, elevation, media access, physical query or publication.
Reference this retained script at the matching source checkpoint; destinations
must not exist. Different build paths/timestamps are not claimed bit reproducible.
"""
import hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert revision=='e9b8fc99accdcce6a1481e4026790b56c1c13148', 'Checkout the qualified source checkpoint first'
C=R/('.aide-local/goal-0.1.0/clean-case-'+revision[:8]);E=R/('.aide/evidence/2026-10-09-case-evidence/reproduction-'+revision[:8]);A=R/('.aide-local/artifacts/DE-W034-'+revision[:8])
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no']) and not C.exists()
E.mkdir(parents=True,exist_ok=False);A.mkdir(parents=True,exist_ok=False);commands=[]
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def run(name,args,cwd=C,limit=420):
    argv=[str(x) for x in args];print('Running clean '+name,flush=True)
    try:p=subprocess.run(argv,cwd=cwd,capture_output=True,timeout=limit)
    except subprocess.TimeoutExpired as error:
        path=E/('clean-'+name+'.log');path.write_bytes((error.stdout or b'')+(error.stderr or b''));commands.append(dict(command=subprocess.list2cmdline(argv),cwd=str(cwd),exit_code=None,status='fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands);raise
    path=E/('clean-'+name+'.log');path.write_bytes(p.stdout+p.stderr);commands.append(dict(command=subprocess.list2cmdline(argv),cwd=str(cwd),exit_code=p.returncode,status='pass' if p.returncode==0 else 'fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands)
    print(name+' exit '+str(p.returncode),flush=True)
    if p.returncode:raise RuntimeError(name+' failed; log retained')
    return p
host_command="""$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$principal=[System.Security.Principal.WindowsPrincipal]::new($identity);$os=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$identity.Name;elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$os.Caption;version=$os.Version;build=$os.BuildNumber;architecture=$os.OSArchitecture}|ConvertTo-Json -Compress"""
host=json.loads(run('host',['powershell','-NoProfile','-Command',host_command],R).stdout);assert host['identity']=='BLACKGLASS-WIN1\\Jules' and host['elevated'] is False
run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],R)
run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision and not subprocess.check_output(['git','status','--porcelain'],cwd=C)
run('configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build','--preset','windows-bootstrap','--target','disked','case_evidence_probe','health_observation_probe','provider_guard_probe']);P=C/'build/windows-bootstrap/Release'
catalog=run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']);assert len(json.loads(catalog.stdout)['tests'])==57
native=run('focused-native',['ctest','--preset','windows-bootstrap','--output-on-failure','-R','^(evidence.case_model|health.observation_model|disked.invocation|disked.acceptance|provider_guard.positive_control)$']);assert b'0 tests failed out of 5' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('health-cases',[sys.executable,'tests/health/test_health.py','--probe',P/'health_observation_probe.exe','--root',C,'--evidence',E/'health-cases.json'])
cases=json.loads((E/'health-cases.json').read_bytes());assert cases['passed'] and cases['cases']==95 and all(x['passed'] for x in cases['observations']) and not any(cases[x] for x in ('physical_io','self_tests','provider_admitted','public_command_implemented'))
run('case-cases',[sys.executable,'tests/evidence/test_case.py','--probe',P/'case_evidence_probe.exe','--root',C,'--evidence',E/'case-cases.json'])
case_cases=json.loads((E/'case-cases.json').read_bytes());assert case_cases['passed'] and case_cases['cases']==82 and all(x['passed'] for x in case_cases['observations']) and not any(case_cases[x] for x in ('physical_io','file_export','public_evidence_command','origin_authenticated'))
check=run('check',[sys.executable,'spec/tools/specctl.py','check']);assert json.loads(check.stdout)['checks']==941
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);assert manifest['files']==253 and manifest['bytes']==1583124
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-case','--byte-budget','350000'])
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-case'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes());assert identity['identity']['source_state']=='clean' and identity['identity']['source_revision']==revision and len(identity['inputs'])==268 and all(sha(C/name)==digest for name,digest in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
private=('disked_journal_prototype','disked_plan_prototype','disked_guarded_model','disked_journal_semantics','disked_model_journal_producer','disked_case_evidence')
assert deps and all(not any(lib in x for lib in private) and 'disked_health_observation' in x for x in deps);(E/'product-link-closure.log').write_bytes(('\n'.join(deps)+'\n').encode())
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','case_evidence_probe','health_observation_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=run('launch',[P/'disked.exe','build','inspect','--json']);assert json.loads(launch.stdout)['result']['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert len([c for c in discovery if c['availability']=='available'])==18 and next(c for c in discovery if c['id']=='health.assess')['availability']=='available' and next(c for c in discovery if c['id']=='evidence.export')['availability']!='available'
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v']);assert b'Ran 175 tests' in spec.stderr and b'skipped=2' in spec.stderr
artifacts=[]
for name in ('disked.exe','case_evidence_probe.exe','disked_case_evidence.lib','health_observation_probe.exe','disked_health_observation.lib','disked_hash.lib','disked_json.lib'):
    path=A/name;shutil.copyfile(P/name,path);artifacts.append(dict(path=path.relative_to(R).as_posix(),sha256=sha(path),bytes=path.stat().st_size))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(source=identity,base_revision='ae5dc262ea69b3813e918ad460509e99267c1795',host=host,observed_at=datetime.now(timezone.utc).isoformat(),passed=True,
    native_ctest_groups_run=5,native_ctest_groups_available=57,case_cases=82,health_cases=95,structural_checks=941,manifest_files=253,manifest_bytes=1583124,
    spec_tests=dict(run=175,passed=173,skipped=2),product_links_health=True,product_links_case=False,product_links_journals=False,implemented_commands=18,
    public_health_available=True,public_evidence_available=False,artifacts=artifacts,
    limitations=['Private in-memory fixture observation/custody builder; no file export, public case command, acquired-image integration, authenticated actors, physical source preservation or forensic qualification.',
        'Case code/fixture/target/provider identities are declarations, not authentication. Independent fixture code identity is synthetic; actual probe/source execution is bound here.',
        'Selected projection chain hashes only disclosed data; it is separate from original private custody and never authenticates it. Adapter sensitivity classification remains unqualified.',
        'Five of 57 native CTest groups rerun; the remaining 52 were not rerun at this revision. Prior frontend/storage/journal/archive evidence remains source-bound.',
        'Windows 10 Enterprise x64 tested host only; other platforms, owner acceptance and physical/independent safety qualification remain pending.',
        'Partial DE-W034 progress; native report creation/readback, public effect admission, acquisition provenance and full unit criteria remain pending.',
        'No physical query, self-test, customer access, elevation, software installation, signing, publication, remote writes or hosted-model dependency.']))
print('Clean partial DE-W034 case model PASS at '+revision,flush=True)
