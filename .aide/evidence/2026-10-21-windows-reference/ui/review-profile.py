"""Replay the retained profile receipt; never launch a guest or infer UI success."""
import hashlib
import json
import lzma
from pathlib import Path, PureWindowsPath
import re
import subprocess

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
REVISION='10f4173f3c99cb6ba220181ac7cc9d9b583f1379'

def packed(name):
    data=(HERE/'profile'/name).read_bytes()
    assert len(data)<=65536
    raw=lzma.decompress(data)
    assert len(raw)<=1048576
    return json.loads(raw)

receipt=packed('receipt.json.xz');proof=receipt['guest']['proof'];profile=proof['ui_profile']
setup=receipt['guest']['setup'];launch=packed('launch.json.xz')
revision=subprocess.check_output(['git','rev-parse',REVISION],cwd=ROOT,text=True).strip()
assert launch['source_revision']==revision and launch['status']=='pass'
assert receipt['host_exit_code']==0 and proof['status']==setup['status']==profile['status']=='pass'
assert setup['size_mib']==32 and all(setup[k] for k in ('image_removed','actor_removed','actor_profile_absent'))
assert proof['primitive_proof']['status']=='pass' and proof['primitive_proof']['all_owned_processes_retired']
assert proof['all_owned_processes_retired'] and proof['all_owned_profiles_retired'] and proof['crypto_device_retired']
assert profile['actor_sid']==setup['actor_sid']==proof['native_identity']['sid']
assert proof['native_identity']['restricted'] and not proof['native_identity']['elevated']
assert not proof['native_identity']['appcontainer']
assert len(proof['controls'])==8 and len(proof['port_observations'])==9
assert all(v['terminal'] and v['temporary_files_removed'] and v['job_retirement']['active_processes']==0 for v in proof['port_observations'])
assert all(profile[k] for k in ('loaded','unloaded','profile_removed','key_removed','owned_hive_write_verified'))
base=PureWindowsPath(profile['path']);observed=json.loads(profile['stdout'])
assert base.drive=='R:' and PureWindowsPath(profile['resolved_profile'])==base
assert observed==profile['probe'] and observed['expected_actor_sid']==profile['actor_sid']
assert all(PureWindowsPath(v).is_relative_to(base) for v in observed['known_folders'].values())
assert PureWindowsPath(observed['temp']).is_relative_to(base.parent)
assert re.fullmatch('[a-f0-9]{32}',observed['nonce'])
last=proof['port_observations'][-1]
assert last['exit_code']==0 and last['argv'][-1]==observed['nonce'] and last['argv'][-2]==profile['actor_sid']
assert not profile['stderr'] and hashlib.sha256(profile['stdout'].encode()).hexdigest()==last['stream_sha256']['stdout']
acl=profile['hive_initialization'];assert not acl['shared_hives_changed'] and not acl['owner_or_sacl_changed']
aces=re.findall(r'\(([^()]*)\)',acl['after'])
assert sorted(aces)==sorted('A;CI;KA;;;'+sid for sid in ('SY','BA',profile['actor_sid']))
aliases={'ui-profile.py':HERE/'profile.py','ui-profile-probe.py':HERE/'profile-probe.py',
         'ordinary-worker.py':HERE.parent.parent/'2026-10-18-ordinary-worker/ordinary-worker.py',
         'guest-proof.py':HERE.parent.parent/'2026-10-18-ordinary-worker/guest-proof.py',
         'windows_executor.py':ROOT/'tests/differential/windows_executor.py'}
inputs={};current_matches={}
for alias,path in aliases.items():
    original=subprocess.check_output(['git','show',revision+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)
    actual=hashlib.sha256(original).hexdigest()
    assert actual==proof['source_inputs'][alias]==receipt['generated_sha256'][alias]
    inputs[path.relative_to(ROOT).as_posix()]='sha256:'+actual
    current_matches[path.relative_to(ROOT).as_posix()]=hashlib.sha256(path.read_bytes()).hexdigest()==actual
before=json.loads((HERE/'profile-before.json').read_bytes());after=json.loads((HERE/'profile/cleanup-live.json').read_bytes())
assert before['shared_accounts']==after['shared_accounts']
assert after['identity']==r'BLACKGLASS-HYPE\Agents' and after['owned_processes']==0
assert all(after[k] for k in ('qualification_absent','scratch_absent','actor_absent','actor_directory_absent',
    'actor_hive_absent','actor_profile_key_absent','actor_backup_profile_key_absent'))
assert receipt['host_backing_start_bytes']==receipt['host_backing_end_bytes']
assert proof['ui_observations']==0 and not proof['campaign_complete'] and not profile['mmc_started'] and not profile['ui_reference_qualified']
result=dict(status='pass',scope='Historical10f4173f receipt replay; applicability to current files is separate',source_revision=revision,source_inputs=inputs,current_input_matches=current_matches,port_calls=9,
    profile_copied_bytes=profile['default_copy']['bytes'],profile_removed=True,owned_cleanup_verified=True,
    shared_account_identity_and_enabled_state_unchanged=True,host_backing_logical_bytes=receipt['host_backing_end_bytes'],
    host_backing_allocated_growth='not_measured',ui_observations=0,campaign_complete=False,
    limitation='probe.desktop is a historical misnamed USERPROFILE value, not a desktop observation. Private desktop is the launcher startup assignment; MMC/interactive station/admin reference remain unqualified.')
(HERE/'profile/historical-replay.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(result))
