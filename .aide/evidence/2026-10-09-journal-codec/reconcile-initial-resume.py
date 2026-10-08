import hashlib,json,shutil,sys
from pathlib import Path
from datetime import datetime,timezone
R=Path.cwd();C=R/'.aide-local/goal-0.1.0/clean-ce9ae70f';E=R/'.aide/evidence/2026-10-09-journal-codec/reproduction-ce9ae70f'
sys.path.insert(0,str(C/'tests/images'))
from test_acquisition_worker import history_check,map_check,source_bytes,owned_process,K
failed=C/'.aide-local/disked-acq-worker-krjmvqyr';folder=failed/('磁'*60);store=folder/'resume'
rows=history_check(store/'acquisition.records');state=rows[-1]['state'];header=json.loads((store/'acquisition.request').read_bytes())
assert state['phase']=='finished' and state['quiescent'] and state['outcome']['status']=='completed'
assert state['binding']['operation_id']==header['operation_id'] and state['binding']['definition_digest']==header['definition_digest']
handle=owned_process(state,str(C/'build/windows-bootstrap/Release/disked.exe'));observed='not_present'
if handle:
    try:assert K.WaitForSingleObject(handle,0)==0;observed='signaled_exact_creation_and_image'
    finally:K.CloseHandle(handle)
expected=source_bytes(16777216);src=(folder/'source.img').read_bytes();dest=(folder/'copy.img').read_bytes()
assert src==expected and dest==expected;maps=map_check(folder/'copy.map',expected)
snap=E/'resume-deadline-reconciliation';snap.mkdir(exist_ok=False)
files={}
for p in [store/'acquisition.request',store/'acquisition.records',store/'acquisition.cancel',folder/'copy.map']:
    target=snap/p.name;shutil.copyfile(p,target);files[target.name]='sha256:'+hashlib.sha256(target.read_bytes()).hexdigest()
duration=(int(state['observed_filetime'])-int(rows[0]['state']['observed_filetime']))/1e7
report=dict(source_revision='ce9ae70f28e6e8c7d6408563fd3508d51d263164',observed_at=datetime.now(timezone.utc).isoformat(),
    scope='Subsequent read-only reconciliation of generated retained fixture; initial campaign remains failed',
    initial_fixture_deadline_seconds=30,observed_worker_history_span_seconds=duration,original_deadline_met=False,
    worker_observation=observed,operation_id=header['operation_id'],record_rows=len(rows),map_rows=len(maps),
    bytes=len(expected),source_equals_generated=True,destination_equals_generated=True,map_chain_and_seal_verified=True,
    sha256='sha256:'+hashlib.sha256(expected).hexdigest(),files=files,fixture_path=str(failed),removed_fixture=False)
(snap/'result.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
shutil.copyfile(C/'build/windows-bootstrap/Testing/Temporary/LastTest.log',E/'initial-native-details.log')
print(json.dumps({k:v for k,v in report.items() if k not in ['files','fixture_path']},indent=2))
