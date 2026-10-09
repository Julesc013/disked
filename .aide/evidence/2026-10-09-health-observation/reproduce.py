"""Clean local reproduction of the private health-observation/redaction model.

Requires the recorded installed Windows compiler/SDK and Python dependencies.
No remote fetch/install, elevation, media access, physical query or publication.
Reference this retained script at the matching source checkpoint; destinations
must not exist. Different build paths/timestamps are not claimed bit reproducible.
"""
import hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
C=R/('.aide-local/goal-0.1.0/clean-health-'+revision[:8]);E=R/('.aide/evidence/2026-10-09-health-observation/reproduction-'+revision[:8]);A=R/('.aide-local/artifacts/DE-W032-'+revision[:8])
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
run('build',['cmake','--build','--preset','windows-bootstrap','--target','disked','health_observation_probe','provider_guard_probe']);P=C/'build/windows-bootstrap/Release'
catalog=run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']);assert len(json.loads(catalog.stdout)['tests'])==55
native=run('focused-native',['ctest','--preset','windows-bootstrap','--output-on-failure','-R','^(health.observation_model|disked.invocation|disked.acceptance|provider_guard.positive_control)$']);assert b'0 tests failed out of 4' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('health-cases',[sys.executable,'tests/health/test_health.py','--probe',P/'health_observation_probe.exe','--root',C,'--evidence',E/'health-cases.json'])
cases=json.loads((E/'health-cases.json').read_bytes());assert cases['passed'] and cases['cases']==95 and all(x['passed'] for x in cases['observations']) and not any(cases[x] for x in ('physical_io','self_tests','provider_admitted','public_command_implemented'))
check=run('check',[sys.executable,'spec/tools/specctl.py','check']);assert json.loads(check.stdout)['checks']==935
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);assert manifest['files']==250 and manifest['bytes']==1558504
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W032','--output','.aide-local/context/DE-W032-health','--byte-budget','350000'])
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W032-health'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes());assert identity['identity']['source_state']=='clean' and identity['identity']['source_revision']==revision and len(identity['inputs'])==258 and all(sha(C/name)==digest for name,digest in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
private=('disked_journal_prototype','disked_plan_prototype','disked_guarded_model','disked_journal_semantics','disked_model_journal_producer','disked_health_observation')
assert deps and all(not any(lib in x for lib in private) for x in deps);(E/'product-link-closure.log').write_bytes(('\n'.join(deps)+'\n').encode())
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','health_observation_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=run('launch',[P/'disked.exe','build','inspect','--json']);assert json.loads(launch.stdout)['result']['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert len([c for c in discovery if c['availability']=='available'])==17 and next(c for c in discovery if c['id']=='health.assess')['availability']!='available'
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v']);assert b'Ran 175 tests' in spec.stderr and b'skipped=2' in spec.stderr
artifacts=[]
for name in ('disked.exe','health_observation_probe.exe','disked_health_observation.lib','disked_json.lib'):
    path=A/name;shutil.copyfile(P/name,path);artifacts.append(dict(path=path.relative_to(R).as_posix(),sha256=sha(path),bytes=path.stat().st_size))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(source=identity,host=host,observed_at=datetime.now(timezone.utc).isoformat(),passed=True,native_ctest_groups_run=4,native_ctest_groups_available=55,health_cases=95,structural_checks=935,manifest_files=250,manifest_bytes=1558504,spec_tests=dict(run=175,passed=173,skipped=2),product_links_health=False,product_links_journals=False,implemented_commands=17,public_health_available=False,artifacts=artifacts,
    limitations=['Private serialized declaration reducer and test-owned values; no real provider, device query, self-test, OS worker containment, file I/O, health/reliability guarantee or forensic admission.',
    'Default support projection omits content/identity; explicit policy and fixed request classification do not establish future adapter classification correctness.',
    'Four of 55 CTest groups rerun; other 51 native groups not rerun at this revision. Prior runtime/journal/archive evidence remains source-bound.',
    'Windows 10 x64 tested host only; other platforms/physical observations, owner acceptance and independent safety qualification remain pending.',
    'Partial DE-W032 progress: actual read-only adapters and public command still require their contracts, containment, inventory and admission evidence. No installation/signing/publication/remote writes.']))
print('Clean partial DE-W032 health model PASS at '+revision,flush=True)
