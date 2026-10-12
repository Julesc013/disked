"""Read-only audit of current private tests against separately identified producer."""
import argparse,gzip,hashlib,json,subprocess
from pathlib import Path
p=argparse.ArgumentParser();p.add_argument('--index',action='store_true');a=p.parse_args();root=Path.cwd();e=root/'.aide/evidence/2026-10-12-report-exit-diagnostics'
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def record(p):return json.loads(p.read_bytes() if p.exists() else gzip.decompress(Path(str(p)+'.gz').read_bytes()))
v=record(e/'validation-summary.json');source=v['test_source_revision'];producer=v['producer_source_revision'];assert source!=producer and v['status']=='pass' and not v['product_rebuilt'] and not v['full_product_suite_rerun'] and not v['owner_accepted'] and not v['unit_complete'] and not v['original_failure_cause_established']
inputs=record(e/'qualification/source-inputs.json');previous=record(root/'.aide/evidence/2026-10-12-inventory-completion/reproduction-f7b4376f/source-inputs.json');assert inputs.keys()==previous.keys() and len(inputs)==493
assert {n for n in inputs if inputs[n]!=previous[n]}==set(v['changed_inputs'])=={'tests/evidence/test_report_process.py','tests/evidence/test_report_worker.py','tests/frontend/test_product_export.py'}
raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(source+':'+n for n in inputs)+'\n').encode());at=0
for n,d in inputs.items():
 end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob';size=int(header[2]);data=raw[end+1:end+1+size];at=end+size+2;assert sha(data)==d and sha((root/n).read_bytes())==d,n
for f in v['artifacts']:assert sha((root/f['path']).read_bytes())==f['sha256'] and f['source_revision']==producer
owned=record(e/'qualification/owned-process.json');joined=record(e/'qualification/joined-product.json');baseline=record(root/'.aide/evidence/2026-10-12-joined-report-waits/isolated-1/results.json')
assert owned['passed'] and owned['checks']==18 and all(x['passed'] for x in owned['observations'])
assert joined['passed'] and joined['checks']==v['joined_product_checks']==len(joined['observations']) and joined['source_revision']==source and not joined['source_dirty'] and all(x['passed'] for x in joined['observations'])
assert {x['name'] for x in joined['observations']}=={x['name'] for x in baseline['observations']}
assert all(x['exit_code']==0 for x in record(e/'qualification/commands.json'))
inv=record(e/'inventory.json')
for f in inv['evidence']+v['artifacts']:
 data=(root/f['path']).read_bytes();assert len(data)==f['bytes'] and sha(data)==f['sha256']
for f in record(e/'compression-map.json'):
 data=gzip.decompress((root/f['encoded_path']).read_bytes());assert len(data)==f['decoded_bytes'] and sha(data)==f['decoded_sha256']
target=':' if a.index else 'HEAD:'
for f in inv['evidence']+[dict(path=(e/'inventory.json').relative_to(root).as_posix(),sha256=sha((e/'inventory.json').read_bytes()))]:assert sha(subprocess.check_output(['git','show',target+f['path']]))==f['sha256']
import jsonschema
h=root/'.aide/handoffs/DE-W030-report-exit-diagnostics-2026-10-12.json';handoff=record(h);jsonschema.Draft202012Validator(record(root/'spec/schemas/handoff.schema.json')).validate(handoff);assert handoff['status']=='partial' and not handoff['blockers']
assert subprocess.check_output(['git','show',target+h.relative_to(root).as_posix()])==h.read_bytes()
for f in handoff['artifacts']:assert sha((root/f['path']).read_bytes())==f['sha256']
print(json.dumps(dict(status='pass',test_source_revision=source,producer_source_revision=producer,source_inputs=len(inputs),retained_files=len(inv['evidence'])+1,owned_checks=18,joined_checks=joined['checks'],original_failure_cause_established=False)))
