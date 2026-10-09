"""Clean local Windows reproduction of private report-worker admission/state.

Uses installed compiler/Python and a fresh local clone; no fetch/installation,
physical devices, elevation, customer data, signing or publication. Existing
owned paths are never deleted or reused. Failure logs and dependencies remain.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args()
revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert revision==a.source and len(revision)==40
C=R/('.aide-local/goal-0.1.0/clean-report-'+revision[:8]);E=R/('.aide/evidence/2026-10-09-report-worker/reproduction-'+revision[:8]);A=R/('.aide-local/artifacts/DE-W034-report-'+revision[:8])
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no']) and not C.exists()
E.mkdir(parents=True,exist_ok=False);A.mkdir(parents=True,exist_ok=False);commands=[]
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def digest(value):return 'sha256:'+hashlib.sha256(value).hexdigest()
def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def run(name,argv,cwd=C,limit=120):
    argv=[str(x) for x in argv];result=subprocess.run(argv,capture_output=True,cwd=cwd,timeout=limit);path=E/('clean-'+name+'.log');path.write_bytes(result.stdout+result.stderr)
    commands.append(dict(command=subprocess.list2cmdline(argv),cwd=str(cwd),exit_code=result.returncode,status='pass' if not result.returncode else 'fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands)
    print(name+' exit '+str(result.returncode),flush=True)
    if result.returncode:raise RuntimeError(name+' failed; log retained')
    return result
host_command="$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$principal=[System.Security.Principal.WindowsPrincipal]::new($identity);$os=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$identity.Name;elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$os.Caption;version=$os.Version;build=$os.BuildNumber;architecture=$os.OSArchitecture}|ConvertTo-Json -Compress"
host=json.loads(run('host',['powershell','-NoProfile','-Command',host_command],R).stdout);assert host['identity']=='BLACKGLASS-WIN1\\Jules' and host['elevated'] is False
run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],R)
run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
run('configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build','--preset','windows-bootstrap','--parallel','4'],limit=900);P=C/'build/windows-bootstrap/Release'
catalog=json.loads(run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']).stdout);selected=[t['name'] for t in catalog['tests']];assert len(selected)==64
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1500);assert b'0 tests failed out of 64' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('report-cases',[sys.executable,'tests/evidence/test_report_worker.py','--probe',P/'report_worker_probe.exe','--fault',P/'report_worker_fault.exe','--product',P/'disked.exe','--root',C,'--evidence',E/'report-cases.json'])
cases=json.loads((E/'report-cases.json').read_bytes());assert cases['status']=='PASS' and cases['checks']==176 and len(cases['samples'])==6 and len(cases['outputs'])==4 and all(x['passed'] for x in cases['observations'])
sample=cases['samples'][0];body=sample['artifact_bytes'].encode();definition=sample['definition']['definition'];desc=definition['export']['effect']['artifact'];out=sample['observation']['value']['state']['outcome']
assert digest(encode(definition))==sample['definition']['definition_digest'] and body==encode(json.loads(body))+b'\n'
assert digest(body)==desc['digest'] and len(body)==int(desc['bytes']) and out['status']=='completed' and out['output']['verified_bytes']==desc['bytes']
assert sample['observation']['value']['state']['receipt']['output_receipt']['artifact_digest']==desc['digest']
write(E/'sample-hash-check.json',dict(passed=True,definition_digest=sample['definition']['definition_digest'],artifact_sha256=digest(body),artifact_bytes=len(body),scope='Generated private report execution definition/state and selected support bytes; no authenticated custody or current-image/physical admission.'))
(E/'sample-support.json').write_bytes(body)
check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout);assert check['checks']==959 and check['schemas']==54
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);assert manifest['files']==262 and manifest['bytes']==1671909
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
context=json.loads(run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-report','--byte-budget','450000']).stdout)
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-report'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes());assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean' and len(identity['inputs'])==307
assert all(sha(C/name)==expected for name,expected in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
private=('disked_journal_prototype','disked_plan_prototype','disked_guarded_model','disked_journal_semantics','disked_model_journal_producer','disked_case_evidence','disked_report_export','disked_file_report_export','disked_file_case_source','disked_file_acquisition_export')
assert deps and all(not any(lib in x for lib in private) for x in deps)
assert all('report_worker.cpp' not in (x.attrib.get('Include') or '') for x in project.iter());(E/'product-link-closure.log').write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','report_worker_probe','report_worker_fault'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result'];assert launch['version']=='0.1.0-dev.27' and launch['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert sum(c['availability']=='available' for c in discovery)==18 and next(c for c in discovery if c['id']=='evidence.export')['availability']!='available'
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],limit=300);assert b'Ran 175 tests' in spec.stderr and b'skipped=2' in spec.stderr
native_artifacts=[dict(path=f.relative_to(C).as_posix(),bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(P.glob('*.exe'))];write(E/'native-artifacts.json',native_artifacts)
artifacts=[]
for name in ('disked.exe','report_worker_probe.exe','report_worker_fault.exe','disked_report_export.lib','disked_file_acquisition_export.lib','disked_case_evidence.lib','disked_file_case_source.lib','disked_file_report_export.lib'):
    path=A/name;shutil.copyfile(P/name,path);artifacts.append(dict(path=path.relative_to(R).as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,source=identity,base_revision='d1f1cc8978ac13e1ac744442f3037cb6f9662547',host=host,observed_at=datetime.now(timezone.utc).isoformat(),
    native_ctest_groups_run=64,native_ctest_groups_available=64,selected_native_groups=selected,report_worker_checks=176,actual_acquisition_copies=1,actual_report_outputs=5,retained_failed_or_cancelled_outputs=2,
    structural_checks=959,manifest_files=262,manifest_bytes=1671909,context_bytes=context['bytes'],spec_tests=dict(run=175,passed=173,skipped=2),implemented_commands=18,public_evidence_available=False,
    product_links_case=False,product_links_export=False,product_links_report_worker=False,product_links_journals=False,artifacts=artifacts,
    limitations=['Private same-executable role in dedicated native probes. Product/report common service, watch, public parameters/results/descriptors and CLI/stdio/GUI/TUI/shell journeys remain pending. Full DE-W034 and all-platform/storage DiskEd 0.1.0 are incomplete.',
        'Delays, cancellation after actual file creation and injected full/short metadata writes are process/API observations. No real full filesystem, power-loss, physical storage, other host/platform or authenticated actor qualification.',
        'Terminal quiescence records provider-handle release; actual process identity/exit is observed separately. A failed terminal record retains executing/uncertain state alongside independently verified output bytes; no automatic restart/deletion.',
        'Review/state/header/receipt samples contain generated private paths and original metadata. Only sample-support.json is the selected redacted payload. Retained case statements do not verify current acquired images or preservation.',
        'Current-user ACL, host applicability and resource observations do not establish isolation from a compromised same-user process or a privileged-writer fence. Owner acceptance and physical/elevation/customer/install/signing/publication/release gates remain separate.']))
print('Clean partial DE-W034 private report-worker PASS at '+revision,flush=True)
