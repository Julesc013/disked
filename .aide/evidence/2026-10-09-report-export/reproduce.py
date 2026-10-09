"""Clean local reproduction of the private native consent-selected report export.

Requires the recorded installed Windows compiler/SDK and Python dependencies.
No remote fetch/install, elevation, media access, physical query or publication.
Reference this retained script at the matching source checkpoint; destinations
must not exist. Different build paths/timestamps are not claimed bit reproducible.
"""
import hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert revision=='46eb65c4768f4053db1fd4b3249589c331e6254c', 'Checkout the qualified source checkpoint first'
C=R/('.aide-local/goal-0.1.0/clean-report-'+revision[:8]);E=R/('.aide/evidence/2026-10-09-report-export/reproduction-'+revision[:8]);A=R/('.aide-local/artifacts/DE-W034-report-'+revision[:8])
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
run('build',['cmake','--build','--preset','windows-bootstrap','--target','disked','case_evidence_probe','health_observation_probe','provider_guard_probe','report_export_probe','file_report_export_probe','file_report_export_fault']);P=C/'build/windows-bootstrap/Release'
catalog=run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']);assert len(json.loads(catalog.stdout)['tests'])==59
native=run('focused-native',['ctest','--preset','windows-bootstrap','--output-on-failure','-R','^(evidence.export_model|evidence.file_export|evidence.case_model|health.observation_model|disked.invocation|disked.acceptance|provider_guard.positive_control)$']);assert b'0 tests failed out of 7' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('health-cases',[sys.executable,'tests/health/test_health.py','--probe',P/'health_observation_probe.exe','--root',C,'--evidence',E/'health-cases.json'])
cases=json.loads((E/'health-cases.json').read_bytes());assert cases['passed'] and cases['cases']==95 and all(x['passed'] for x in cases['observations']) and not any(cases[x] for x in ('physical_io','self_tests','provider_admitted','public_command_implemented'))
run('case-cases',[sys.executable,'tests/evidence/test_case.py','--probe',P/'case_evidence_probe.exe','--root',C,'--evidence',E/'case-cases.json'])
case_cases=json.loads((E/'case-cases.json').read_bytes());assert case_cases['passed'] and case_cases['cases']==82 and all(x['passed'] for x in case_cases['observations']) and not any(case_cases[x] for x in ('physical_io','file_export','public_evidence_command','origin_authenticated'))
run('export-cases',[sys.executable,'tests/evidence/test_export.py','--probe',P/'report_export_probe.exe','--root',C,'--evidence',E/'export-cases.json'])
exports=json.loads((E/'export-cases.json').read_bytes());assert exports['passed'] and exports['cases']==53 and not exports['file_io'] and not exports['public_command']
run('file-export-cases',[sys.executable,'tests/evidence/test_file_export.py','--probe',P/'file_report_export_probe.exe','--fault',P/'file_report_export_fault.exe','--root',C,'--evidence',E/'file-export-cases.json'])
files=json.loads((E/'file-export-cases.json').read_bytes());assert files['passed'] and files['cases']==53 and len(files['process_observations'])==4 and not files['physical_io'] and not files['public_command']
check=run('check',[sys.executable,'spec/tools/specctl.py','check']);assert json.loads(check.stdout)['checks']==943
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);assert manifest['files']==254 and manifest['bytes']==1594840
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-report','--byte-budget','350000'])
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-report'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes());assert identity['identity']['source_state']=='clean' and identity['identity']['source_revision']==revision and len(identity['inputs'])==278 and all(sha(C/name)==digest for name,digest in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
private=('disked_journal_prototype','disked_plan_prototype','disked_guarded_model','disked_journal_semantics','disked_model_journal_producer','disked_case_evidence','disked_report_export','disked_file_report_export')
assert deps and all(not any(lib in x for lib in private) and 'disked_health_observation' in x for x in deps);(E/'product-link-closure.log').write_bytes(('\n'.join(deps)+'\n').encode())
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','report_export_probe','file_report_export_probe','file_report_export_fault'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=run('launch',[P/'disked.exe','build','inspect','--json']);assert json.loads(launch.stdout)['result']['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert len([c for c in discovery if c['availability']=='available'])==18 and next(c for c in discovery if c['id']=='health.assess')['availability']=='available' and next(c for c in discovery if c['id']=='evidence.export')['availability']!='available'
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v']);assert b'Ran 175 tests' in spec.stderr and b'skipped=2' in spec.stderr
artifacts=[]
for name in ('disked.exe','report_export_probe.exe','file_report_export_probe.exe','file_report_export_fault.exe','disked_report_export.lib','disked_file_report_export.lib','case_evidence_probe.exe','disked_case_evidence.lib','health_observation_probe.exe','disked_health_observation.lib','disked_hash.lib','disked_json.lib'):
    path=A/name;shutil.copyfile(P/name,path);artifacts.append(dict(path=path.relative_to(R).as_posix(),sha256=sha(path),bytes=path.stat().st_size))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(source=identity,base_revision='4c9f2e13f378b3f5ad4748d1de6f3c8b499a4572',host=host,observed_at=datetime.now(timezone.utc).isoformat(),passed=True,
    native_ctest_groups_run=7,native_ctest_groups_available=59,export_cases=53,file_export_cases=53,export_process_observations=4,case_cases=82,health_cases=95,
    structural_checks=943,manifest_files=254,manifest_bytes=1594840,spec_tests=dict(run=175,passed=173,skipped=2),
    product_links_health=True,product_links_case=False,product_links_export=False,product_links_journals=False,implemented_commands=18,public_evidence_available=False,artifacts=artifacts,
    limitations=['Private typed fixture support-file export; no public evidence.export, admitted case repository, acquisition/custody integration or physical qualification.',
        'Native creation/flush/readback and directory/producers sharing verified only on the recorded Windows host. The report adapter strengthens its own ancestor handles; the shared image/acquisition metadata-only helper requires follow-up audit/repair before further image effects.',
        'Fault seams and an owned-child cut are not real full-filesystem, power-loss, worker containment or all-allocation failure qualification.',
        'Case/actor/code declarations remain unauthenticated; artifact identity verifies selected bytes only. Routing/producer receipts are not redacted support exports.',
        'Seven of 59 native groups rerun; other 52 groups and additional platforms not rerun at this source revision. Prior evidence remains source-bound.',
        'DE-W034 and full DiskEd 0.1.0 remain incomplete. Owner acceptance, physical devices, elevation, customer data, installation, signing and publication remain separate. No remote writes.']))
print('Clean partial DE-W034 native report export PASS at '+revision,flush=True)
