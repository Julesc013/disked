"""Verify retained carrier evidence bytes in files, Git index or HEAD."""
import hashlib,json,subprocess,sys
from pathlib import Path

root=Path(__file__).resolve().parents[3]
mode=sys.argv[1] if len(sys.argv)>1 else 'files'
assert mode in ('files','staged','head')
prefix='.aide/evidence/2026-10-10-carrier-fixtures'
source='d4102abd5a1ea619b5123210bd8b801cb8657ea2'
def data(name):
    if mode=='files' or name.startswith('.aide-local/'):
        return (root/name).read_bytes()
    return subprocess.check_output(['git','show',(':' if mode=='staged' else 'HEAD:')+name],cwd=root)
def sha(value):return 'sha256:'+hashlib.sha256(value).hexdigest()
def read(name):return json.loads(data(name))
inventory=read(prefix+'/inventory.json')
handoff=read('.aide/handoffs/DE-W062-carrier-fixtures-2026-10-10.json')
assert inventory['source_revision']==source
assert handoff['spec_manifest_digest']==sha(data('spec/manifest.json'))
assert not handoff['performed_remote_writes'] and handoff['status']=='partial'
for row in inventory['evidence_files']+inventory['artifacts']:
    value=data(row['path'])
    assert len(value)==row['bytes'] and sha(value)==row['sha256'],row['path']
for row in handoff['artifacts']:
    assert sha(data(row['path']))==row['sha256'],row['path']
inputs=read(prefix+'/reproduction-d4102ab/source-inputs.json')
for name,value in inputs.items():
    blob=subprocess.check_output(['git','show',source+':'+name],cwd=root)
    assert sha(blob)==value and sha(data(name))==value,name
result=read(prefix+'/reproduction-d4102ab/results.json')
assert result['passed'] and result['source_revision']==source
assert result['base_native_executions']==33 and result['base_assertions']==223
assert result['host_native_executions']==33 and result['host_assertions']==223
assert result['composition_tests']==26 and result['setup_tests']==30
assert result['tooling_tests']==dict(run=215,passed=213,skipped=2)
assert all(result[key] for key in ('payload_equality','deterministic_S','occupied_data_retained','damaged_D_inspection_route'))
assert not any(result[key] for key in ('product_native_rebuilt','repair_or_recovery_success','live_interlock_qualified',
    'installed_sdk_qualified','native_setup_carrier_qualified','owner_accepted','unit_complete','remote_writes'))
programme=read('.aide/programmes/disked-0.1.0.json')
assert programme['status']=='active' and programme['current_work']=='DE-W062'
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
