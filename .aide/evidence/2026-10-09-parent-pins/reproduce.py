"""Clean local reproduction of shared ordinary-file parent coordination.

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
C=R/('.aide-local/goal-0.1.0/clean-parent-'+revision[:8]);E=R/('.aide/evidence/2026-10-09-parent-pins/reproduction-'+revision[:8]);A=R/('.aide-local/artifacts/DE-W033-parent-'+revision[:8])
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
targets=['disked','disked_provider_guard','disked_gui_unavailable','disked_tui_fault','disked_image_test','provider_guard_probe','report_export_probe','file_report_export_probe','file_report_export_fault','acquisition_worker_probe','acquisition_worker_fault','acquisition_command_probe','file_acquisition_probe','file_acquisition_fault','image_file_capture_probe','image_file_capture_fault','image_observation_probe','watch_probe','shell_model_probe','gui_model_probe','tui_model_probe']
run('build',['cmake','--build','--preset','windows-bootstrap','--target',*targets]);P=C/'build/windows-bootstrap/Release'
catalog=run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']);assert len(json.loads(catalog.stdout)['tests'])==60
selected=['evidence.export_model','evidence.file_export','frontend.acquisition_forms','frontend.acquisition_interactive','image.acquisition_commands','image.acquisition_operations','image.acquisition_worker','image.file_acquisition','image.parent_pins','image.shared_commands','image.file_capture','frontend.gui_model','frontend.gui_windows','frontend.tui_model','frontend.tui_windows','shell.model','shell.windows','disked.invocation','disked.acceptance','provider_guard.positive_control'];assert len(selected)==20
native=run('focused-native',['ctest','--preset','windows-bootstrap','--output-on-failure','-R','^('+'|'.join(x.replace('.','\\.') for x in selected)+')$'],limit=1200);assert b'0 tests failed out of 20' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('parent-cases',[sys.executable,'tests/images/test_parent_pins.py','--probe',P/'file_acquisition_fault.exe','--capture-probe',P/'image_file_capture_probe.exe','--root',C,'--evidence',E/'parent-cases.json'])
parents=json.loads((E/'parent-cases.json').read_bytes());assert parents['passed'] and parents['cases']==4 and parents['mode']=='strong-parent-contract' and not parents['all_namespace_fencing_qualified']
run('file-cases',[sys.executable,'tests/images/test_file_acquisition.py','--probe',P/'file_acquisition_probe.exe','--fault',P/'file_acquisition_fault.exe','--root',C,'--evidence',E/'file-cases.json'])
cases=json.loads((E/'file-cases.json').read_bytes());assert cases['passed'] and cases['cases']==126 and len(cases['process_observations'])==9 and all(x['alive_observed'] and x['terminal_observed'] for x in cases['process_observations'])
run('capture-cases',[sys.executable,'tests/frontend/test_image_file_capture.py','--probe',P/'image_file_capture_probe.exe','--fault',P/'image_file_capture_fault.exe','--map-probe',P/'image_observation_probe.exe','--evidence',E/'capture-cases.json'])
capture=json.loads((E/'capture-cases.json').read_bytes());assert capture['passed'] and capture['cases']==104
run('export-cases',[sys.executable,'tests/evidence/test_export.py','--probe',P/'report_export_probe.exe','--root',C,'--evidence',E/'export-cases.json'])
exports=json.loads((E/'export-cases.json').read_bytes());assert exports['passed'] and exports['cases']==53 and not exports['file_io'] and not exports['public_command']
run('file-export-cases',[sys.executable,'tests/evidence/test_file_export.py','--probe',P/'file_report_export_probe.exe','--fault',P/'file_report_export_fault.exe','--root',C,'--evidence',E/'file-export-cases.json'])
files=json.loads((E/'file-export-cases.json').read_bytes());assert files['passed'] and files['cases']==53 and len(files['process_observations'])==4 and not files['physical_io'] and not files['public_command']
check=run('check',[sys.executable,'spec/tools/specctl.py','check']);assert json.loads(check.stdout)['checks']==945
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);assert manifest['files']==255 and manifest['bytes']==1603110
run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W033','--output','.aide-local/context/DE-W033-parent','--byte-budget','450000'])
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W033-parent'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes());assert identity['identity']['source_state']=='clean' and identity['identity']['source_revision']==revision and len(identity['inputs'])==280 and all(sha(C/name)==digest for name,digest in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
private=('disked_journal_prototype','disked_plan_prototype','disked_guarded_model','disked_journal_semantics','disked_model_journal_producer','disked_case_evidence','disked_report_export','disked_file_report_export')
assert deps and all(not any(lib in x for lib in private) and 'disked_health_observation' in x for x in deps);(E/'product-link-closure.log').write_bytes(('\n'.join(deps)+'\n').encode())
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','file_acquisition_fault','image_file_capture_probe','file_report_export_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=run('launch',[P/'disked.exe','build','inspect','--json']);assert json.loads(launch.stdout)['result']['source_revision']==revision and json.loads(launch.stdout)['result']['version']=='0.1.0-dev.23'
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert len([c for c in discovery if c['availability']=='available'])==18 and next(c for c in discovery if c['id']=='health.assess')['availability']=='available' and next(c for c in discovery if c['id']=='evidence.export')['availability']!='available'
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v']);assert b'Ran 175 tests' in spec.stderr and b'skipped=2' in spec.stderr
artifacts=[]
for name in ['disked.exe','report_export_probe.exe','file_report_export_probe.exe','file_report_export_fault.exe','file_acquisition_probe.exe','file_acquisition_fault.exe','image_file_capture_probe.exe','image_file_capture_fault.exe','image_observation_probe.exe','acquisition_command_probe.exe','acquisition_worker_probe.exe','acquisition_worker_fault.exe','disked_local_file.lib','disked_file_acquisition.lib','disked_image_capture.lib','disked_file_report_export.lib']:
    path=A/name;shutil.copyfile(P/name,path);artifacts.append(dict(path=path.relative_to(R).as_posix(),sha256=sha(path),bytes=path.stat().st_size))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(source=identity,base_revision='b819f473bf9710a607810f2a8a2140b4c4e3531f',host=host,observed_at=datetime.now(timezone.utc).isoformat(),passed=True,
    native_ctest_groups_run=len(selected),native_ctest_groups_available=60,selected_native_groups=selected,parent_cases=4,acquisition_cases=126,capture_cases=104,export_cases=53,file_export_cases=53,export_process_observations=4,
    structural_checks=945,manifest_files=255,manifest_bytes=1603110,spec_tests=dict(run=175,passed=173,skipped=2),
    product_links_health=True,product_links_case=False,product_links_export=False,product_links_journals=False,implemented_commands=18,public_evidence_available=False,artifacts=artifacts,
    limitations=['Ordinary-file parent coordination and generated-file frontends on the recorded Windows host only; no physical namespace/drive-alias fence or elevated/external-writer qualification.',
        'Every directory must allow strong read/list pins. Metadata-only access cannot authorize fallback. Prospective acquisition epochs and executable generations changed; old maps do not authorize cross-generation resume.',
        'Fault seams, DACL changes to owned folders and owned-child cuts are not actual full-filesystem, power-loss, physical-backup or other-platform qualification.',
        'Twenty of 60 native groups rerun; other 40 groups not rerun at this source revision. Historical evidence remains source-bound.',
        'Public evidence.export remains unavailable; private case/export and five journal libraries remain unlinked from disked.exe. DE-W033/034 and full DiskEd 0.1.0 are incomplete.',
        'Owner acceptance, physical devices, elevation, customer data, installation, signing and publication remain separate. No remote writes.']))
print('Clean partial DE-W033 shared parent coordination PASS at '+revision,flush=True)
