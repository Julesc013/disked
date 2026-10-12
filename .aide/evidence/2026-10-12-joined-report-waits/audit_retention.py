"""Read-only audit of the finite joined-report diagnostic and prior exact failure."""
import argparse,ast,hashlib,json,struct,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--index',action='store_true');a=p.parse_args();root=Path.cwd();e=root/'.aide/evidence/2026-10-12-joined-report-waits'
def read(p):return json.loads(p.read_bytes())
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
inv=read(e/'inventory.json');v=read(e/'validation-summary.json');source=v['source_revision'];assert source==inv['source_revision'] and v['diagnostic_only'] and not v['original_failure_cause_established']
for f in inv['evidence']+inv['artifacts']:
 data=(root/f['path']).read_bytes();assert len(data)==f['bytes'] and sha(data)==f['sha256']
for f in inv['artifacts']:
 data=(root/f['path']).read_bytes();at=struct.unpack_from('<I',data,60)[0];assert data[at:at+4]==b'PE\0\0' and struct.unpack_from('<H',data,at+4)[0]==0x8664
assert v['test_git_blob']==subprocess.check_output(['git','rev-parse',source+':'+v['test_path']],text=True).strip()
assert sha(subprocess.check_output(['git','show',source+':'+v['test_path']]))==v['test_sha256']
qualified=read(root/v['qualified_build_reference']);assert qualified['source_revision']==source and qualified['status']=='pass'
assert next(x['sha256'] for x in qualified['artifacts'] if x['kind']=='product')==next(x['sha256'] for x in inv['artifacts'] if x['kind']=='product')
result=read(e/'isolated-1/results.json');assert result['passed'] and result['checks']==281 and result['source_revision']==source and not result['source_dirty']
trace=[json.loads(x) for x in (e/'isolated-1/waits.ndjson').read_text().splitlines()];waits=[x for x in trace if x['kind']=='actual_wait'];assert len(waits)==v['waits']==6 and all(x['milliseconds']==3000 and x['result']==0 for x in waits)
assert max(x['duration_seconds'] for x in waits)==v['maximum_observed_wait_seconds']
verified={x['handle']:x['binding'] for x in trace if x['kind']=='creation_verified_report_handle'}
assert all(verified[x['handle']]==x['binding'] and int(x['binding']['process_id'])>0 and int(x['binding']['process_created'])>0 for x in waits)
old=read(e/'original-failure/observations.json');assert not old['original_failure_cause_established'] and not old['process_exit_inferred_from_receipt']
for f in old['inputs']:
 data=(e/'original-failure'/f['retained_path']).read_bytes();assert len(data)==f['bytes'] and sha(data)==f['sha256']
states=[json.loads(x)['state'] for x in (e/'original-failure/state/report.records').read_bytes().splitlines()]
assert [x['phase'] for x in states]==['prepared','executing','finished']
line=next(x for x in (root/old['original_failure']).read_text().splitlines() if x.startswith("AssertionError: ('retain actual worker',"))
actual=ast.literal_eval(line.removeprefix('AssertionError: '));assert actual[1]==states[-1]
assert sha((e/'original-failure/support.json').read_bytes())==states[-1]['receipt']['output_receipt']['artifact_digest']
target=':' if a.index else 'HEAD:'
for f in inv['evidence']+[dict(path=(e/'inventory.json').relative_to(root).as_posix(),sha256=sha((e/'inventory.json').read_bytes()))]:
 assert sha(subprocess.check_output(['git','show',target+f['path']]))==f['sha256'],f['path']
print(json.dumps(dict(status='pass',source_revision=source,tree='index' if a.index else 'HEAD',retained_files=len(inv['evidence'])+1,actual_waits=len(waits),checks=281,original_failure_cause_established=False)))
