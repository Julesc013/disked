"""Clean native product verification and common request qualification.
Installed pinned tools, fresh local clone, serial native suites, owned images.
No fetch/install/elevation/devices/customer data/signing/publication.
"""
import argparse,hashlib,json,shutil,subprocess,sys,xml.etree.ElementTree as ET
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();p=argparse.ArgumentParser();p.add_argument('--source',required=True);a=p.parse_args()
revision=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip();assert revision==a.source and len(revision)==40
C=R/('.aide-local/goal-0.1.0/clean-product-verification-'+revision[:8])
E=R/('.aide/evidence/2026-10-10-product-verification/reproduction-'+revision[:8])
A=R/('.aide-local/artifacts/DE-W034-product-verification-'+revision[:8])
assert not subprocess.check_output(['git','status','--porcelain','--untracked-files=no'])
assert not C.exists() and not E.exists() and not A.exists();E.mkdir(parents=True);A.mkdir(parents=True);commands=[]
def write(path,value):path.write_text(json.dumps(value,indent=2)+'\n',encoding='utf-8',newline='\n')
def sha(path):return 'sha256:'+hashlib.sha256(path.read_bytes()).hexdigest()
def run(name,argv,cwd=C,limit=120):
    argv=[str(x) for x in argv];start=datetime.now(timezone.utc).isoformat();r=subprocess.run(argv,capture_output=True,cwd=cwd,timeout=limit)
    log=E/('clean-'+name+'.log');log.write_bytes(r.stdout+r.stderr)
    commands.append(dict(command=argv,cwd=str(cwd),started_at=start,exit_code=r.returncode,status='pass' if not r.returncode else 'fail',evidence_path=log.relative_to(R).as_posix()))
    write(E/'commands.json',commands);print(name+' exit '+str(r.returncode),flush=True)
    if r.returncode:raise RuntimeError(name+' failed; actual logs/dependencies retained')
    return r
host_command="$identity=[System.Security.Principal.WindowsIdentity]::GetCurrent();$principal=[System.Security.Principal.WindowsPrincipal]::new($identity);$os=Get-CimInstance Win32_OperatingSystem;[ordered]@{identity=$identity.Name;elevated=$principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator);os=$os.Caption;version=$os.Version;build=$os.BuildNumber;architecture=$os.OSArchitecture}|ConvertTo-Json -Compress"
host=json.loads(run('host',['powershell','-NoProfile','-Command',host_command],R).stdout);assert host['identity']=='BLACKGLASS-WIN1\\Jules' and not host['elevated']
run('python-environment',[sys.executable,'-c','import sys,importlib.metadata as m;print(sys.version);print("PyYAML="+m.version("PyYAML"));print("jsonschema="+m.version("jsonschema"))'],R)
run('clone',['git','clone','--no-hardlinks','--no-local',R,C],R)
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==revision and not subprocess.check_output(['git','status','--porcelain'],cwd=C)
run('configure',['cmake','--preset','windows-bootstrap','-DPython3_EXECUTABLE='+sys.executable])
run('build',['cmake','--build','--preset','windows-bootstrap','--parallel','4'],limit=900);P=C/'build/windows-bootstrap/Release'
catalog=json.loads(run('test-catalog',['ctest','--preset','windows-bootstrap','--show-only=json-v1']).stdout)
selected=[x['name'] for x in catalog['tests']];assert len(selected)==75 and 'evidence.verification_worker' in selected and 'evidence.verification_commands' in selected
native=run('native',['ctest','--preset','windows-bootstrap','--output-on-failure'],limit=1500);assert b'0 tests failed out of 75' in native.stdout
(E/'native-details.log').write_bytes((C/'build/windows-bootstrap/Testing/Temporary/LastTest.log').read_bytes())
run('verification-commands',[sys.executable,'tests/evidence/test_verification_commands.py','--probe',P/'verification_command_probe.exe','--fault',P/'verification_command_fault.exe','--product',P/'disked.exe','--root',C,'--evidence',E/'verification-commands.json'])
f=json.loads((E/'verification-commands.json').read_bytes());assert f['checks']>=450 and len(f['samples'])==6 and all(x['passed'] for x in f['observations'])
names=[x['name'] for x in f['observations']]
assert len([x for x in names if x.startswith('false-grants-') and len(x)==len('false-grants-')+6 and set(x[-6:])<=set('01')])==63
for name in ('public-budget-before-execution','oversized-request-zero-ports','observer-retains-last-state-cursor','observer-failure-does-not-cancel','admission-timeout-retains-routing','cancel-before-provider-no-verdict','retention-failure-keeps-actual-verdict','actual-mismatch-confirmed-prefix','actual-cancelled-prefix','product-refuses-unavailable-selected-store'):assert name in names
for sample in f['samples']:
    state=sample['result']['state'];header=sample['header'];verifier=state['binding']['verifier']
    assert verifier['source_revision']==revision and verifier['source_state']=='clean'
    assert verifier['image_digest'] in [sha(P/'verification_command_probe.exe'),sha(P/'verification_command_fault.exe')]
    assert header['definition']['verifier']==verifier and state['quiescent'] and state['phase']=='finished'
    expected={k:state['binding'][k] for k in ('operation_id','attempt_id','worker_epoch','capture_epoch','definition_digest','host_id','verifier')}
    assert expected==sample['result']['request_binding'] and sample['rows'][-1]['state']==state
write(E/'sample-independent-check.json',dict(passed=True,actual_retained_samples=6,source_revision=revision,scope='Retained source/binary/request/state/epoch bindings. Native harness separately validates canonical record chain, actual process exit, collection bytes/observer hashes and producer schemas. Historical evidence authenticates no actor or current image.'))
run('product-verification',[sys.executable,'tests/frontend/test_product_verification.py','--product',P/'disked.exe','--fault',P/'disked_verification_test.exe','--root',C,'--evidence',E/'product-verification.json'],limit=240)
product_results=json.loads((E/'product-verification.json').read_bytes());assert product_results['passed'] and product_results['checks']>=200 and len(product_results['samples'])==11 and len(product_results['native_journeys'])==11
assert product_results['source_revision']==revision and product_results['source_dirty'] is False and product_results['owner_accepted'] is False
names=[x['name'] for x in product_results['observations']]
assert names.count('missing-grant-before-effects')==63
for name in ('gui-late-completion-separate','bounded-wait-retains-review','cached-discovery-with-live-callback','occupied-slot-not-replaced','released-callback-single-matched-effect','oversized-reply-keeps-routing-and-allocated-id','actual-cancelled-prefix','actual-retention-failure-keeps-verdict','disconnected-observer-does-not-cancel-or-restart','explicit-provisional-product-selection','source-and-original-metadata-unchanged'):assert name in names
assert {x['frontend'] for x in product_results['native_journeys']}=={'gui','tui','shell','stdio'}
def canonical(v):return json.dumps(v,sort_keys=True,separators=(',',':'),ensure_ascii=False).encode('utf-8')
for sample in product_results['samples']:
    s=sample['result']['state'];v=s['binding']['verifier'];assert v['source_revision']==revision and v['source_state']=='clean' and v['image_digest'] in [sha(P/'disked.exe'),sha(P/'disked_verification_test.exe')]
    assert sample['header']['definition']['verifier']==v and s['quiescent'] and s['phase']=='finished'
    previous='0'*64;history=b''
    for n,row in enumerate(sample['rows'],1):
        unsigned={k:x for k,x in row.items() if k!='digest'};assert row['previous']==previous and hashlib.sha256(canonical(unsigned)).hexdigest()==row['digest'] and row['state']['sequence']==str(n)
        previous=row['digest'];history+=canonical(row)+b'\n'
    assert 'sha256:'+hashlib.sha256(history).hexdigest()==sample['history_sha256'] and sample['rows'][-1]['state']==s
    body=bytes.fromhex(sample['collection_hex']);assert 'sha256:'+hashlib.sha256(body).hexdigest()==sample['collection_sha256']
    if s['retention']['state']=='verified':
        c=json.loads(body);assert body.endswith(b'\n') and sample['collection_sha256']==s['retention']['digest'] and len(body)==int(s['retention']['bytes']) and 'sha256:'+hashlib.sha256(canonical(c)).hexdigest()==s['retention']['collection_revision'] and c['records'][0]['observation']['outcome']==s['outcome']
check=json.loads(run('check',[sys.executable,'spec/tools/specctl.py','check']).stdout);assert check['status']=='PASS' and check['schemas']==69
manifest=json.loads(run('manifest',[sys.executable,'spec/tools/specctl.py','verify-manifest']).stdout);run('freshness',[sys.executable,'spec/tools/specctl.py','index','--check'])
context=json.loads(run('context',[sys.executable,'spec/tools/specctl.py','context','--work','DE-W034','--output','.aide-local/context/DE-W034-image-observation','--byte-budget','500000']).stdout)
run('verify-context',[sys.executable,'spec/tools/specctl.py','verify-context','.aide-local/context/DE-W034-image-observation'])
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
assert identity['identity']['source_revision']==revision and identity['identity']['source_state']=='clean' and len(identity['inputs'])==378 and all(sha(C/name)==value for name,value in identity['inputs'].items())
project=ET.parse(C/'build/windows-bootstrap/disked.vcxproj');deps=[x.text or '' for x in project.iter() if x.tag.endswith('}AdditionalDependencies')]
assert deps and all('disked_file_image_verification' in x for x in deps);(E/'product-link-closure.log').write_text('\n'.join(deps)+'\n',encoding='utf-8',newline='\n')
dumpbin=Path(identity['compiler_path']).with_name('dumpbin.exe')
for subject in ('disked','disked_verification_test','verification_command_probe','request_channel_probe'):
    for kind in ('HEADERS','IMPORTS','DEPENDENTS'):run(subject+'-'+kind.lower(),[dumpbin,'/'+kind,P/(subject+'.exe')])
launch=json.loads(run('launch',[P/'disked.exe','build','inspect','--json']).stdout)['result'];assert launch['version']=='0.1.0-dev.34' and launch['source_revision']==revision
discovery=json.loads(run('discovery',[P/'disked.exe','commands','--json']).stdout)['result']['commands'];assert sum(x['availability']=='available' for x in discovery)==20
tool=run('spec-tests',[sys.executable,'-m','unittest','discover','-s','spec/tools/tests','-v'],limit=300);assert b'Ran 196 tests' in tool.stderr and b'skipped=2' in tool.stderr
write(E/'native-artifacts.json',[dict(path=p.relative_to(C).as_posix(),bytes=p.stat().st_size,sha256=sha(p)) for p in sorted(P.glob('*.exe'))]);artifacts=[]
for name in ('disked.exe','disked_verification_test.exe','request_channel_probe.exe','verification_command_probe.exe','verification_command_fault.exe','verification_worker_probe.exe','verification_worker_fault.exe','image_verification_collection_probe.exe','disked_verification_commands.lib','disked_verification_observation.lib','disked_report_export.lib','disked_file_image_verification.lib'):
    target=A/name;shutil.copyfile(P/name,target);artifacts.append(dict(path=target.relative_to(R).as_posix(),bytes=target.stat().st_size,sha256=sha(target)))
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
write(E/'clean-results.json',dict(passed=True,base_revision='c3d820092970ab1ec56f122332d9325ba9cf02ca',source=identity,host=host,observed_at=datetime.now(timezone.utc).isoformat(),native_ctest_groups_run=75,selected_native_groups=selected,focused_checks=f['checks'],actual_generated_acquisitions=1,actual_retained_samples=6,actual_admission_timeout=True,actual_cancellation_before_and_during=True,actual_observer_read_failure=True,actual_prepare_command_form_request_parity=True,actual_negotiated_events=True,public_private_byte_limits=True,actual_retention_fault=True,terminal_faults_in_regression_suite=True,synthetic_contradictions_separate=True,structural_checks=check['checks'],manifest=manifest,context_bytes=context['bytes'],spec_tests=dict(run=196,passed=194,skipped=2),implemented_commands=20,product_selects_image_verification_adapter=True,product_checks=product_results['checks'],product_native_journeys=len(product_results['native_journeys']),product_retained_samples=len(product_results['samples']),product_wait_view_disconnect_reply_faults=True,artifacts=artifacts,limitations=[
    'Proposed ordinary-file product selection and actual bounded common channel/frontend verification qualified at this source/host; no stable ABI, authenticated custody/current-image or full product admission.',
    'Native admission wait is 3000 ms, CLI/stdio callback wait 4000 ms, finite watch follow 2000 ms; individual OS filesystem calls have no universal latency guarantee. No replacement, cleanup or exit inference on timeout.',
    'Actual generated acquisition, same-generation byte corruption, cancellation/admission/observer/retention failures are distinct from synthetic malformed replies and deliberately oversized valid private definitions.',
    'Provider quiescence, OS process exit, verification verdict and retention certainty remain distinct. Hashes authenticate no actor/custody/current image; API flush/readback is not power-loss persistence.',
    'Full DE-W034, all specified platforms/storage and owner/physical/elevation/customer/install/signing/publication gates remain open. Static imports do not prove all dynamic dependencies.']))
print('Clean DE-W034 native product verification PASS at '+revision,flush=True)
