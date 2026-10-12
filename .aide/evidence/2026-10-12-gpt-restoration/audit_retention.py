"""Read-only owned GPT restoration/source/receipt/journal audit."""
import argparse,gzip,hashlib,json,struct,subprocess,tarfile
from pathlib import Path
import jsonschema
p=argparse.ArgumentParser();p.add_argument('--index',action='store_true');p.add_argument('--historical',action='store_true');a=p.parse_args();root=Path.cwd();e=root/'.aide/evidence/2026-10-12-gpt-restoration'
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def record(p):return json.loads(p.read_bytes() if p.exists() else gzip.decompress(Path(str(p)+'.gz').read_bytes()))
v=record(e/'validation-summary.json');source=v['source_revision'];r=e/('reproduction-'+source[:8]);inputs=record(r/'source-inputs.json');blobs=record(r/'source-blob-bindings.json');assert inputs.keys()==blobs.keys() and len(inputs)==v['source_inputs']
raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(source+':'+n for n in inputs)+'\n').encode());at=0
for n,d in inputs.items():
 end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob';size=int(header[2]);data=raw[end+1:end+size+1];at=end+size+2;assert sha(data)==d and hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blobs[n]
 if not a.historical:assert sha((root/n).read_bytes())==d,n
assert v['status']=='pass' and v['private_owned_effects_implemented'] and v['unrelated_bytes_preserved'] and not v['writer_admitted'] and not v['qualifies_recovery'] and not v['owner_accepted'] and not v['unit_complete']
identity=record(r/'build-identity.json');assert identity['identity']['source_revision']==source and identity['identity']['source_state']=='clean' and len(identity['inputs'])==v['product_inputs']
assert all(inputs[n]==d for n,d in identity['inputs'].items())
focused=record(r/'gpt-effects-results.json');assert focused['passed'] and focused['cases']==190 and len(focused['records'])==190
probe=next(x for x in v['artifacts'] if x['kind']=='gpt-effects');assert focused['probe_sha256']==probe['sha256']
names={x['name'] for x in focused['records']};assert {'repeat-old-admission','readonly-critical-review','readonly-critical-completion','readonly-torn-header','readonly-torn-tail','readonly-swapped-object-refused','readonly-hardlink-refused','basis-binding-before-create','device-path','unc-path','max-array'}<=names
normal=next(x for x in focused['records'] if x['name']=='512-primary');stages=[x['stage'] for x in normal['finish']['events'] if '.write.' in x['stage'] or '.flush.' in x['stage']]
for stage in stages:
 for action in ('crash_before','crash_after','before_error','after_error'):
  assert any(x.get('fault')==dict(stage=stage,action=action) for x in focused['records'])
 if '.write.' in stage:assert any(x.get('fault')==dict(stage=stage,action='partial_error') for x in focused['records'])
assert sum(x.get('exit_code')==112 for x in focused['records'])>=60
for x in focused['records']:
 if 'preparation' not in x:continue
 prepared=x['preparation'];manifest=prepared['manifest'];definition=prepared['definition'];review=x['review'];grant=x['grant'];assert manifest['executor_digest']==probe['sha256'] and manifest['source_revision']==source and not manifest['storage_independent']
 assert prepared['plan_digest']==sha(json.dumps(definition,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()) and not prepared['execution_authorized']
 assert all(not definition[k] for k in ('authorizes_effects','writer_admitted','qualifies_recovery','qualifies_durability'))
 raw=bytes.fromhex(x['journal_hex']);assert sha(raw)==x.get('journal_sha256',sha(raw))
 if 'backup_hex' in x:assert len(bytes.fromhex(x['backup_hex']))==x['backup_bytes'] and sha(bytes.fromhex(x['backup_hex']))==x['backup_sha256']
 if 'inspection' in x:
  inspection=x['inspection'];assert not inspection['authorizes_effects'] and not inspection['qualifies_power_loss'] and not inspection['qualifies_recovery']
 if len(raw)<192:continue
 assert raw[:8]==b'DEJPR001' and raw[160:192]==hashlib.sha256(raw[:160]).digest() and raw[40:72]==bytes.fromhex(prepared['plan_digest'][7:]) and raw[24:40]==bytes.fromhex(manifest['journal_identity'][7:])[:16]
 resources=dict(root=manifest['root_identity'],image=manifest['image_identity'],backup=manifest['backup_identity'],journal=manifest['journal_identity'],image_bytes=manifest['image_bytes']);code=dict(provider=manifest['provider_id'],executor=manifest['executor_digest'])
 canonical=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
 assert raw[72:104]==hashlib.sha256(canonical(resources)).digest() and raw[104:136]==hashlib.sha256(canonical(code)).digest()
 at=192;previous=raw[160:192];number=0;bootstrap=[definition,review,grant];rejected=x['name'].startswith('readonly-critical-')
 while at<len(raw):
  if len(raw)-at<112:break
  prefix=raw[at:at+112];assert prefix[:4]==b'JREC';kind,flags,prefix_bytes,length,sequence=struct.unpack_from('<HHIIQ',prefix,4);assert flags==1 and prefix_bytes==112 and sequence==number+1 and prefix[24:40]==bytes.fromhex(manifest['publisher_identity']) and struct.unpack_from('<Q',prefix,40)[0]==int(manifest['publisher_epoch']) and prefix[48:80]==previous
  if len(raw)-at<144+length:break
  payload=raw[at+112:at+112+length];trailer=raw[at+112+length:at+144+length];assert hashlib.sha256(payload).digest()==prefix[80:112] and hashlib.sha256(raw[160:192]+prefix+payload).digest()==trailer;value=json.loads(payload);assert canonical(value)==payload
  if rejected and sequence==int(x['inspection']['journal']['records'])+1:break
  if number<3:assert kind==number+1 and value==bootstrap[number]
  else:assert value['plan_digest']==prepared['plan_digest'] and value.get('backup_digest')==prepared['backup_digest']
  number+=1;at+=144+length;previous=trailer
 assert number==int(x['inspection']['journal']['records']),x['name']

restoration=record(r/'gpt-restoration-results.json');assert restoration['passed'] and restoration['cases']==138 and len(restoration['records'])==138 and restoration['probe_sha256']==probe['sha256']
assert v['private_restoration_implemented'] and v['original_artifacts_preserved'] and v['gpt_restoration_cases']==138
names={x['name'] for x in restoration['records']};assert {'512-primary','512-backup','4096-primary','4096-backup','completed-refused','cancelled-prefix','already-original','foreign-byte-refused','backup-refused','history-refused','repeated-first','repeated-second','snapshot-changed-after-review','identity-changed-after-review','journal-collision-refused','large-restoration-2'}<=names
assert sum(x['exit_code']==112 for x in restoration['records'])==51
normal=next(x for x in restoration['records'] if x['name']=='512-primary');stages=[x['stage'] for x in normal['finish']['events'] if '.write.' in x['stage'] or '.flush.' in x['stage']];assert len(stages)==24
for stage in stages:
 for action in ('crash_before','crash_after','before_error','after_error'):
  assert any(x.get('fault')==dict(stage=stage,action=action) for x in restoration['records'])
 if '.write.' in stage:assert any(x.get('fault')==dict(stage=stage,action='partial_error') for x in restoration['records'])
canonical=lambda value:json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
for x in restoration['records']:
 prepared=x['preparation'];store=x['store'];raw=bytes.fromhex(x['journal_hex'])
 if prepared is None:assert not raw and not store and x['exit_code']==3;continue
 d=prepared['definition'];m=d['resources'];review=x['review'];grant=x['grant'];dg=prepared['restoration_digest']
 assert dg==sha(canonical(d)) and not prepared['execution_authorized'] and not any('.write.' in t['stage'] or '.flush.' in t['stage'] for t in prepared['events'])
 assert m['executor_digest']==probe['sha256'] and m['source_revision']==source and not m['storage_independent']
 assert not any(d[k] for k in ('restores_healthy_gpt','product_writes_admitted','qualifies_power_loss','qualifies_recovery'))
 assert d['original_manifest_digest']==sha(canonical(m)) and d['inspection_digest']==sha(canonical(prepared['original_inspection']))
 assert d['original_image_digest']==m['image_before_sha256']==x['original_image_sha256'] and d['observed_image_digest']==x['image_before_sha256']
 assert d['backup_digest']==x['old_artifacts_sha256']['backup.bin'] and d['original_journal_digest']==x['old_artifacts_sha256']['journal.bin']
 assert d['journal_name']=='recovery-'+d['attempt_id']+'.bin' and len(d['attempt_id'])==32
 assert review['restoration_digest']==dg and review['observed_image_digest']==d['observed_image_digest'] and review['reviewed'] and review['issuer']=='fixture-controller'
 assert grant['restoration_digest']==dg and grant['review_digest']==sha(canonical(review)) and grant['original_manifest_digest']==d['original_manifest_digest'] and grant['executor_digest']==probe['sha256'] and grant['patch_ids']==[p['id'] for p in d['patches']]
 assert grant['allow_fixture_restoration'] and grant['allow_new_recovery_journal'] and grant['acknowledge_nonatomic_same_volume']
 for i,patch in enumerate(d['patches']):assert patch['depends_on']==([] if i==0 else [d['patches'][i-1]['id']]) and int(patch['bytes'])>0 and int(patch['offset'])+int(patch['bytes'])<=int(m['image_bytes'])
 if not store:assert not raw;continue
 assert store['name']==d['journal_name'] and store['executor_digest']==probe['sha256'] and not store['storage_independent'] and store['identity'] not in [m[k] for k in ('root_identity','image_identity','backup_identity','journal_identity')]
 if len(raw)<192:continue
 assert raw[:8]==b'DEJPR001' and raw[160:192]==hashlib.sha256(raw[:160]).digest() and raw[24:40]==bytes.fromhex(store['identity'][7:])[:16] and raw[40:72]==bytes.fromhex(dg[7:])
 assert raw[72:104]==hashlib.sha256(canonical(dict(original=m,recovery_store=store))).digest() and raw[104:136]==hashlib.sha256(canonical(dict(provider=m['provider_id'],executor=store['executor_digest']))).digest()
 at=192;previous=raw[160:192];n=0;confirmed=0;pending=False;sealed=False;expected_image=d['observed_image_digest']
 while at<len(raw):
  if len(raw)-at<112:break
  prefix=raw[at:at+112];assert prefix[:4]==b'JREC';kind,flags,header,length,seq=struct.unpack_from('<HHIIQ',prefix,4);assert flags==1 and header==112 and seq==n+1 and prefix[24:40]==bytes.fromhex(store['publisher_identity']) and struct.unpack_from('<Q',prefix,40)[0]==int(store['publisher_epoch']) and prefix[48:80]==previous
  if len(raw)-at<144+length:break
  payload=raw[at+112:at+112+length];trailer=raw[at+112+length:at+144+length];assert prefix[80:112]==hashlib.sha256(payload).digest() and trailer==hashlib.sha256(raw[160:192]+prefix+payload).digest();value=json.loads(payload);assert payload==canonical(value) and not sealed
  if n<3:assert kind==n+1 and value==[d,review,grant][n]
  elif n==3:assert kind==4 and value==dict(schema='org.disked.gpt-restoration-admission/1',restoration_digest=dg,review_digest=sha(canonical(review)),grant_digest=sha(canonical(grant)),store=store)
  elif kind==5:
   assert not pending and confirmed<len(d['patches']) and value['event']=='intention' and int(value['prefix'])==confirmed and value['image_digest']==expected_image and value['patch']==d['patches'][confirmed];pending=True
  elif kind==6:
   assert pending and value['event']=='completion' and int(value['prefix'])==confirmed+1 and value['patch']==d['patches'][confirmed];confirmed+=1;pending=False;expected_image=value['image_digest']
  else:assert kind==9 and value['event']=='seal-restored-basis' and int(value['prefix'])==confirmed==len(d['patches']) and not pending and value['image_digest']==d['original_image_digest'];sealed=True
  if n>=3:assert value['restoration_digest']==dg
  n+=1;at+=144+length;previous=trailer
 finish=x['finish']
 if x['exit_code']==0 and d['patches']:assert sealed and at==len(raw) and x['image_after_sha256']==d['original_image_digest'] and finish['restoration']['status']=='restored_original_basis'
for name in ('gpt-restoration-initial-tests.json','gpt-restoration-expanded-tests.json'):assert not record(e/'initial-diagnostics'/name)['passed']
assert record(e/'initial-diagnostics/gpt-restoration-second-tests.json')['passed']
assert record(e/'initial-diagnostics/gpt-restoration-final-initial-tests.json')['passed']
assert all(x['exit_code']==0 for x in record(r/'commands.json'));assert b'0 tests failed out of 81' in (r/'logs/product-parallel.log').read_bytes()
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
name='.aide/handoffs/DE-W042-gpt-restoration-2026-10-12.json';h=record(root/name);jsonschema.Draft202012Validator(record(root/'spec/schemas/handoff.schema.json')).validate(h);assert h['status']=='partial' and not h['blockers']
for x in h['artifacts']:assert sha((root/x['path']).read_bytes())==x['sha256']
target=':' if a.index else 'HEAD:';requests=[(target+x['path'],x['sha256']) for x in inv['evidence']];requests += [(target+n,sha((root/n).read_bytes())) for n in [name,(e/'inventory.json').relative_to(root).as_posix(),'.aide/programmes/disked-0.1.0.json','docs/development-plan.md','TODO.MD']]
raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(n for n,d in requests)+'\n').encode());at=0
for n,d in requests:
 end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob',n;size=int(header[2]);data=raw[end+1:end+size+1];at=end+size+2;assert sha(data)==d,n
print(json.dumps(dict(status='pass',source_revision=source,historical_source_only=a.historical,tree='index' if a.index else 'HEAD',source_inputs=len(inputs),retained_files=len(inv['evidence'])+1,gpt_effect_cases=190,gpt_restoration_cases=138,product_groups=81,artifacts=len(v['artifacts']),owner_accepted=False,unit_complete=False)))
