"""Clean local reproduction of the provisional inward export command service.

Installed compiler/Python only; fresh local clone and owned generated fixtures.
No fetch, installation, elevation, physical/customer media, signing or publication.
Never delete or reuse an existing owned reproduction/artifact path.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args()
revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert revision==a.source and len(revision)==40
C=R/('.aide-local/goal-0.1.0/clean-export-command-'+revision[:8]);E=R/('.aide/evidence/2026-10-09-export-command/reproduction-'+revision[:8]);A=R/('.aide-local/artifacts/DE-W034-export-command-'+revision[:8])
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no']) and not C.exists()
E.mkdir(parents=True,exist_ok=False);A.mkdir(parents=True,exist_ok=False);commands=[]
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def digest(value):return 'sha256:'+hashlib.sha256(value).hexdigest()
def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def run(name,argv,cwd=C,limit=120):
    argv=[str(x) for x in argv];start=datetime.now(timezone.utc).isoformat();result=subprocess.run(argv,capture_output=True,cwd=cwd,timeout=limit);path=E/('clean-'+name+'.log');path.write_bytes(result.stdout+result.stderr)
    commands.append(dict(command=argv,cwd=str(cwd),started_at=start,exit_code=result.returncode,status='pass' if not result.returncode else 'fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands)
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
catalog=json.loads(run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']).stdout);selected=[t['name'] for t in catalog['tests']];assert len(selected)==65 and 'evidence.export_commands' in selected
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1500);assert b'0 tests failed out of 65' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('export-cases',[sys.executable,'tests/evidence/test_export_commands.py','--probe',P/'export_command_probe.exe','--fault',P/'export_command_fault.exe','--product',P/'disked.exe','--root',C,'--evidence',E/'export-cases.json'])
cases=json.loads((E/'export-cases.json').read_bytes());assert cases['checks']>=130 and len(cases['verified_outputs'])==2 and all(x['passed'] for x in cases['observations']) and not cases['source_dirty'] and cases['source_revision']==revision
sample=cases['samples'][0];definition=sample['definition'];body=encode(sample['support'])+b'\n';artifact=definition['export']['effect']['artifact'];state=sample['result']['state']
assert digest(encode(definition))==sample['header']['definition_digest'] and digest(body)==artifact['digest'] and len(body)==int(artifact['bytes'])
assert state==sample['rows'][-1]['state'] and state['outcome']['status']=='completed' and state['outcome']['output']['verified_bytes']==artifact['bytes']
cancel=next(s for s in cases['samples'] if s.get('name')=='actual-cancelled')['result']['state'];unresolved=next(s for s in cases['samples'] if s.get('name')=='actual-unresolved')['result']
assert cancel['outcome']['status']=='cancelled' and cancel['cancellation_observation']=='observed' and cancel['outcome']['output']['output_state']=='not_created'
assert unresolved['state']['phase']=='executing' and not unresolved['state']['quiescent'] and unresolved['worker_observation']=='exited'
(E/'sample-support.json').write_bytes(body);write(E/'sample-hash-check.json',dict(passed=True,artifact_sha256=digest(body),artifact_bytes=len(body),definition_digest=digest(encode(definition)),scope='Independent generated support bytes and retained state; not authenticated custody or current-image verification.'))
check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout);assert check['status']=='PASS' and check['schemas']==58
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout)
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
context=json.loads(run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-export-command','--byte-budget','500000']).stdout)
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-export-command'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes());assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean'
assert len(identity['inputs'])==317 and all(sha(C/name)==expected for name,expected in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
private=('disked_journal_prototype','disked_plan_prototype','disked_guarded_model','disked_journal_semantics','disked_model_journal_producer','disked_case_evidence','disked_report_export','disked_file_report_export','disked_file_case_source','disked_file_acquisition_export','disked_export_commands')
assert deps and all(not any(lib in x for lib in private) for x in deps)
assert all('report_worker.cpp' not in (x.attrib.get('Include') or '') for x in project.iter());(E/'product-link-closure.log').write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','export_command_probe','export_command_fault'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result'];assert launch['version']=='0.1.0-dev.29' and launch['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert sum(c['availability']=='available' for c in discovery)==18
export=next(c for c in discovery if c['id']=='evidence.export');assert export['availability']!='available' and export['syntax_status']=='defined' and export['handler'] is None
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],limit=300);assert b'Ran 178 tests' in spec.stderr and b'skipped=2' in spec.stderr
write(E/'native-artifacts.json',[dict(path=f.relative_to(C).as_posix(),bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(P.glob('*.exe'))])
artifacts=[]
for name in ('disked.exe','export_command_probe.exe','export_command_fault.exe','disked_export_commands.lib','disked_report_export.lib','disked_file_acquisition_export.lib'):
    path=A/name;shutil.copyfile(P/name,path);artifacts.append(dict(path=path.relative_to(R).as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,source=identity,base_revision='095b647a90b8fd354dc7b7fadfb2cd7bd98ebafc',host=host,observed_at=datetime.now(timezone.utc).isoformat(),
    native_ctest_groups_run=65,selected_native_groups=selected,export_command_checks=cases['checks'],actual_acquisition_copies=1,actual_report_outputs=2,actual_cancel_before_output=1,actual_lost_terminal_record=1,
    structural_checks=check['checks'],manifest=manifest,context_bytes=context['bytes'],spec_tests=dict(run=178,passed=176,skipped=2),implemented_commands=18,public_evidence_available=False,
    product_links_case=False,product_links_export=False,product_links_export_commands=False,product_links_report_worker=False,product_links_journals=False,artifacts=artifacts,
    limitations=['Private common-service probe exercises canonical parsing/request/forms and inward ports; not real product CLI/stdio/GUI/TUI/shell export journeys or bounded product watch. evidence.export remains planned, handler null. Full DE-W034 and all specified 0.1.0 platforms/storage are incomplete.',
        'Exact private code/store/case/effect binding and ordinary Windows process/API tests do not establish physical storage, other platforms, power-loss persistence, authenticated actors or current acquired-image verification.',
        'A lost terminal record remains unknown alongside independently verified actual output. Cancellation observation, retained state, provider quiescence and actual process exit remain separate. No restart/deletion.',
        'Private definitions/receipts/samples contain generated routing metadata; only sample-support.json is the selected default-redacted payload.',
        'Static dumpbin imports are observations, not a complete dynamic DLL closure. Worker source dynamically loads ADVAPI32 under the existing Windows profile.',
        'Owner acceptance, physical/elevation/customer/install/signing/publication/release gates remain separate.']))
print('Clean partial DE-W034 inward export command PASS at '+revision,flush=True)
