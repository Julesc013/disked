"""Read-only exact AIDE source, passive export and retained metadata audit."""
import argparse,gzip,hashlib,json,subprocess
from pathlib import Path
import jsonschema
p=argparse.ArgumentParser();p.add_argument('--index',action='store_true');a=p.parse_args();root=Path.cwd();e=root/'.aide/evidence/2026-10-12-aide-weekly'
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def record(p):return json.loads(p.read_bytes() if p.exists() else gzip.decompress(Path(str(p)+'.gz').read_bytes()))
v=record(e/'validation-summary.json');source=v['source_revision'];rev=v['aide_revision'];inputs=record(e/'qualification/source-inputs.json');assert len(inputs)==v['source_inputs']
raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(source+':'+n for n in inputs)+'\n').encode());at=0
for n,d in inputs.items():
 end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob';size=int(header[2]);data=raw[end+1:end+size+1];at=end+size+2;assert sha(data)==d and sha((root/n).read_bytes())==d,n
lock=record(root/'spec/references/aide-lock.json');assert lock['revision']==rev and lock['refresh']['next_review_date']=='2026-10-19' and not lock['qualification']['selected_stable_consumer_qualified']
upstream=root/lock['checkout']
for x in lock['files']:
 data=(e/'review'/x['path']).read_bytes();assert sha(data)==x['sha256'];assert subprocess.check_output(['git','show',rev+':'+x['path']],cwd=upstream)==data
schema=record(e/'review/.aide/protocol/aide-workunit.schema.json');validator=jsonschema.Draft202012Validator(schema);records=sorted((e/'qualification/export').glob('*.json'));assert len(records)==v['validated_workunits']==36
for p in records:
 x=record(p);validator.validate(x);assert x['spec']['authorizes_implementation'] is False and x['status']['phase']=='planned' and x['status']['result']=='NOT_RUN' and not x['status']['validated']
release=record(e/'review/release-api.json');assert release['tag_name']=='aide-lite-v1.0.0' and not release['draft'] and not release['prerelease'] and release['target_commitish']=='0f293eb6a99dbd444bfa35016007b13451c49275'
assert not v['upstream_code_executed'] and not v['live_import'] and not v['selected_stable_consumer_qualified'] and not v['unit_complete'] and not v['owner_accepted']
assert not v['native_product_input_comparison']['changed'] and not v['native_product_input_comparison']['product_rebuilt'] and not v['native_product_input_comparison']['product_suite_rerun']
previous=record(root/'.aide/evidence/2026-10-12-job-coexistence/reproduction-98a5b593/build-identity.json');assert all(sha((root/n).read_bytes())==d for n,d in previous['inputs'].items())
assert all(x['exit_code']==0 for x in record(e/'qualification/commands.json'))
inv=record(e/'inventory.json')
for x in inv['evidence']:
 data=(root/x['path']).read_bytes();assert len(data)==x['bytes'] and sha(data)==x['sha256']
for x in record(e/'compression-map.json'):
 data=gzip.decompress((root/x['encoded_path']).read_bytes());assert len(data)==x['decoded_bytes'] and sha(data)==x['decoded_sha256']
name='.aide/handoffs/DE-W061-aide-weekly-2026-10-12.json';h=record(root/name);jsonschema.Draft202012Validator(record(root/'spec/schemas/handoff.schema.json')).validate(h);assert h['status']=='partial' and not h['blockers']
for x in h['artifacts']:assert sha((root/x['path']).read_bytes())==x['sha256']
target=':' if a.index else 'HEAD:';requests=[(target+x['path'],x['sha256']) for x in inv['evidence']];requests += [(target+n,sha((root/n).read_bytes())) for n in [name,(e/'inventory.json').relative_to(root).as_posix(),'.aide/programmes/disked-0.1.0.json','docs/development-plan.md','TODO.MD']]
raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(n for n,d in requests)+'\n').encode());at=0
for n,d in requests:
 end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob',n;size=int(header[2]);data=raw[end+1:end+size+1];at=end+size+2;assert sha(data)==d,n
print(json.dumps(dict(status='pass',source_revision=source,aide_revision=rev,tree='index' if a.index else 'HEAD',source_inputs=len(inputs),retained_files=len(inv['evidence'])+1,passive_workunits=36,live_import=False,stable_consumer_qualified=False)))
