"""Audit exact-source tree-session qualification without rerunning native tests."""
import hashlib,json,subprocess
from pathlib import Path
e=Path(__file__).resolve().parent;root=e.parents[2]
sha=lambda b:'sha256:'+hashlib.sha256(b).hexdigest()
s=json.loads((e/'summary.json').read_bytes());source=s['source_revision']
assert s['passed'] and s['source_state']=='clean' and s['native_test_groups']==113
assert s['independent_header_compilations']==26 and s['maximum_publication_bytes']>8388608
assert not any(s[k] for k in ('physical_device_access','owner_accepted','release_ready','recursive_extraction_qualified'))
c=json.loads((e/'fat-tree-session-cases.json').read_bytes());assert c['passed'] and c['observations']==s['session_observations'] and len(c['journeys'])==4
assert c['journeys'][-1]['records']==17601 and c['journeys'][-1]['input_requests']==1 and c['journeys'][-1]['event_envelopes']>256
assert {'native-gui','native-tui','native-shell','complete-cli-stream'}<=set(r.get('kind') for r in c['records'])
supplement=json.loads((e/'startup-late.json').read_bytes());assert supplement['passed'] and len(supplement['scenarios'])==4
assert supplement['exe_sha256']==next(x['sha256'] for x in s['artifacts'] if x['kind']=='disked_tree_test')
inputs=json.loads((e/'source-inputs.json').read_bytes());bindings=json.loads((e/'source-blob-bindings.json').read_bytes());assert set(inputs)==set(bindings)
raw=subprocess.check_output(['git','cat-file','--batch'],cwd=root,input=('\n'.join(source+':'+p for p in inputs)+'\n').encode());at=0
for p,digest in inputs.items():
 end=raw.index(b'\n',at);parts=raw[at:end].split();assert parts[1]==b'blob';n=int(parts[2]);data=raw[end+1:end+1+n];at=end+n+2
 assert sha(data)==digest and parts[0].decode()==bindings[p],p
identity=json.loads((e/'build-identity.json').read_bytes());assert identity['identity']['source_revision']==source and identity['identity']['source_state']=='clean'
assert identity['inputs']=={p:inputs[p] for p in identity['inputs']}
assert all(r['exit_code']==0 for r in json.loads((e/'commands.json').read_bytes()))
assert '100% tests passed' in (e/'logs/native-tests.log').read_text(encoding='utf-8')
inventory=json.loads((e/'retention.json').read_bytes());assert inventory['source_revision']==source
actual={p.relative_to(e).as_posix() for p in e.rglob('*') if p.is_file() and '__pycache__' not in p.parts}-{'retention.json'};assert actual==set(inventory['files'])
for p,digest in inventory['files'].items():assert sha((e/p).read_bytes())==digest,p
print(json.dumps(dict(status='PASS',source_revision=source,source_bindings=len(inputs),retained_files=len(actual),native_groups=113,session_observations=c['observations']),indent=2))
