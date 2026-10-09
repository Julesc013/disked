"""Read-only qualification of the retained timed-out, owned test fixture.

No worker replay, termination, dependency cleanup or physical access. The PID
check uses the exact record's process creation time and executable identity.
"""
import hashlib,json,shutil,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();C=R/'.aide-local/goal-0.1.0/clean-store-7df4b6c8'
E=R/'.aide/evidence/2026-10-09-worker-store/reproduction-7df4b6c8'
owned=C/'.aide-local/disked-acq-worker-rvld9_hs'
assert owned.resolve().parent==(C/'.aide-local').resolve()
sys.path.insert(0,str(C/'tests/images'))
from test_acquisition_worker import history_check,owned_process,K,map_check,digest,source_bytes
d=next(p for p in owned.rglob('resume') if p.is_dir())
rows=history_check(d/'acquisition.records');s=rows[-1]['state']
header=json.loads((d/'acquisition.request').read_bytes())
code=C/'build/windows-bootstrap/Release/disked.exe'
assert hashlib.sha256(code.read_bytes()).hexdigest()==header['definition']['image_digest']
identity=json.loads((C/'build/windows-bootstrap/generated/build-identity.json').read_bytes())
assert identity['identity']['source_revision']==header['definition']['source_revision']
assert identity['identity']['source_state']=='clean' and len(identity['inputs'])==282
assert subprocess.check_output(['git','rev-parse','HEAD'],cwd=C,text=True).strip()==header['definition']['source_revision']
assert not subprocess.check_output(['git','status','--porcelain'],cwd=C)
assert s['binding']['operation_id']==header['operation_id']
assert s['binding']['attempt_id']==header['attempt_id']
assert s['binding']['worker_epoch']==header['worker_epoch']
assert s['binding']['definition_digest']==header['definition_digest']
assert s['phase']=='finished' and s['quiescent'] and s['outcome']['status']=='completed'
h=owned_process(s,str(C/'build/windows-bootstrap/Release/disked.exe'))
wait=None
if h:
    try:wait=K.WaitForSingleObject(h,0);assert wait==0
    finally:K.CloseHandle(h)
data=(d.parent/'source.img').read_bytes();copied=(d.parent/'copy.img').read_bytes()
assert data==copied==source_bytes(16777216)
maps=map_check(d.parent/'copy.map',data)
inputs=[]
for p in (d/'acquisition.request',d/'acquisition.records',d.parent/'state/acquisition.request',d.parent/'state/acquisition.records',d.parent/'copy.map',d.parent/'copy.img',d.parent/'source.img'):
    inputs.append(dict(path=p.relative_to(R).as_posix(),bytes=p.stat().st_size,sha256=digest(p.read_bytes())))
    if p.suffix not in ('.img','.map'):
        (E/('failed-fixture-'+p.parent.name+'-'+p.name)).write_bytes(p.read_bytes())
out=dict(observed_at=datetime.now(timezone.utc).isoformat(),read_only=True,source_revision=header['definition']['source_revision'],
    records=len(rows),elapsed_between_first_and_last=(int(s['observed_filetime'])-int(rows[0]['state']['observed_filetime']))/1e7,
    checkpoints=[dict(sequence=x['state']['sequence'],bytes=x['state']['checkpoint_bytes'],phase=x['state']['phase'],
        elapsed=(int(x['state']['observed_filetime'])-int(rows[0]['state']['observed_filetime']))/1e7) for x in rows],
    last_state=s,process_absent=not h,process_wait_result=wait,bytes=len(copied),copy_matches=True,map_records=len(maps),inputs=inputs,
    conclusion='The full-size resumed copy completed after the 30-second test deadline with advancing durable checkpoints. This does not retroactively pass the failed test or establish a performance promise.')
(E/'failed-fixture-terminal-inspection.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n')
(E/'failed-source-build-identity.json').write_text(json.dumps(identity,indent=2)+'\n',encoding='utf-8',newline='\n')
# Preserve that exact generation for its original map. No execution or replay.
artifact=R/'.aide-local/artifacts/DE-W033-store-7df4b6c8/disked.exe'
assert artifact.parent.resolve().parent==(R/'.aide-local/artifacts').resolve()
if artifact.exists():assert artifact.read_bytes()==code.read_bytes()
else:shutil.copyfile(code,artifact)
(E/'failed-artifacts.json').write_text(json.dumps(dict(source_revision=header['definition']['source_revision'],
    native_run_status='fail',passed_groups=60,failed_groups=['frontend.acquisition_interactive'],
    artifacts=[dict(path=artifact.relative_to(R).as_posix(),bytes=artifact.stat().st_size,sha256=digest(artifact.read_bytes()))]),indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(dict(records=len(rows),elapsed_between_first_and_last=out['elapsed_between_first_and_last'],process_absent=not h,
    process_wait_result=wait,copy_matches=True,map_records=len(maps),operation_id=header['operation_id'])))
