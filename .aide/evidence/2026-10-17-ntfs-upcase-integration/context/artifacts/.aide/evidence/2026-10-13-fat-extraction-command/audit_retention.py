"""Audit retained exact-source public prototype extraction evidence; no native rerun."""
import hashlib,json,subprocess
from pathlib import Path
e=Path(__file__).resolve().parent;root=e.parents[2]
sha=lambda b:'sha256:'+hashlib.sha256(b).hexdigest()
s=json.loads((e/'summary.json').read_bytes());source=s['source_revision']
assert s['passed'] and s['source_state']=='clean' and s['native_test_groups']==106
assert s['independent_header_compilations']==20 and s['product_dispatch_admitted']
assert not s['physical_device_access'] and not s['owner_accepted'] and not s['release_ready']
c=json.loads((e/'fat-extraction-command-cases.json').read_bytes())
assert c['passed'] and c['checks']>=70 and len(c['records'])==c['checks'] and len(c['verified_copies'])==11
assert any(r['name']=='real-cancel-resume' and r['observed_prefix']>0 for r in c['records'])
assert all(any(r['name']=='native-'+name and r['phase']=='execute' for r in c['records']) for name in ('gui','tui','shell'))
inputs=json.loads((e/'source-inputs.json').read_bytes());bindings=json.loads((e/'source-blob-bindings.json').read_bytes());assert set(inputs)==set(bindings)
raw=subprocess.check_output(['git','cat-file','--batch'],cwd=root,input=('\n'.join(source+':'+p for p in inputs)+'\n').encode());at=0
for p,digest in inputs.items():
 end=raw.index(b'\n',at);parts=raw[at:end].split();assert parts[1]==b'blob'
 n=int(parts[2]);data=raw[end+1:end+1+n];at=end+n+2;assert sha(data)==digest and parts[0].decode()==bindings[p],p
identity=json.loads((e/'build-identity.json').read_bytes());assert identity['identity']['source_revision']==source and identity['identity']['source_state']=='clean'
assert identity['inputs']=={p:inputs[p] for p in identity['inputs']}
commands=json.loads((e/'commands.json').read_bytes());assert all(r['exit_code']==0 for r in commands)
failed=json.loads((e/'failed-27499f20/receipt.json').read_bytes())
assert failed['source_revision']=='27499f20b578c152096c9d0d20b1a702340faf19' and failed['status']=='failed_validation'
assert failed['native_groups']==106 and failed['passed_groups']==104 and failed['exit_code']==8
assert failed['failed_groups']==['disked.acceptance','disked_provider_guard.acceptance']
assert json.loads((e/'failed-27499f20/commands.json').read_bytes())[-1]['exit_code']==8
assert '100% tests passed' in (e/'logs/native-tests.log').read_text(encoding='utf-8')
inventory=json.loads((e/'retention.json').read_bytes());assert inventory['source_revision']==source
actual={p.relative_to(e).as_posix() for p in e.rglob('*') if p.is_file() and '__pycache__' not in p.parts}-{'retention.json'}
assert actual==set(inventory['files'])
for p,digest in inventory['files'].items():assert sha((e/p).read_bytes())==digest,p
print(json.dumps(dict(status='PASS',source_revision=source,source_bindings=len(inputs),retained_files=len(actual),native_groups=106,verified_complete_files=11),indent=2))
