"""Verify exact retained private volume-adapter evidence and current projection."""
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3]
mode=sys.argv[1] if len(sys.argv)>1 else 'files'
assert mode in ('files','staged','head')
prefix='.aide/evidence/2026-10-10-nt-volume-namespace'
source='17129e6eaa6cfb5786cbf1f022fb38eb25fd286f'
git_bytes={}
def data(name):
    if mode=='files' or name.startswith('.aide-local/'):
        return (root/name).read_bytes()
    if name not in git_bytes:
        git_bytes[name]=subprocess.check_output(['git','show',(':' if mode=='staged' else 'HEAD:')+name],cwd=root)
    return git_bytes[name]
def sha(value):return 'sha256:'+hashlib.sha256(value).hexdigest()
def read(name):return json.loads(data(name))
inventory=read(prefix+'/inventory.json')
handoff=read('.aide/handoffs/DE-W030-nt-volume-namespace-2026-10-10.json')
if mode!='files':
    # Read exact blob bytes in one process. Preserve empty and binary payloads;
    # do not decode Git contents or depend on checkout newline conversion.
    names=sorted({row['path'] for row in inventory['evidence_files']+inventory['artifacts']+handoff['artifacts']
        if not row['path'].startswith('.aide-local/')})
    assert all('\n' not in name and '\r' not in name for name in names)
    refs=[(':' if mode=='staged' else 'HEAD:')+name for name in names]
    batch=subprocess.run(['git','cat-file','--batch'],cwd=root,input=('\n'.join(refs)+'\n').encode('utf-8'),capture_output=True,check=True).stdout
    at=0
    for name in names:
        end=batch.index(b'\n',at);header=batch[at:end].split();assert len(header)==3 and header[1]==b'blob',name
        count=int(header[2]);at=end+1;git_bytes[name]=batch[at:at+count];at+=count
        assert batch[at:at+1]==b'\n',name;at+=1
    assert at==len(batch)
assert inventory['source_revision']==source
assert handoff['spec_manifest_digest']==sha(data('spec/manifest.json'))
assert not handoff['performed_remote_writes'] and handoff['status']=='partial'
for row in inventory['evidence_files']+inventory['artifacts']:
    value=data(row['path'])
    assert len(value)==row['bytes'] and sha(value)==row['sha256'],row['path']
for row in handoff['artifacts']:
    assert sha(data(row['path']))==row['sha256'],row['path']
inputs=read(prefix+'/reproduction-17129e6/source-inputs.json')
for name,value in inputs.items():
    blob=subprocess.check_output(['git','show',source+':'+name],cwd=root)
    assert sha(blob)==value and sha(data(name))==value,name
result=read(prefix+'/reproduction-17129e6/results.json')
assert result['status']=='pass' and result['source_revision']==source
assert result['source_inputs']==len(inputs)==11
assert result['host']==dict(identity='BLACKGLASS-WIN1\\Jules',elevated=False)
assert result['campaigns']==[
    dict(architecture='x64',native_executions=49,assertions=258,pointer_bytes=8),
    dict(architecture='Win32',native_executions=49,assertions=258,pointer_bytes=4)]
assert result['tooling_tests']==dict(run=215,passed=213,skipped=2)
assert result['structural_checks']==1043 and result['native_table_bound']
assert not any(result[key] for key in ('live_namespace_qualified','physical_access','product_native_rebuilt',
    'XP_qualified','provider_admitted','unit_complete','owner_accepted','remote_writes'))
programme=read('.aide/programmes/disked-0.1.0.json')
assert programme['status']=='active' and programme['current_work']=='DE-W030'
assert not programme['baseline_owner_accepted'] and not programme['implementation_owner_accepted']
assert programme['in_progress_slice']['source_revision']==source
summary=read(prefix+'/validation-summary.json')
assert not summary['full_programme_complete'] and not summary['owner_accepted'] and not summary['unit_complete']
sys.path.insert(0,str(root/'spec/tools'))
from specctl import Bundle
Bundle(root/'spec').validate('urn:disked:schema:handoff:1',handoff)
print(json.dumps(dict(status='pass',mode=mode,evidence_files=len(inventory['evidence_files']),
    native_artifacts=len(inventory['artifacts']),handoff_hashes=len(handoff['artifacts']),source_inputs=len(inputs),
    owner_accepted=False,full_programme_complete=False,remote_writes=False)))
