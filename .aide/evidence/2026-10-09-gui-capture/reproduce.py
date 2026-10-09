"""Reproduce native owned GUI capture repair using installed tools and owned files.

Fresh local clone, generated acquisition/report fixtures and unelevated processes.
No network fetch, path reuse, installation, signing or physical/customer media.
Run native suites sequentially: CTest locks do not cover external harnesses.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path

R=Path.cwd();parser=argparse.ArgumentParser();parser.add_argument('--source',required=True);args=parser.parse_args()
revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert revision==args.source and len(revision)==40
C=R/('.aide-local/goal-0.1.0/clean-gui-capture-'+revision[:8])
E=R/('.aide/evidence/2026-10-09-gui-capture/reproduction-'+revision[:8])
A=R/('.aide-local/artifacts/DE-W015-gui-capture-'+revision[:8])
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'])
assert not C.exists() and not E.exists() and not A.exists()
E.mkdir(parents=True);A.mkdir(parents=True);commands=[]

def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def digest(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def sha(path):return digest(path.read_bytes())
def encode(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def run(name,argv,cwd=C,limit=120):
    argv=[str(x) for x in argv];start=datetime.now(timezone.utc).isoformat()
    result=subprocess.run(argv,capture_output=True,cwd=cwd,timeout=limit)
    path=E/('clean-'+name+'.log');path.write_bytes(result.stdout+result.stderr)
    commands.append(dict(command=argv,cwd=str(cwd),started_at=start,exit_code=result.returncode,
        status='pass' if not result.returncode else 'fail',evidence_path=path.relative_to(R).as_posix()))
    write(E/'commands.json',commands);print(name+' exit '+str(result.returncode),flush=True)
    if result.returncode:raise RuntimeError(name+' failed; log and fixtures retained')
    return result

host_command="$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$principal=[System.Security.Principal.WindowsPrincipal]::new($identity);$os=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$identity.Name;elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$os.Caption;version=$os.Version;build=$os.BuildNumber;architecture=$os.OSArchitecture}|ConvertTo-Json -Compress"
host=json.loads(run('host',['powershell','-NoProfile','-Command',host_command],R).stdout)
assert host['identity']=='BLACKGLASS-WIN1\\Jules' and host['elevated'] is False
run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],R)
run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
run('configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build','--preset','windows-bootstrap','--parallel','4'],limit=900)
P=C/'build/windows-bootstrap/Release'
catalog=json.loads(run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']).stdout)
selected=[t['name'] for t in catalog['tests']]
assert len(selected)==69 and all(n in selected for n in ('frontend.gui_capture','frontend.gui_windows','frontend.product_export'))
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1500)
assert b'0 tests failed out of 69' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('product-export',[sys.executable,'tests/frontend/test_product_export.py','--product',P/'disked.exe',
    '--fault',P/'disked_report_test.exe','--root',C,'--evidence',E/'product-export.json'],limit=200)
cases=json.loads((E/'product-export.json').read_bytes())
assert cases['checks']>=100 and len(cases['verified_outputs'])==6
assert all(x['passed'] for x in cases['observations']) and not cases['source_dirty'] and cases['source_revision']==revision
assert {x['frontend'] for x in cases['verified_outputs']}=={'cli','stdio','gui','tui','shell','stdio-private-timeout'}
assert {x['frontend'] for x in cases['native_journeys']}=={'gui','tui','shell','stdio'}
sample=cases['samples'][0];definition=sample['definition'];body=encode(sample['support'])+b'\n'
artifact=definition['export']['effect']['artifact'];state=sample['result']['state'];header=sample['header']
assert digest(encode(definition))==header['definition_digest'] and digest(body)==artifact['digest'] and len(body)==int(artifact['bytes'])
assert state==sample['rows'][-1]['state'] and state['outcome']['status']=='completed'
assert state['outcome']['output']['verified_bytes']==artifact['bytes']
previous='0'*64
for index,row in enumerate(sample['rows'],1):
    assert row['state']['sequence']==str(index) and row['previous']==previous
    assert digest(encode({k:v for k,v in row.items() if k!='digest'}))=='sha256:'+row['digest'];previous=row['digest']
    for key in ('operation_id','attempt_id','worker_epoch'):assert row['state']['binding'][key]==header[key]
gate=next(x for x in cases['native_journeys'] if x.get('phase')=='occupied-timeout-gate')
assert gate['expired']['status']=='unknown' and gate['expired']['result']['definition_digest']
assert gate['expired']['result']['state_directory'] and gate['cached']['status']=='completed'
assert gate['busy']['diagnostics'][0]['code']=='request_resource_limit' and gate['reconciled']['operation_id']
(E/'sample-support.json').write_bytes(body)
write(E/'sample-hash-check.json',dict(passed=True,artifact_sha256=digest(body),artifact_bytes=len(body),
    definition_digest=digest(encode(definition)),verified_row_digests=len(sample['rows']),
    scope='Independent generated support bytes and retained producer history; not authenticated custody or current acquired-image verification.'))
run('gui-capture',[sys.executable,'tests/frontend/test_gui_capture.py','--product',P/'disked.exe','--root',C,'--evidence',E/'gui-capture.json'])
capture=json.loads((E/'gui-capture.json').read_bytes());assert capture['passed'] and capture['checks']==24 and len(capture['captures'])==6
assert capture['source_revision']==revision and not capture['source_dirty'] and capture['executable_sha256']==sha(P/'disked.exe')
run('gui-windows',[sys.executable,'tests/frontend/test_gui_windows.py','--exe',P/'disked.exe','--guard',P/'disked_provider_guard.exe',
    '--unavailable',P/'disked_gui_unavailable.exe','--evidence',E/'gui-observations.json'])
run('report-process-identity',[sys.executable,'tests/evidence/test_report_process.py','--evidence',E/'report-process-identity.json'])
process_checks=json.loads((E/'report-process-identity.json').read_bytes());assert process_checks['passed'] and process_checks['checks']==7
check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout)
assert check['status']=='PASS' and check['schemas']==60
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout)
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
context=json.loads(run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W015',
    '--output','.aide-local/context/DE-W015-gui-capture','--byte-budget','500000']).stdout)
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W015-gui-capture'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean'
assert len(identity['inputs'])==331 and all(sha(C/name)==expected for name,expected in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj')
deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
linked=('disked_case_evidence','disked_report_export','disked_file_case_source',
    'disked_file_acquisition_export','disked_export_commands','disked_report_observation')
excluded=('disked_journal_prototype','disked_plan_prototype','disked_guarded_model','disked_journal_semantics','disked_model_journal_producer')
assert deps and all(any(lib in x for x in deps) for lib in linked)
assert all(not any(lib in x for lib in excluded) for x in deps)
assert any('report_worker.cpp' in (x.attrib.get('Include') or '') for x in project.iter())
(E/'product-link-closure.log').write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','disked_report_test','export_command_probe','export_command_fault'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result']
assert launch['version']=='0.1.0-dev.31' and launch['source_revision']==revision
assert launch['report_provider']=='provider.report.acquisition-case.prototype/1'
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands']
assert sum(c['availability']=='available' for c in discovery)==19
export=next(c for c in discovery if c['id']=='evidence.export')
assert export['availability']=='available' and export['implementation_status']=='implemented' and export['contract_status']=='planned'
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],limit=300)
assert b'Ran 185 tests' in spec.stderr and b'skipped=2' in spec.stderr
write(E/'native-artifacts.json',[dict(path=f.relative_to(C).as_posix(),bytes=f.stat().st_size,sha256=sha(f)) for f in sorted(P.glob('*.exe'))])
artifacts=[]
for name in ('disked.exe','disked_report_test.exe','export_command_probe.exe','export_command_fault.exe',
    'disked_export_commands.lib','disked_report_export.lib','disked_file_acquisition_export.lib','disked_report_observation.lib'):
    path=A/name;shutil.copyfile(P/name,path)
    artifacts.append(dict(path=path.relative_to(R).as_posix(),bytes=path.stat().st_size,sha256=sha(path)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,source=identity,base_revision='79807daa7ea86a2e87a20f4ec2333c398308d866',
    host=host,observed_at=datetime.now(timezone.utc).isoformat(),native_ctest_groups_run=69,selected_native_groups=selected,
    report_process_identity_checks=process_checks['checks'],gui_capture_checks=capture['checks'],actual_gui_captures=6,product_export_checks=cases['checks'],actual_acquisition_copies=1,actual_report_outputs=6,actual_frontends=['cli','stdio','gui','tui','shell'],
    actual_occupied_callback_timeout=True,structural_checks=check['checks'],manifest=manifest,context_bytes=context['bytes'],
    spec_tests=dict(run=185,passed=183,skipped=2),implemented_commands=19,public_evidence_available=True,
    product_links_case=True,product_links_export=True,product_links_export_commands=True,product_links_report_worker=True,
    product_links_report_observation=True,product_links_journals=False,artifacts=artifacts,
    limitations=['Owned client paint guard is not complete text/layout/accessibility/DPI or other-platform qualification. Full DE-W034 and all specified 0.1.0 platforms/storage remain incomplete. Export covers only retained generated acquisition case metadata and support JSON; no full case/custody/health-before-after workflow.',
        'Actual five-frontend execution, watch and reconnect are separate from private fault gates and synthetic reader/semantic probes. One actual timed-out callback remains occupied until its completion; explicit reconciliation does not replay its effect.',
        'Finite follow bounds deliberate polling, not blocked Windows API latency. Response/event/render quotas remain finite; Windows argv, public envelope and admitted 64 KiB typed definitions are distinct limits.',
        'Historical compatible observation does not grant a different/retired executable writer authority. Definitions and receipts contain generated routing metadata; only sample-support.json is the selected default-redacted payload.',
        'No authenticated custody/actor, current acquired-image verification, stable public ABI, power-loss or physical/other-platform qualification. Static imports are not a complete dynamic DLL closure.',
        'Owner acceptance, physical/elevation/customer/install/signing/publication/release gates remain separate.']))
print('Clean partial DE-W015 capture repair PASS at '+revision,flush=True)
