"""Read-only native caller coexistence/source/quota/evidence audit."""
import argparse,gzip,hashlib,json,struct,subprocess,tarfile
from pathlib import Path
import jsonschema
p=argparse.ArgumentParser();p.add_argument('--index',action='store_true');p.add_argument('--historical',action='store_true');a=p.parse_args();root=Path.cwd();e=root/'.aide/evidence/2026-10-12-gpt-repair-command'
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def record(p):return json.loads(p.read_bytes() if p.exists() else gzip.decompress(Path(str(p)+'.gz').read_bytes()))
v=record(e/'validation-summary.json');source=v['source_revision'];r=e/('reproduction-'+source[:8]);inputs=record(r/'source-inputs.json');blobs=record(r/'source-blob-bindings.json');assert inputs.keys()==blobs.keys() and len(inputs)==v['source_inputs']
raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(source+':'+n for n in inputs)+'\n').encode());at=0
for n,d in inputs.items():
 end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob';size=int(header[2]);data=raw[end+1:end+size+1];at=end+size+2;assert sha(data)==d and hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blobs[n]
 if not a.historical:assert sha((root/n).read_bytes())==d,n
assert v['status']=='pass' and v['public_preview_implemented'] and v['source_preserved'] and not v['writer_admitted'] and not v['qualifies_recovery'] and not v['owner_accepted'] and not v['unit_complete']
identity=record(r/'build-identity.json');assert identity['identity']['source_revision']==source and identity['identity']['source_state']=='clean' and len(identity['inputs'])==v['product_inputs']
assert all(inputs[n]==d for n,d in identity['inputs'].items())
focused=record(r/'gpt-repair-command-results.json');assert focused['passed'] and focused['cases']==59 and len(focused['records'])==59
names=[x['name'] for x in focused['records']];assert all(n in names for n in ['gui-preview','tui-preview','shell-preview','stdio-expired-preview-slot','stdio-preview'])
late=next(x for x in focused['records'] if x['name']=='stdio-expired-preview-slot');assert late['expired']['status']=='unknown' and late['expired']['operation_id'] is None and late['busy']['diagnostics'][0]['code']=='request_resource_limit' and late['release_observations'][-1]['status']=='completed'
for x in focused['records']:
 if 'response' in x or 'observation' in x:
  value=x.get('response',x.get('observation',{}).get('response'));definition=value['result']['definition'];encoded=json.dumps(definition,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode();assert value['result']['plan_digest']==sha(encoded) and not definition['authorizes_effects'] and not definition['writer_admitted']
failed=e/'initial-diagnostics/failed-clean-721a2c48';old_art=record(failed/'failed-product-artifact.json');data=(root/old_art['path']).read_bytes();assert len(data)==old_art['bytes'] and sha(data)==old_art['sha256'] and old_art['source_revision']=='721a2c485cfc5f91980a589f0617cfd71b767cc5'
assert b'2 tests failed out of 79' in (failed/'logs/product-parallel.log').read_bytes()
assert any(x['name']=='product-parallel' and x['exit_code']==8 for x in record(failed/'commands.json'))
discovery=record(failed/'discovery.stdout');assert sum(c['availability']=='available' for c in discovery['result']['commands'])==21
assert not record(e/'initial-diagnostics/gpt-command-initial-tests.json')['passed']
assert record(e/'initial-diagnostics/gpt-command-tests-final-initial.json')['passed']
assert all(x['exit_code']==0 for x in record(r/'commands.json'));assert b'0 tests failed out of 79' in (r/'logs/product-parallel.log').read_bytes()
arch=record(e/'context-archive.json');data=(root/arch['archive_path']).read_bytes();assert len(data)==arch['bytes'] and sha(data)==arch['sha256']
with tarfile.open(root/arch['archive_path'],'r:gz') as tar:
 members=tar.getmembers();assert len(members)==arch['files'] and all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members)
 manifest=json.loads(tar.extractfile('manifest.json').read());payload=tar.extractfile('context.md').read();assert manifest['git_head']==source and not manifest['git_dirty'] and len(payload)==manifest['payload_bytes']==arch['context_bytes'] and sha(payload)==manifest['payload_sha256']
 requests=[source+':'+item['path'] for item in manifest['files']];raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(requests)+'\n').encode());at=0
 for item in manifest['files']:
  end=raw.index(b'\n',at);head=raw[at:end].split();assert len(head)==3 and head[1]==b'blob',item['path'];length=int(head[2]);content=raw[end+1:end+length+1];at=end+length+2;assert len(content)==item['bytes'] and sha(content)==item['sha256'],item['path']
  if item['delivery']=='artifact':assert tar.extractfile('artifacts/'+item['path']).read()==content,item['path']
inv=record(e/'inventory.json')
for x in inv['evidence']+v['artifacts']:
 data=(root/x['path']).read_bytes();assert len(data)==x['bytes'] and sha(data)==x['sha256'],x['path']
for x in record(e/'compression-map.json'):
 data=gzip.decompress((root/x['encoded_path']).read_bytes());assert len(data)==x['decoded_bytes'] and sha(data)==x['decoded_sha256']
for x in v['artifacts']:
 data=(root/x['path']).read_bytes();offset=struct.unpack_from('<I',data,60)[0];assert data[offset:offset+4]==b'PE\0\0' and struct.unpack_from('<H',data,offset+4)[0]==0x8664 and x['source_revision']==source
name='.aide/handoffs/DE-W041-gpt-repair-command-2026-10-12.json';h=record(root/name);jsonschema.Draft202012Validator(record(root/'spec/schemas/handoff.schema.json')).validate(h);assert h['status']=='partial' and not h['blockers']
for x in h['artifacts']:assert sha((root/x['path']).read_bytes())==x['sha256']
target=':' if a.index else 'HEAD:';requests=[(target+x['path'],x['sha256']) for x in inv['evidence']];requests += [(target+n,sha((root/n).read_bytes())) for n in [name,(e/'inventory.json').relative_to(root).as_posix(),'.aide/programmes/disked-0.1.0.json','docs/development-plan.md','docs/native-bootstrap.md','docs/getting-started.md','docs/command-experience.md','TODO.MD']]
raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(n for n,d in requests)+'\n').encode());at=0
for n,d in requests:
 end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob',n;size=int(header[2]);data=raw[end+1:end+size+1];at=end+size+2;assert sha(data)==d,n
print(json.dumps(dict(status='pass',source_revision=source,historical_source_only=a.historical,tree='index' if a.index else 'HEAD',source_inputs=len(inputs),retained_files=len(inv['evidence'])+1,gpt_command_cases=59,product_groups=79,artifacts=len(v['artifacts']),owner_accepted=False,unit_complete=False)))
