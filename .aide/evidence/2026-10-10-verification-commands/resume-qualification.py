import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();revision='178da19408530799d3add84f10f8c9d1447aac64'
assert subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip()==revision
C=R/('.aide-local/goal-0.1.0/clean-verification-commands-'+revision[:8])
E=R/('.aide/evidence/2026-10-10-verification-commands/reproduction-'+revision[:8])
A=R/('.aide-local/artifacts/DE-W034-verification-commands-'+revision[:8])
commands=json.loads((E/'commands.json').read_text());assert commands and all(c['exit_code']==0 for c in commands)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision and not subprocess.check_output(['git','status','--porcelain'],cwd=C)
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def run(name,argv,cwd=C,limit=120):
    argv=[str(x) for x in argv];start=datetime.now(timezone.utc).isoformat();r=subprocess.run(argv,capture_output=True,cwd=cwd,timeout=limit)
    log=E/('clean-'+name+'.log');log.write_bytes(r.stdout+r.stderr)
    commands.append(dict(command=argv,cwd=str(cwd),started_at=start,exit_code=r.returncode,status='pass' if not r.returncode else 'fail',evidence_path=log.relative_to(R).as_posix()))
    write(E/'commands.json',commands);print(name+' exit '+str(r.returncode),flush=True)
    if r.returncode:raise RuntimeError(name+' failed; actual logs/dependencies retained')
    return r
host=json.loads((E/'clean-host.log').read_bytes());assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
P=C/'build/windows-bootstrap/Release';catalog=json.loads((E/'clean-test-catalog.log').read_bytes());selected=[x['name'] for x in catalog['tests']]
assert len(selected)==74 and b'0 tests failed out of 74' in (E/'clean-native.log').read_bytes()
f=json.loads((E/'verification-commands.json').read_text());assert f['checks']>=450 and len(f['samples'])==6 and all(x['passed'] for x in f['observations']);names=[x['name'] for x in f['observations']]
assert len([x for x in names if x.startswith('false-grants-') and len(x)==len('false-grants-')+6 and set(x[-6:])<=set('01')])==63
for name in ('public-budget-before-execution','oversized-request-zero-ports','observer-retains-last-state-cursor','observer-failure-does-not-cancel','admission-timeout-retains-routing','cancel-before-provider-no-verdict','retention-failure-keeps-actual-verdict','actual-mismatch-confirmed-prefix','actual-cancelled-prefix','product-handler-remains-unavailable'):assert name in names
for sample in f['samples']:
    state=sample['result']['state'];header=sample['header'];verifier=state['binding']['verifier']
    assert verifier['source_revision']==revision and verifier['source_state']=='clean'
    assert verifier['image_digest'] in [sha(P/'verification_command_probe.exe'),sha(P/'verification_command_fault.exe')]
    assert header['definition']['verifier']==verifier and state['quiescent'] and state['phase']=='finished'
    expected={k:state['binding'][k] for k in ('operation_id','attempt_id','worker_epoch','capture_epoch','definition_digest','host_id','verifier')}
    assert expected==sample['result']['request_binding'] and sample['rows'][-1]['state']==state
write(E/'sample-independent-check.json',dict(passed=True,actual_retained_samples=6,source_revision=revision,scope='Retained source/binary/request/state/epoch bindings. Native harness separately validates canonical record chain, actual process exit, collection bytes/observer hashes and producer schemas. Historical evidence authenticates no actor or current image.'))
check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout);assert check['status']=='PASS' and check['schemas']==69
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
context=json.loads(run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-image-observation','--byte-budget','500000']).stdout)
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-image-observation'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean' and len(identity['inputs'])==374 and all(sha(C/name)==value for name,value in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
assert deps and all('disked_file_image_verification' not in x for x in deps);(E/'product-link-closure.log').write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','verification_command_probe','verification_command_fault','verification_worker_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result'];assert launch['version']=='0.1.0-dev.33' and launch['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert sum(x['availability']=='available' for x in discovery)==19
tool=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],limit=300);assert b'Ran 195 tests' in tool.stderr and b'skipped=2' in tool.stderr
write(E/'native-artifacts.json',[dict(path=p.relative_to(C).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(P.glob('*.exe'))]);artifacts=[]
for name in ('disked.exe','verification_command_probe.exe','verification_command_fault.exe','verification_worker_probe.exe','verification_worker_fault.exe','image_verification_collection_probe.exe','disked_verification_commands.lib','disked_verification_observation.lib','disked_report_export.lib'):
    target=A/name;shutil.copyfile(P/name,target);artifacts.append(dict(path=target.relative_to(R).as_posix(),bytes=target.stat().st_size,sha256=sha(target)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,base_revision='412395920484173516f9ab3cc0cf8f24f93a1f8f',source=identity,host=host,observed_at=datetime.now(timezone.utc).isoformat(),native_ctest_groups_run=74,selected_native_groups=selected,focused_checks=f['checks'],actual_generated_acquisitions=1,actual_retained_samples=6,actual_admission_timeout=True,actual_cancellation_before_and_during=True,actual_observer_read_failure=True,actual_prepare_command_form_request_parity=True,actual_negotiated_events=True,public_private_byte_limits=True,actual_retention_fault=True,terminal_faults_in_regression_suite=True,synthetic_contradictions_separate=True,structural_checks=check['checks'],manifest=manifest,context_bytes=context['bytes'],spec_tests=dict(run=195,passed=193,skipped=2),implemented_commands=19,product_selects_image_verification_adapter=False,artifacts=artifacts,limitations=[
    'Shared provisional image.verify service and negotiated event semantics exercised in a private native command probe; no product admission, bounded product channel/frontend qualification or stable ABI.',
    'Admission wait is 3000 ms; synchronous preparation/inspection and all OS filesystem calls do not have universal caller-latency qualification. No replacement, cleanup or exit inference on timeout.',
    'Actual generated acquisition, same-generation byte corruption, cancellation/admission/observer/retention failures are distinct from synthetic malformed replies and deliberately oversized valid private definitions.',
    'Provider quiescence, OS process exit, verification verdict and retention certainty remain distinct. Hashes authenticate no actor/custody/current image; API flush/readback is not power-loss persistence.',
    'Full DE-W034, all specified platforms/storage and owner/physical/elevation/customer/install/signing/publication gates remain open. Static imports do not prove all dynamic dependencies.']))
print('Clean private DE-W034 shared verification commands/events PASS at '+revision,flush=True)
