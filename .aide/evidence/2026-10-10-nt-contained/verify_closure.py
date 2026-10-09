"""Check current contained-reader evidence bytes, source and projection."""
import hashlib,json,subprocess,sys
from pathlib import Path
root=Path(__file__).resolve().parents[3];mode=sys.argv[1] if len(sys.argv)>1 else 'files';assert mode in ('files','staged','head')
prefix='.aide/evidence/2026-10-10-nt-contained';source='d3798a7d867f9cce7369ca50cd55659e0280eddb';cache={}
def sha(b):return 'sha256:'+hashlib.sha256(b).hexdigest()
def data(name):
    if mode=='files' or name.startswith('.aide-local/'):return (root/name).read_bytes()
    if name not in cache:cache[name]=subprocess.check_output(['git','show',(':' if mode=='staged' else 'HEAD:')+name],cwd=root)
    return cache[name]
def read(name):return json.loads(data(name))
inventory=read(prefix+'/inventory.json');handoff=read('.aide/handoffs/DE-W030-nt-contained-2026-10-10.json')
if mode!='files':
    names=sorted({x['path'] for x in inventory['evidence_files']+inventory['artifacts']+handoff['artifacts'] if not x['path'].startswith('.aide-local/')});assert all('\n' not in n and '\r' not in n for n in names)
    refs=[(':' if mode=='staged' else 'HEAD:')+n for n in names];batch=subprocess.run(['git','cat-file','--batch'],cwd=root,input=('\n'.join(refs)+'\n').encode(),capture_output=True,check=True).stdout;at=0
    for n in names:
        end=batch.index(b'\n',at);header=batch[at:end].split();assert len(header)==3 and header[1]==b'blob',n;length=int(header[2]);at=end+1;cache[n]=batch[at:at+length];at+=length;assert batch[at:at+1]==b'\n';at+=1
    assert at==len(batch)
assert inventory['source_revision']==source and handoff['spec_manifest_digest']==sha(data('spec/manifest.json'))
assert handoff['status']=='partial' and not handoff['performed_remote_writes']
for row in inventory['evidence_files']+inventory['artifacts']:
    b=data(row['path']);assert len(b)==row['bytes'] and sha(b)==row['sha256'],row['path']
for row in handoff['artifacts']:assert sha(data(row['path']))==row['sha256'],row['path']
inputs=read(prefix+'/reproduction-d3798a7/source-inputs.json');assert len(inputs)==24
for n,value in inputs.items():assert sha(subprocess.check_output(['git','show',source+':'+n],cwd=root))==value and sha(data(n))==value,n
result=read(prefix+'/reproduction-d3798a7/results.json');assert result['status']=='pass' and result['source_revision']==source and result['source_inputs']==24
assert result['host']['identity']=='BLACKGLASS-WIN1\\Jules' and not result['host']['elevated']
expected=[]
for arch,pointer in [('x64',8),('Win32',4)]:
    expected += [dict(kind='adapter',architecture=arch,assertions=258,executions=49,child_launches=0,pointer_bytes=pointer),dict(kind='worker',architecture=arch,assertions=116,executions=24,child_launches=18,pointer_bytes=pointer)]
assert result['campaigns']==expected and result['tooling_tests']==dict(run=215,passed=213,skipped=2) and result['structural_checks']==1045
for key in ('live_namespace_qualified','physical_access','product_native_rebuilt','XP_qualified','provider_admitted','durable_reconnect','unit_complete','owner_accepted','remote_writes'):assert not result[key],key
summary=read(prefix+'/validation-summary.json');assert not summary['full_programme_complete'] and not summary['unit_complete'] and not summary['owner_accepted']
programme=read('.aide/programmes/disked-0.1.0.json');assert programme['status']=='active' and programme['current_work']=='DE-W030' and programme['in_progress_slice']['source_revision']==source
assert not programme['baseline_owner_accepted'] and not programme['implementation_owner_accepted']
sys.path.insert(0,str(root/'spec/tools'));from specctl import Bundle
Bundle(root/'spec').validate('urn:disked:schema:handoff:1',handoff)
print(json.dumps(dict(status='pass',mode=mode,evidence_files=len(inventory['evidence_files']),artifacts=len(inventory['artifacts']),handoff_hashes=len(handoff['artifacts']),source_inputs=len(inputs),unit_complete=False,owner_accepted=False,full_programme_complete=False,remote_writes=False)))
