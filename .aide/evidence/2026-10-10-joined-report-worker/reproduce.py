"""Clean source-bound qualification of the private joined report worker.
Uses installed pinned tools, a fresh local clone and serial owned native tests.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from types import SimpleNamespace
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();ap=argparse.ArgumentParser();ap.add_argument('--source',required=True);ap.add_argument('--resume',action='store_true');a=ap.parse_args()
revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert revision==a.source and len(revision)==40
C=R/('.aide-local/goal-0.1.0/clean-joined-worker-'+revision[:8]);E=R/('.aide/evidence/2026-10-10-joined-report-worker/reproduction-'+revision[:8]);A=R/('.aide-local/artifacts/DE-W034-joined-worker-'+revision[:8])
if a.resume:
    assert C.is_dir() and E.is_dir() and A.is_dir()
    assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision
    assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
    commands=json.loads((E/'commands.json').read_bytes())
else:
    assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'])
    assert not C.exists() and not E.exists() and not A.exists();E.mkdir(parents=True);A.mkdir(parents=True);commands=[]
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode()
def run(name,argv,cwd=C,limit=120):
    argv=[str(x) for x in argv];log=E/('clean-'+name+'.log')
    if a.resume and name in ('host','python-environment','clone','configure','build','test-catalog','native','joined-worker'):
        retained=[c for c in commands if c['evidence_path']==log.relative_to(R).as_posix()]
        assert len(retained)==1 and retained[0]['command']==argv and retained[0]['cwd']==str(cwd) and retained[0]['exit_code']==0 and retained[0]['status']=='pass' and log.is_file(),name
        print(name+' retained actual pass',flush=True)
        # These stages consume only stdout; the retained log contains actual
        # combined output. New qualification stages still execute normally.
        return SimpleNamespace(stdout=log.read_bytes(),stderr=b'',returncode=0)
    r=subprocess.run(argv,capture_output=True,cwd=cwd,timeout=limit);log.write_bytes(r.stdout+r.stderr)
    commands.append(dict(command=argv,cwd=str(cwd),exit_code=r.returncode,status='pass' if not r.returncode else 'fail',evidence_path=log.relative_to(R).as_posix()));write(E/'commands.json',commands);print(name+' exit '+str(r.returncode),flush=True)
    if r.returncode:raise RuntimeError(name+' failed; retain actual logs/dependencies')
    return r
host_command="$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$principal=[System.Security.Principal.WindowsPrincipal]::new($identity);$os=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$identity.Name;elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$os.Caption;version=$os.Version;build=$os.BuildNumber;architecture=$os.OSArchitecture}|ConvertTo-Json -Compress"
host=json.loads(run('host',['powershell','-NoProfile','-Command',host_command],R).stdout);assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],R)
run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R);assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision
run('configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build','--preset','windows-bootstrap','--parallel','4'],limit=900);P=C/'build/windows-bootstrap/Release'
catalog=json.loads(run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']).stdout);selected=[x['name'] for x in catalog['tests']];assert len(selected)==76 and 'evidence.verification_case_export' in selected and 'evidence.report_worker' in selected
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1800);assert b'0 tests failed out of 76' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('joined-worker',[sys.executable,'tests/evidence/test_verification_case.py','--probe',P/'verification_case_probe.exe','--fault',P/'verification_case_fault.exe','--product',P/'disked.exe','--worker',P/'report_worker_probe.exe','--worker-fault',P/'report_worker_fault.exe','--root',C,'--evidence',E/'joined-worker.json'],limit=240)
f=json.loads((E/'joined-worker.json').read_bytes());assert f['passed'] and f['checks']>=520 and len(f['actual_exports'])==47
names=[x['name'] for x in f['observations']]
assert names.count('joined-31-false-grants-no-effects')==31 and names.count('joined-sixteen-worker-selected-policies')==16 and names.count('joined-public-profile-gate-refuses')==3
for name in ('joined-independent-selected-output','joined-independent-final-source-pair','joined-admission-timeout-is-uncertain','joined-late-worker-no-replacement','joined-independent-job-limits','joined-cancel-before-create-observed','joined-cancel-keeps-created-file','joined-client-departure-does-not-cancel','joined-terminal-store-failure-not-success','joined-recreated-source-no-effects'):assert name in names
original=f['samples'][0];body=bytes.fromhex(original['collection_hex']);coll=json.loads(body)
assert coll['request_raw'].encode()==bytes.fromhex(original['acquisition_request_hex']) and bytes.fromhex(coll['history_hex'])==bytes.fromhex(original['acquisition_history_hex']) and body==canonical(coll)+b'\n'
joined=[s for s in f['samples'] if s.get('kind','').startswith('actual-joined-worker-')];assert len(joined)==26
for sample in joined:
    d=sample['definition'];exe=P/('report_worker_fault.exe' if d['definition']['image_digest']==sha(P/'report_worker_fault.exe')[7:] else 'report_worker_probe.exe')
    assert d['definition']['source_revision']==revision and d['definition']['image_digest']==sha(exe)[7:] and d['definition_digest']=='sha256:'+hashlib.sha256(canonical(d['definition'])).hexdigest()
    assert sample['header']['definition']==d['definition'] and sample['header']['grant']['collection_read'] and sample['records'][-1]['state']==sample['observation']['value']['state']
check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout);assert check['status']=='PASS' and check['schemas']==72
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
context=json.loads(run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-joined-worker','--byte-budget','500000']).stdout);run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-joined-worker'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes());assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean' and len(identity['inputs'])==394 and all(sha(C/name)==value for name,value in identity['inputs'].items())
for subject in ('disked','report_worker_probe','report_worker_fault'):
    project=ET.parse(C/('build/windows-bootstrap/'+subject+'.vcxproj'));deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')];assert deps and all('disked_file_verification_case_export' in x for x in deps)
    (E/(subject+'-link-closure.log')).write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','report_worker_probe','report_worker_fault'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result'];assert launch['version']=='0.1.0-dev.35' and launch['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert sum(x['availability']=='available' for x in discovery)==20
tool=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],limit=400);assert b'Ran 205 tests' in tool.stderr and b'skipped=2' in tool.stderr
write(E/'native-artifacts.json',[dict(path=p.relative_to(C).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(P.glob('*.exe'))]);artifacts=[]
for name in ('disked.exe','report_worker_probe.exe','report_worker_fault.exe','verification_case_probe.exe','verification_case_fault.exe','disked_file_verification_case_export.lib','disked_report_export.lib'):
    target=A/name;shutil.copyfile(P/name,target);artifacts.append(dict(path=target.relative_to(R).as_posix(),bytes=target.stat().st_size,sha256=sha(target)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,base_revision='5d51b9b014568ae80f3856722307ffc034f5bdc7',source=identity,host=host,observed_at=datetime.now(timezone.utc).isoformat(),qualification_resumed=a.resume,qualification_recipe_sha256=sha(Path(__file__)),native_ctest_groups_run=76,selected_native_groups=selected,focused_checks=f['checks'],actual_exports=len(f['actual_exports']),actual_joined_workers=len(joined),actual_generated_acquisitions=1,actual_retained_collections=1,synthetic_faults_separate=True,structural_checks=check['checks'],manifest=manifest,context_bytes=context['bytes'],spec_tests=dict(run=205,passed=203,skipped=2),implemented_commands=20,product_links_joined_adapter=True,product_selects_joined_public_profile=False,artifacts=artifacts,limitations=['Private contained report role and strict producer checks on this Windows host; common command/frontend admission remains open.','Historical evidence does not authenticate custody, qualify current media or prove power-loss persistence.','Synthetic port faults are separate from actual generated native effects; original media paths were moved before joined-worker tests.','Full DE-W034 and all 0.1.0 platforms/storage, owner and privilege/release gates remain open.']))
print('Clean DE-W034 private joined report worker PASS at '+revision,flush=True)
