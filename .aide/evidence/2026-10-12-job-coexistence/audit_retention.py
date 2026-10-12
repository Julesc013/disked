"""Read-only native caller coexistence/source/quota/evidence audit."""
import argparse,gzip,hashlib,json,struct,subprocess
from pathlib import Path
import jsonschema
p=argparse.ArgumentParser();p.add_argument('--index',action='store_true');p.add_argument('--historical',action='store_true');a=p.parse_args();root=Path.cwd();e=root/'.aide/evidence/2026-10-12-job-coexistence'
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def record(p):return json.loads(p.read_bytes() if p.exists() else gzip.decompress(Path(str(p)+'.gz').read_bytes()))
v=record(e/'validation-summary.json');source=v['source_revision'];r=e/('reproduction-'+source[:8]);inputs=record(r/'source-inputs.json');blobs=record(r/'source-blob-bindings.json');assert inputs.keys()==blobs.keys() and len(inputs)==v['source_inputs']
raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(source+':'+n for n in inputs)+'\n').encode());at=0
for n,d in inputs.items():
 end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob';size=int(header[2]);data=raw[end+1:end+size+1];at=end+size+2;assert sha(data)==d and hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blobs[n]
 if not a.historical:assert sha((root/n).read_bytes())==d,n
assert v['status']=='pass' and v['private_frontend_job_qualified'] and v['shared_worker_limits_unchanged'] and not v['owner_accepted'] and not v['unit_complete']
identity=record(r/'build-identity.json');assert identity['identity']['source_revision']==source and identity['identity']['source_state']=='clean' and len(identity['inputs'])==v['product_inputs']
assert all(inputs[n]==d for n,d in identity['inputs'].items())
memory=record(r/'frontend-memory-results.json');quota=record(r/'worker-quota-results.json');assert memory['passed'] and memory['tests']==12 and quota['passed'] and quota['tests']==1
coexist=next(x for x in memory['observations'] if x['test'].startswith('independent host hierarchies'))
probe=coexist['private_job'];assert probe['ready'] and probe['private_job'] and probe['platform_code']=='0' and [probe[k] for k in ('flags','process_bytes','job_bytes','active_limit')]==['256','268435456','0','0']
for item in memory['observations']:
 if 'before' in item and 'after' in item and 'flags' in item['before']:
  assert all(item['before'][k]==item['after'][k] for k in ('flags','process_bytes','job_bytes','active_limit'))
pressure=next(x for x in memory['observations'] if x['test'].startswith('actual commit denial in private'));assert pressure['probe']['private_job'] and not pressure['probe']['ready'] and pressure['probe']['error']=='memory_budget_unavailable' and pressure['memory']['peak_commit_bytes']<=64*1024*1024
real=next(x for x in memory['observations'] if x['test'].startswith('actual product protocol'));assert real['protocol']['status']==real['discovery']['status']=='completed' and not real['protocol']['diagnostics'] and not real['discovery']['diagnostics']
budget=quota['observations'][0];assert budget['max_workers']==4 and budget['process_memory_limit']==128*1024*1024 and budget['job_memory_limit']==512*1024*1024
old=record(e/'initial-diagnostics/job-coexistence-before.json');assert old['passed'] and old['tests']==1;assert old['observations'][0]['response']['diagnostics'][0]['code']=='memory_budget_incompatible'
assert all(x['exit_code']==0 for x in record(r/'commands.json'));assert b'0 tests failed out of 78' in (r/'logs/product-parallel.log').read_bytes()
inv=record(e/'inventory.json')
for x in inv['evidence']+v['artifacts']:
 data=(root/x['path']).read_bytes();assert len(data)==x['bytes'] and sha(data)==x['sha256'],x['path']
for x in record(e/'compression-map.json'):
 data=gzip.decompress((root/x['encoded_path']).read_bytes());assert len(data)==x['decoded_bytes'] and sha(data)==x['decoded_sha256']
for x in v['artifacts']:
 data=(root/x['path']).read_bytes();offset=struct.unpack_from('<I',data,60)[0];assert data[offset:offset+4]==b'PE\0\0' and struct.unpack_from('<H',data,offset+4)[0]==0x8664 and x['source_revision']==source
name='.aide/handoffs/DE-W017-job-coexistence-2026-10-12.json';h=record(root/name);jsonschema.Draft202012Validator(record(root/'spec/schemas/handoff.schema.json')).validate(h);assert h['status']=='partial' and not h['blockers']
for x in h['artifacts']:assert sha((root/x['path']).read_bytes())==x['sha256']
target=':' if a.index else 'HEAD:';requests=[(target+x['path'],x['sha256']) for x in inv['evidence']];requests += [(target+n,sha((root/n).read_bytes())) for n in [name,(e/'inventory.json').relative_to(root).as_posix(),'.aide/programmes/disked-0.1.0.json','docs/development-plan.md','TODO.MD']]
raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(n for n,d in requests)+'\n').encode());at=0
for n,d in requests:
 end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob',n;size=int(header[2]);data=raw[end+1:end+size+1];at=end+size+2;assert sha(data)==d,n
print(json.dumps(dict(status='pass',source_revision=source,historical_source_only=a.historical,tree='index' if a.index else 'HEAD',source_inputs=len(inputs),retained_files=len(inv['evidence'])+1,memory_tests=12,quota_tests=1,product_groups=78,artifacts=len(v['artifacts']),owner_accepted=False,unit_complete=False)))
