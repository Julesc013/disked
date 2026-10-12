"""Read-only audit of exact-source GPT planning and retained native evidence."""
import argparse,gzip,hashlib,json,struct,subprocess
from pathlib import Path
import jsonschema
p=argparse.ArgumentParser();p.add_argument('--index',action='store_true');p.add_argument('--historical',action='store_true');a=p.parse_args();root=Path.cwd();e=root/'.aide/evidence/2026-10-12-gpt-repair-planning'
def sha(data):return 'sha256:'+hashlib.sha256(data).hexdigest()
def record(p):return json.loads(p.read_bytes() if p.exists() else gzip.decompress(Path(str(p)+'.gz').read_bytes()))
v=record(e/'validation-summary.json');source=v['source_revision'];r=e/('reproduction-'+source[:8]);inputs=record(r/'source-inputs.json');blobs=record(r/'source-blob-bindings.json');assert inputs.keys()==blobs.keys() and len(inputs)==v['source_inputs']==417
raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(source+':'+n for n in inputs)+'\n').encode());at=0
for name,expected in inputs.items():
 end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob';size=int(header[2]);data=raw[end+1:end+1+size];at=end+size+2
 assert sha(data)==expected and hashlib.sha1(b'blob '+str(len(data)).encode()+b'\0'+data).hexdigest()==blobs[name],name
 if not a.historical:assert sha((root/name).read_bytes())==expected,name
inv=record(e/'inventory.json')
for item in inv['evidence']+v['artifacts']:
 data=(root/item['path']).read_bytes();assert len(data)==item['bytes'] and sha(data)==item['sha256'],item['path']
for item in record(e/'compression-map.json'):
 data=gzip.decompress((root/item['encoded_path']).read_bytes());assert len(data)==item['decoded_bytes'] and sha(data)==item['decoded_sha256']
assert not any(f.suffix.lower() in ('.exe','.dll','.obj','.pdb','.img') for f in e.rglob('*') if f.is_file())
assert v['status']=='pass' and v['ctest_groups']==78 and not v['writer_admitted'] and not v['public_command_admitted'] and not v['qualifies_recovery'] and not v['unit_complete'] and not v['owner_accepted'] and not v['earlier_parallel_failure_cause_established']
result=record(r/'gpt-repair-results.json');assert result['passed'] and result['tests']==16 and result['executions']==107 and len(result['outputs'])==len(result['inputs'])==107
assert all(x['exit_code'] in (0,3) and x['output_bytes']>0 for x in result['outputs'])
identity=record(r/'build-identity.json');assert identity['identity']['source_revision']==source and identity['identity']['source_state']=='clean' and len(identity['inputs'])==410
assert all(inputs[n]==value for n,value in identity['inputs'].items())
for artifact in v['artifacts']:
 data=(root/artifact['path']).read_bytes();pe=struct.unpack_from('<I',data,60)[0];assert data[pe:pe+4]==b'PE\0\0' and struct.unpack_from('<H',data,pe+4)[0]==0x8664 and artifact['source_revision']==source
assert result['probe_sha256']==next(x['sha256'] for x in v['artifacts'] if x['kind']=='gpt-repair')
commands=record(r/'commands.json');assert all(x['exit_code']==0 for x in commands)
log=(r/'logs/product-parallel.log').read_bytes();assert b'0 tests failed out of 78' in log
discovery=record(e/'initial-diagnostics/gpt-repair-discovery-after-campaign.stdout');row=next(x for x in discovery['result']['commands'] if x['id']=='table.gpt.repair.plan');assert row['availability']=='unavailable' and not discovery['diagnostics']
assert not (e/'initial-diagnostics/gpt-repair-discovery-after-campaign.stderr').read_bytes()
initial=record(e/'initial-diagnostics/gpt-repair-initial-tests.json');assert not initial['passed']
initial=record(e/'initial-diagnostics/gpt-repair-geometry-tests.json');assert not initial['passed']
name='.aide/handoffs/DE-W041-gpt-repair-planning-2026-10-12.json';handoff=record(root/name);jsonschema.Draft202012Validator(record(root/'spec/schemas/handoff.schema.json')).validate(handoff);assert handoff['status']=='partial' and not handoff['blockers']
for x in handoff['artifacts']:assert sha((root/x['path']).read_bytes())==x['sha256']
target=':' if a.index else 'HEAD:';requests=[(target+x['path'],x['sha256']) for x in inv['evidence']];requests += [(target+path,sha((root/path).read_bytes())) for path in [name,(e/'inventory.json').relative_to(root).as_posix(),'.aide/programmes/disked-0.1.0.json','docs/development-plan.md','TODO.MD']]
raw=subprocess.check_output(['git','cat-file','--batch'],input=('\n'.join(n for n,d in requests)+'\n').encode());at=0
for name,expected in requests:
 end=raw.index(b'\n',at);header=raw[at:end].split();assert len(header)==3 and header[1]==b'blob',name;size=int(header[2]);data=raw[end+1:end+1+size];at=end+size+2;assert sha(data)==expected,name
print(json.dumps(dict(status='pass',source_revision=source,tree='index' if a.index else 'HEAD',historical_source_only=a.historical,source_inputs=len(inputs),retained_files=len(inv['evidence'])+1,artifacts=2,gpt_tests=16,gpt_executions=107,product_groups=78,writer_admitted=False,unit_complete=False)))
