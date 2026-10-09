"""Clean local reproduction of typed recorded-acquisition case/source/export.

Run from the matching committed source with the installed recorded toolchain.
Unique clone/evidence/artifact paths must not exist. No remote fetch/install,
physical access, elevation, customer data, signing or publication. Build paths
and timestamps are not claimed bit reproducible.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args();assert revision==a.source and len(revision)==40
C=R/('.aide-local/goal-0.1.0/clean-case-'+revision[:8]);E=R/('.aide/evidence/2026-10-09-acquisition-cases/reproduction-'+revision[:8]);A=R/('.aide-local/artifacts/DE-W034-cases-'+revision[:8])
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no']) and not C.exists()
E.mkdir(parents=True,exist_ok=False);A.mkdir(parents=True,exist_ok=False);commands=[]
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def run(name,args,cwd=C,limit=420):
    argv=[str(x) for x in args];print('Running clean '+name,flush=True);path=E/('clean-'+name+'.log')
    try:result=subprocess.run(argv,cwd=cwd,capture_output=True,timeout=limit)
    except subprocess.TimeoutExpired as error:
        path.write_bytes((error.stdout or b'')+(error.stderr or b''));commands.append(dict(command=subprocess.list2cmdline(argv),cwd=str(cwd),exit_code=None,status='fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands);raise
    path.write_bytes(result.stdout+result.stderr);commands.append(dict(command=subprocess.list2cmdline(argv),cwd=str(cwd),exit_code=result.returncode,status='pass' if not result.returncode else 'fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands)
    print(name+' exit '+str(result.returncode),flush=True)
    if result.returncode:raise RuntimeError(name+' failed; log retained')
    return result
host_command="$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$principal=[System.Security.Principal.WindowsPrincipal]::new($identity);$os=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$identity.Name;elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$os.Caption;version=$os.Version;build=$os.BuildNumber;architecture=$os.OSArchitecture}|ConvertTo-Json -Compress"
host=json.loads(run('host',['powershell','-NoProfile','-Command',host_command],R).stdout);assert host['identity']=='BLACKGLASS-WIN1\\Jules' and host['elevated'] is False
run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],R)
run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
run('configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build','--preset','windows-bootstrap'],limit=900);P=C/'build/windows-bootstrap/Release'
catalog=json.loads(run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']).stdout);selected=[t['name'] for t in catalog['tests']];assert len(selected)==62
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1500);assert b'0 tests failed out of 62' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('case-cases',[sys.executable,'tests/evidence/test_acquisition_case.py','--probe',P/'acquisition_case_probe.exe','--product',P/'disked.exe','--worker-fault',P/'acquisition_worker_fault.exe','--root',C,'--evidence',E/'case-cases.json'])
cases=json.loads((E/'case-cases.json').read_bytes());assert cases['passed'] and cases['checks']==153 and len(cases['actual_acquisition_copies'])==2 and all(x['passed'] for x in cases['observations'])
sys.path.insert(0,str(C/'tests/evidence'));from test_case import encode,digest
sample=cases['sample'];body=sample['artifact_bytes'].encode();support=json.loads(body)
assert digest(encode(sample['case']))==sample['case_revision']==sample['source_binding']['case_revision']
assert digest(body)==sample['artifact']['digest'] and body==encode(support)+b'\n' and len(body)==int(sample['artifact']['bytes'])
assert sample['case']['claims']==support['claims'] and support['claims']['current_image_verification']=='not_performed'
write(E/'sample-hash-check.json',dict(passed=True,case_revision=sample['case_revision'],artifact_sha256=digest(body),artifact_bytes=len(body),scope='Retained generated-case/private-view and selected support bytes; not physical/authenticity admission.'))
(E/'sample-support.json').write_bytes(body)
assert json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout)['checks']==947
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);assert manifest['files']==256 and manifest['bytes']==1622062
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-case','--byte-budget','450000'])
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-case'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes());assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean' and len(identity['inputs'])==289
assert all(sha(C/name)==expected for name,expected in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
private=('disked_journal_prototype','disked_plan_prototype','disked_guarded_model','disked_journal_semantics','disked_model_journal_producer','disked_case_evidence','disked_report_export','disked_file_report_export','disked_file_case_source')
assert deps and all(not any(lib in x for lib in private) and 'disked_health_observation' in x for x in deps);(E/'product-link-closure.log').write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','acquisition_case_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result'];assert launch['version']=='0.1.0-dev.25' and launch['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert sum(c['availability']=='available' for c in discovery)==18 and next(c for c in discovery if c['id']=='evidence.export')['availability']!='available'
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v']);assert b'Ran 175 tests' in spec.stderr and b'skipped=2' in spec.stderr
artifacts=[]
for name in ('disked.exe','acquisition_case_probe.exe','acquisition_worker_fault.exe','case_evidence_probe.exe','report_export_probe.exe','file_report_export_probe.exe','disked_case_evidence.lib','disked_file_case_source.lib','disked_report_export.lib','disked_file_report_export.lib'):
    path=A/name;shutil.copyfile(P/name,path);artifacts.append(dict(path=path.relative_to(R).as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,source=identity,base_revision='8e193dd07aee4e8d164719fdc874739214e1ade7',host=host,observed_at=datetime.now(timezone.utc).isoformat(),
    native_ctest_groups_run=62,native_ctest_groups_available=62,selected_native_groups=selected,acquisition_case_checks=153,actual_acquisition_copies=2,
    structural_checks=947,manifest_files=256,manifest_bytes=1622062,spec_tests=dict(run=175,passed=173,skipped=2),implemented_commands=18,public_evidence_available=False,
    product_links_case=False,product_links_export=False,product_links_case_source=False,product_links_journals=False,artifacts=artifacts,
    limitations=['Recorded Windows ordinary-process/API behavior only; other platforms, physical storage, power loss and authenticated custody remain unqualified.',
        'Case verifies captured request/history consistency, not current source/image bytes, original creator/ACL ownership, worker exit or full recovery closure. Actual two acquired source/copy/map checks are independent test observations.',
        'Content revision and current source-resource binding are distinct. Copied metadata does not inherit original store generation/file identities; per-session guards do not establish cross-session ancestry continuity.',
        'Pure-model path/header/history changes are synthetic. One real writer uses a separately compiled admission-delay seam. No raw media, elevation, customer data, signing, installation or remote writes.',
        'Surrounding sample case/source/receipt contains original generated metadata; sample-support.json alone is the policy-selected artifact.',
        'Public evidence.export exact joint case/source/effect definition, bounded service/cancellation/late-result behavior and CLI/stdio/GUI/TUI/shell parity remain pending. Full DE-W034 and DiskEd 0.1.0 are incomplete; owner acceptance remains separate.']))
print('Clean partial DE-W034 acquisition case/source PASS at '+revision,flush=True)
