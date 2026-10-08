import hashlib,json,shutil,subprocess,sys
from pathlib import Path
from datetime import datetime,timezone
R=Path.cwd();revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()
assert not subprocess.check_output(['git','status','--porcelain'])
C=R/('.aide-local/goal-0.1.0/clean-'+revision[:8]);assert not C.exists()
E=R/('.aide/evidence/2026-10-09-acquisition-operations/reproduction-'+revision[:8]);E.mkdir(parents=True,exist_ok=False)
A=R/('.aide-local/artifacts/DE-W033-observation-'+revision[:8]);A.mkdir(parents=True,exist_ok=False);commands=[]
def write(p,v):p.write_text(json.dumps(v,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(p):return 'sha256:'+hashlib.sha256(p.read_bytes()).hexdigest()
def run(name,args,cwd=C,limit=420):
    print('Running clean '+name,flush=True);argv=[str(x) for x in args]
    try:p=subprocess.run(argv,cwd=cwd,capture_output=True,timeout=limit)
    except subprocess.TimeoutExpired as error:
        path=E/('clean-'+name+'.log');path.write_bytes((error.stdout or b'')+(error.stderr or b''))
        commands.append(dict(command=subprocess.list2cmdline(argv),cwd=str(cwd),exit_code=None,status='fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands);raise
    path=E/('clean-'+name+'.log');path.write_bytes(p.stdout+p.stderr)
    commands.append(dict(command=subprocess.list2cmdline(argv),cwd=str(cwd),exit_code=p.returncode,status='pass' if p.returncode==0 else 'fail',evidence_path=path.relative_to(R).as_posix()));write(E/'commands.json',commands)
    print(name+' exit '+str(p.returncode),flush=True)
    if p.returncode:raise RuntimeError(name+' failed; retained log')
    return p
run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision and not subprocess.check_output(['git','status','--porcelain'],cwd=C)
run('configure',['cmake','--preset','windows-bootstrap']);run('build',['cmake','--build','--preset','windows-bootstrap'])
native=run('native-tests',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=900);assert b'0 tests failed out of 45' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
P=C/'build/windows-bootstrap/Release'
run('command-cases',[sys.executable,'tests/images/test_acquisition_commands.py','--probe',P/'acquisition_command_probe.exe','--root',C,'--evidence',E/'command-cases.json'])
command_cases=json.loads((E/'command-cases.json').read_bytes());assert command_cases['checks']==len(command_cases['observations']) and len(command_cases['verified_copies'])==6 and all(c['passed'] for c in command_cases['observations'])

run('operation-cases',[sys.executable,'tests/images/test_acquisition_operations.py','--probe',P/'acquisition_command_probe.exe','--disked',P/'disked.exe','--reader',P/'watch_probe.exe','--root',C,'--evidence',E/'operation-cases.json'])
operation_cases=json.loads((E/'operation-cases.json').read_bytes())
assert operation_cases['checks']==len(operation_cases['observations']) and len(operation_cases['verified'])==2 and len(operation_cases['producer_events'])>=4
assert not operation_cases['public_copy_admitted'] and all(c['passed'] for c in operation_cases['observations'])
validation_source=Path(__file__).with_name('validate-producer-events.py')
if not validation_source.exists():validation_source=R/'.aide-local/goal-0.1.0/validate_acquisition_events.py'
shutil.copyfile(validation_source,E/'validate-producer-events.py')
run('producer-schema',[sys.executable,E/'validate-producer-events.py',C,E/'operation-cases.json'])

run('worker-cases',[sys.executable,'tests/images/test_acquisition_worker.py','--probe',P/'acquisition_worker_probe.exe','--fault',P/'acquisition_worker_fault.exe','--root',C,'--evidence',E/'worker-cases.json'])
worker=json.loads((E/'worker-cases.json').read_bytes());assert worker['all_passed'] and worker['checks']==len(worker['observations']) and sum('outcome' in w for w in worker['workers'])==10
run('file-cases',[sys.executable,'tests/images/test_file_acquisition.py','--probe',P/'file_acquisition_probe.exe','--fault',P/'file_acquisition_fault.exe','--root',C,'--evidence',E/'file-cases.json'])
cases=json.loads((E/'file-cases.json').read_text(encoding='utf-8'));assert cases['passed'] and cases['cases']==126
assert len(cases['process_observations'])==9 and all(p['alive_observed'] and p['terminal_observed'] for p in cases['process_observations'])
run('pipeline-cases',[sys.executable,'tests/images/test_acquisition_pipeline.py','--probe',P/'acquisition_probe.exe','--root',C,'--validate-schemas','--evidence',E/'pipeline-cases.json'])
core=json.loads((E/'pipeline-cases.json').read_text(encoding='utf-8'));assert core['passed'] and core['cases']==218
run('check',[sys.executable,'spec/tools/specctl.py','check']);run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest'])
fresh=run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
spec=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v']);assert b'Ran 175 tests' in spec.stderr and b'skipped=2' in spec.stderr
run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W033','--output','.aide-local/context/DE-W033-worker','--byte-budget','280000'])
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W033-worker'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_text(encoding='utf-8'))
assert identity['identity']['source_state']=='clean' and identity['identity']['source_revision']==revision
assert len(identity['inputs'])==222 and all(sha(C/name)==digest for name,digest in identity['inputs'].items())
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
subjects=['disked','acquisition_probe','file_acquisition_probe','file_acquisition_fault','acquisition_worker_probe','acquisition_worker_fault','acquisition_command_probe','watch_probe']
for subject in subjects:
    for kind in ['HEADERS','IMPORTS','DEPENDENTS']:run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
run('launch',[P/'disked.exe','build','inspect','--json'])
assert json.loads((E/'clean-launch.log').read_text())['result']['source_revision']==revision
discovery=run('discovery',[P/'disked.exe','command','list','--json'])
value=json.loads(discovery.stdout)
write(E/'command-discovery.json',value)
artifacts=[]
for name in ['disked.exe','disked_acquisition.lib','disked_local_file.lib','disked_file_acquisition.lib','disked_hash.lib','acquisition_probe.exe','file_acquisition_probe.exe','file_acquisition_fault.exe','acquisition_worker_probe.exe','acquisition_worker_fault.exe','disked_acquisition_commands.lib','acquisition_command_probe.exe','watch_probe.exe','disked_acquisition_observation.lib']:
    target=A/name;shutil.copyfile(P/name,target);artifacts.append(dict(path=target.relative_to(R).as_posix(),sha256=sha(target),bytes=target.stat().st_size))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(source=identity,observed_at=datetime.now(timezone.utc).isoformat(),passed=True,native_ctest_groups=45,file_cases=126,command_checks=command_cases['checks'],command_verified_copies=6,worker_checks=worker['checks'],worker_completed_byte_verifications=10,process_observations=cases['process_observations'],pipeline_cases=218,
    operation_checks=operation_cases['checks'],producer_events=len(operation_cases['producer_events']),spec_tests=dict(run=175,passed=173,skipped=2),artifacts=artifacts,imports_subjects={n:sha(P/(n+'.exe')) for n in subjects},
    limitations=['Private Windows generated-file acquisition; W033 and all DiskEd 0.1.0 remain incomplete','Public explicit acquisition inspect/cancel and CLI/stdio watch verified; visible copy review/submission, interactive rendering and public copy admission remain pending','No power-loss, physical backing, real failing media, snapshots or restore qualification','Other hosts/platforms, owner acceptance and independent safety qualification remain unverified']))
print('Clean W033 acquisition observation PASS at '+revision,flush=True)
