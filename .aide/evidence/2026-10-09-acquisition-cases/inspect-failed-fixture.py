"""Read-only observation of the retained first working-test fixture.

Generated repository-owned files only. No worker invocation, process control,
cleanup, media-path traversal, source authenticity or retroactive test pass.
"""
import hashlib,json,sys
from datetime import datetime,timezone
from pathlib import Path
R=Path.cwd();E=R/'.aide/evidence/2026-10-09-acquisition-cases'
owned=R/'.aide-local/disked-acq-worker-0albszf7/owned'
assert owned.is_dir() and owned.resolve().is_relative_to(R/'.aide-local')
sys.path.insert(0,str(R/'tests/images'))
from test_acquisition_worker import source_bytes,map_check,history_check,canonical
expected=source_bytes(262145)
src=owned/'OWNED-CUSTOMER-SOURCE.img';dst=owned/'OWNED-CUSTOMER-COPY.img';mapping=owned/'OWNED-CUSTOMER-MAP.map'
assert src.read_bytes()==dst.read_bytes()==expected
map_rows=map_check(mapping,expected);rows=history_check(owned/'state/acquisition.records')
header_path=owned/'state/acquisition.request';assert header_path.stat().st_size<=32768
header=json.loads(header_path.read_bytes());last=rows[-1]['state']
assert last['phase']=='finished' and last['quiescent'] and last['outcome']['status']=='completed'
assert last['binding']['definition_digest']==header['definition_digest']=='sha256:'+hashlib.sha256(canonical(header['definition'])).hexdigest()
files=[]
for path in (src,dst,mapping,header_path,owned/'state/acquisition.records',owned/'support.json'):
    body=path.read_bytes();files.append(dict(path=path.relative_to(R).as_posix(),bytes=len(body),sha256='sha256:'+hashlib.sha256(body).hexdigest()))
result=dict(passed=True,observed_at=datetime.now(timezone.utc).isoformat(),mode='read-only-retained-generated-fixture',
    files=files,source_copy_bytes=262145,worker_history_records=len(rows),map_records=len(map_rows),
    recorded_terminal_state=last,recorded_source_revision=header['definition']['source_revision'],
    qualifications=['Independent bytes/pattern/map/history observation only; original working-test result remains failed.',
        'No worker/process action or cleanup; no worker-exit, authenticated actor, clean-source reconstruction or physical claim.'])
(E/'failed-fixture-inspection.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print('PASS read-only retained generated fixture: original test failure remains retained.')
