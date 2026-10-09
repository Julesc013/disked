"""Clean local reproduction of joint case/source/export admission.

Installed recorded Windows compiler/dependencies only. Fresh owned paths must
not exist; no remote fetch/install, physical/elevated/customer/release actions.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args();assert revision==a.source and len(revision)==40
C=R/('.aide-local/goal-0.1.0/clean-joint-'+revision[:8]);E=R/('.aide/evidence/2026-10-09-joint-export/reproduction-'+revision[:8]);A=R/('.aide-local/artifacts/DE-W034-joint-'+revision[:8])
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
catalog=json.loads(run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']).stdout);selected=[t['name'] for t in catalog['tests']];assert len(selected)==63
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1500);assert b'0 tests failed out of 63' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('joint-cases',[sys.executable,'tests/evidence/test_acquisition_export.py','--probe',P/'acquisition_export_probe.exe','--fault',P/'acquisition_export_fault.exe','--product',P/'disked.exe','--root',C,'--evidence',E/'joint-cases.json'])
cases=json.loads((E/'joint-cases.json').read_bytes());assert cases['passed'] and cases['checks']==116 and len(cases['actual_acquisition_copies'])==1 and len(cases['actual_exports'])==3 and len(cases['native_events'])==3 and all(x['passed'] for x in cases['observations'])
sys.path.insert(0,str(C/'tests/evidence'));from test_case import encode,digest
sample=cases['sample'];body=sample['artifact_bytes'].encode();support=json.loads(body);desc=sample['definition']['effect']['artifact']
assert digest(encode(sample['definition']))==sample['definition_digest']
assert digest(body)==desc['digest'] and body==encode(support)+b'\n' and len(body)==int(desc['bytes'])
assert sample['outcome']['status']=='completed' and sample['outcome']['source_state']=='matched' and sample['outcome']['output']['verified_bytes']==str(len(body))
assert sample['receipt']['output_receipt']['output_created_observed'] and sample['receipt']['output_receipt']['artifact_digest']==desc['digest']
write(E/'sample-hash-check.json',dict(passed=True,definition_digest=sample['definition_digest'],artifact_sha256=digest(body),artifact_bytes=len(body),scope='Generated private joint review/receipt and selected artifact bytes; no authenticated actor/current image/physical admission.'))
(E/'sample-support.json').write_bytes(body)
assert json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout)['checks']==953
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);assert manifest['files']==259 and manifest['bytes']==1652455
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-joint','--byte-budget','450000'])
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-joint'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes());assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean' and len(identity['inputs'])==298
assert all(sha(C/name)==expected for name,expected in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
private=('disked_journal_prototype','disked_plan_prototype','disked_guarded_model','disked_journal_semantics','disked_model_journal_producer','disked_case_evidence','disked_report_export','disked_file_report_export','disked_file_case_source','disked_file_acquisition_export')
assert deps and all(not any(lib in x for lib in private) and 'disked_health_observation' in x for x in deps);(E/'product-link-closure.log').write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','acquisition_export_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result'];assert launch['version']=='0.1.0-dev.26' and launch['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert sum(c['availability']=='available' for c in discovery)==18 and next(c for c in discovery if c['id']=='evidence.export')['availability']!='available'
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v']);assert b'Ran 175 tests' in spec.stderr and b'skipped=2' in spec.stderr
artifacts=[]
for name in ('disked.exe','acquisition_export_probe.exe','acquisition_export_fault.exe','acquisition_case_probe.exe','file_report_export_probe.exe','file_report_export_fault.exe','report_export_probe.exe','disked_file_acquisition_export.lib','disked_case_evidence.lib','disked_file_case_source.lib','disked_report_export.lib','disked_file_report_export.lib'):
    path=A/name;shutil.copyfile(P/name,path);artifacts.append(dict(path=path.relative_to(R).as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,source=identity,base_revision='65134c4c2f4f9dfd3b0ed9029b0eb75884e38add',host=host,observed_at=datetime.now(timezone.utc).isoformat(),
    native_ctest_groups_run=63,native_ctest_groups_available=63,selected_native_groups=selected,joint_export_checks=116,actual_acquisition_copies=1,actual_completed_or_retained_outputs=3,native_generation_events=3,
    structural_checks=953,manifest_files=259,manifest_bytes=1652455,spec_tests=dict(run=175,passed=173,skipped=2),implemented_commands=18,public_evidence_available=False,
    product_links_case=False,product_links_export=False,product_links_case_source=False,product_links_joint_export=False,product_links_journals=False,artifacts=artifacts,
    limitations=['Recorded Windows ordinary-process/API behavior only; other platforms, physical storage, power loss and authenticated custody remain unqualified.',
        'Joint source checks are observations, not atomic multi-resource snapshots or a privileged-writer fence. Case statements do not verify current image or source preservation; actual generated acquisition byte/map check is independent test evidence.',
        'Late-source/completed-output and executor-throw cases are pure models. Native generation changes are actual metadata-only writes in coordinated prepared/created/read events of the same fault child; no restart or cleanup of unfinished dependencies.',
        'Surrounding sample definition/routing receipt contains original generated metadata; sample-support.json alone is consent-selected support.',
        'Public worker/code/store identity, reconnect, parameter/result/descriptor contracts, bounded shared service/cancellation/late results and actual CLI/stdio/GUI/TUI/shell parity remain pending. Full DE-W034 and all-platform/storage DiskEd 0.1.0 are incomplete; owner acceptance remains separate.']))
print('Clean partial DE-W034 joint source/case/export PASS at '+revision,flush=True)
