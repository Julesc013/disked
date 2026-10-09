"""Clean local reproduction of worker-state directory coordination and creation facts.

Requires the recorded installed Windows compiler/SDK and Python dependencies.
No remote fetch/install, elevation, media access, physical query or publication.
Reference this retained script at the matching source checkpoint; destinations
must not exist. Different build paths/timestamps are not claimed bit reproducible.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);args=parser.parse_args()
assert revision==args.source and len(revision)==40, 'Checkout the qualified source checkpoint first'
C=R/('.aide-local/goal-0.1.0/clean-store-'+revision[:8]);E=R/('.aide/evidence/2026-10-09-worker-store/reproduction-'+revision[:8]);A=R/('.aide-local/artifacts/DE-W033-store-'+revision[:8])
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
run('build',['cmake','--build','--preset','windows-bootstrap'],limit=900);P=C/'build/windows-bootstrap/Release'
catalog=run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']);selected=[x['name'] for x in json.loads(catalog.stdout)['tests']];assert len(selected)==61
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1200);assert b'0 tests failed out of 61' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('directory-cases',[sys.executable,'tests/operation/test_worker_directory.py','--probe',P/'worker_directory_probe.exe','--root',C,'--evidence',E/'directory-cases.json'])
directories=json.loads((E/'directory-cases.json').read_bytes());assert directories['passed'] and directories['cases']==5 and directories['mode']=='fixed-helper-contract' and not directories['whole_worker_redirection_qualified']
run('worker-cases',[sys.executable,'tests/images/test_acquisition_worker.py','--probe',P/'acquisition_worker_probe.exe','--fault',P/'acquisition_worker_fault.exe','--root',C,'--evidence',E/'worker-cases.json'])
workers=json.loads((E/'worker-cases.json').read_bytes());assert workers['all_passed'] and workers['checks']==len(workers['observations']) and all(x['passed'] for x in workers['observations']) and sum('outcome' in x for x in workers['workers'])==10
run('store-failure-cases',[sys.executable,'tests/resilience/test_store_failures.py','--exe',P/'disked.exe','--fault',P/'disked_store_fault.exe','--evidence',E/'store-failure-cases.json'])
faults=json.loads((E/'store-failure-cases.json').read_bytes());assert faults['passed'] and faults['tests']==7 and not faults['failures']
check=run('check',[sys.executable,'spec/tools/specctl.py','check']);assert json.loads(check.stdout)['checks']==945
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);assert manifest['files']==255 and manifest['bytes']==1610139
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W033','--output','.aide-local/context/DE-W033-store','--byte-budget','450000'])
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W033-store'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes());assert identity['identity']['source_state']=='clean' and identity['identity']['source_revision']==revision and len(identity['inputs'])==282 and all(sha(C/name)==digest for name,digest in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
private=('disked_journal_prototype','disked_plan_prototype','disked_guarded_model','disked_journal_semantics','disked_model_journal_producer','disked_case_evidence','disked_report_export','disked_file_report_export')
assert deps and all(not any(lib in x for lib in private) and 'disked_health_observation' in x for x in deps);(E/'product-link-closure.log').write_bytes(('\n'.join(deps)+'\n').encode())
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','worker_directory_probe','acquisition_worker_fault','disked_store_fault'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=run('launch',[P/'disked.exe','build','inspect','--json']);assert json.loads(launch.stdout)['result']['source_revision']==revision and json.loads(launch.stdout)['result']['version']=='0.1.0-dev.24'
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert len([c for c in discovery if c['availability']=='available'])==18 and next(c for c in discovery if c['id']=='health.assess')['availability']=='available' and next(c for c in discovery if c['id']=='evidence.export')['availability']!='available'
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v']);assert b'Ran 175 tests' in spec.stderr and b'skipped=2' in spec.stderr
artifacts=[]
for name in ['disked.exe','worker_directory_probe.exe','acquisition_worker_probe.exe','acquisition_worker_fault.exe','disked_store_fault.exe','acquisition_command_probe.exe','disked_local_file.lib','disked_file_acquisition.lib']:
    path=A/name;shutil.copyfile(P/name,path);artifacts.append(dict(path=path.relative_to(R).as_posix(),sha256=sha(path),bytes=path.stat().st_size))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(source=identity,base_revision='0f61342349b14eb57d61de592d1a61c094ed8c46',host=host,observed_at=datetime.now(timezone.utc).isoformat(),passed=True,
    native_ctest_groups_run=len(selected),native_ctest_groups_available=61,selected_native_groups=selected,directory_cases=5,acquisition_worker_checks=workers['checks'],verified_worker_copies=10,store_failure_tests=7,
    structural_checks=945,manifest_files=255,manifest_bytes=1610139,spec_tests=dict(run=175,passed=173,skipped=2),
    product_links_health=True,product_links_case=False,product_links_export=False,product_links_journals=False,implemented_commands=18,public_evidence_available=False,artifacts=artifacts,
    limitations=['The baseline observation exercised the exact private Directory helper, not a full-worker redirection. It allowed leaf-state rename/replacement and refused ancestor rename; retained separately from fixed qualification.',
        'Five focused native cases verify live rename refusals, real directory/ancestor creation-time changes and metadata-only permission refusal on the recorded Windows host. No physical namespace/drive-alias fence or elevated/external-writer qualification.',
        'Successful CREATE_NEW facts are retained before later validation. Injected post-creation failure leaves actual partial files and unknown fake/acquisition admission identities; such injection is not an actual hardware/API failure.',
        'All 61 available Windows native CTest groups rerun, including actual worker, GUI/TUI/shell, owned-file, private model and artifact checks. Other hosts/platforms, physical storage, power loss and full-filesystem exhaustion remain unverified.',
        'Existing private persisted store identity/generation fields remain unchanged; per-session ancestor guards do not establish cross-session ancestry continuity. Old maps retain same-code resume restrictions.',
        'Public evidence.export remains unavailable; private case/export and five journal libraries remain unlinked. DE-W033/017/034 and full DiskEd 0.1.0 are incomplete.',
        'Owner acceptance, physical devices, elevation, customer data, installation, signing and publication remain separate. No remote writes.']))
print('Clean partial DE-W033/017 worker-store coordination PASS at '+revision,flush=True)
