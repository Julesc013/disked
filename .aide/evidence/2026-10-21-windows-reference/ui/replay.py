"""Verify actual UI evidence and the frozen combined12-tuple campaign."""
import hashlib
import importlib.util
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import struct
import subprocess
import sys
import tarfile
import uuid

ROOT=Path(__file__).resolve().parents[4]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/differential'))
from projections import strict_json
from windows_ui_observations import complete_observations, project_ui

def check(value,reason):
    if not value:raise ValueError(reason)
def sha(body):return hashlib.sha256(body).hexdigest()
def packed(path,bound=8388608):
    compressed=path.read_bytes();check(len(compressed)<=1048576,'compressed_bound')
    decoder=lzma.LZMADecompressor(memlimit=8*1024*1024);raw=decoder.decompress(compressed,max_length=bound+1)
    check(len(raw)<=bound and decoder.eof and not decoder.unused_data,'decompression_bound');return raw
def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path);module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def main():
    check(bool(os.environ.get('DISKED_WORK_ROOT')),'managed_runner')
    # Re-run the unchanged API verifier, including its raw SDK bytes and native
    # fixture expectations. Its historical eight-tuple result stays incomplete.
    api_directory=HERE.parent/'api';before=(api_directory/'replay.json').read_bytes()
    load('prior_windows_api_replay',HERE.parent/'replay.py').main()
    check((api_directory/'replay.json').read_bytes()==before,'historical_api_receipt_unchanged')
    api_outer=strict_json(packed(api_directory/'receipt.json.xz'));api=api_outer['guest']['proof']['windows_reference']
    directory=HERE/'capture';outer=strict_json(packed(directory/'receipt.json.xz'));proof=outer['guest']['proof'];report=proof['windows_ui']
    launch=strict_json(packed(directory/'launch.json.xz'));revision=launch['source_revision']
    check(launch['status']=='pass' and outer['status']=='pass' and outer['host_exit_code']==0 and proof['status']=='pass','execution')
    check(report['status']=='captured_pending_semantic_review' and not report['campaign_complete'] and not proof['campaign_complete'],'collection_scope')
    check(all(proof[key] for key in ('all_owned_processes_retired','all_owned_profiles_retired','all_owned_reference_jobs_retired','all_owned_media_retired','crypto_device_retired','object_namespace_retired')),'retirement')
    check(proof['window_station']['retired'] and report['reference_role']['retired'],'exception_retirement')
    check(report['windows_registry']==api['environment']['windows_registry'],'same_windows_profile')
    check('sha256:'+proof['compiler_sha256'] in api['toolchain'].values() and 'sha256:'+proof['linker_sha256'] in api['toolchain'].values(),'same_toolchain')
    role=report['role_observation']['identity'];actor=outer['guest']['setup']['actor_sid']
    check(role['sid']==actor==proof['native_identity']['sid'] and role['administrator'] and not role['restricted'] and not role['appcontainer'],'role_identity')
    check(proof['native_identity']['restricted'] and not proof['native_identity']['elevated'],'ordinary_role_separate')
    check(len(proof['port_observations'])==10 and len(report['reference_role']['launches'])==9 and len(report['retirements'])==9,'call_and_job_sets')
    check(all(row['active_processes']==0 for row in report['retirements']),'reference_quiescence')
    limits=report['reference_job_limits'];check(len(limits)==9 and limits[0]['commit_bytes']==268435456 and limits[0]['processes']==8,'role_limits')
    check(all(row['paired'] and row['commit_bytes']==134217728 and row['processes']==4 for row in limits[1:]),'aggregate_limits')
    for row in report['reference_role']['launches']:
        state=row['job_after_assignment'];token=row['token']
        check(state['in_owned_job'] and state['flags']=='0x2208' and state['ui_limits']==0 and row['job_assigned_before_resume'],'job_assignment')
        check(token['sid']==actor and token['administrator'] and not token['restricted'] and row['actual_session']==3,'child_role')
    aliases={'windows-reference-ui.py':HERE/'control.py','windows-reference-role.py':HERE/'reference.py',
        'ui-profile.py':HERE/'profile.py','ui-profile-probe.py':HERE/'profile-probe.py','windows-reference-media.py':HERE.parent/'media.py',
        'native-port.py':HERE.parent.parent/'2026-10-20-differential-evidence/native-port.py',
        'native-port.cpp':HERE.parent.parent/'2026-10-20-differential-evidence/native-port.cpp',
        'windows_executor.py':ROOT/'tests/differential/windows_executor.py',
        **{name:HERE.parent.parent/'2026-10-18-ordinary-worker'/name for name in ('interactive-run.ps1','window-station.py','object-namespace.py','ordinary-worker.py','guest-proof.py')}}
    aliases.update({path:ROOT/path for path in report_source_files()})
    for alias,path in aliases.items():
        original=subprocess.check_output(['git','show',revision+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)
        check(sha(original)==proof['source_inputs'][alias]==outer['generated_sha256'][alias],'source_binding:'+alias)
    archive=directory/'retained.tar.xz';check(sha(archive.read_bytes())==proof['archive_sha256'],'archive_hash')
    files={}
    with tarfile.open(fileobj=io.BytesIO(packed(archive,12582912)),mode='r:') as stream:
        for member in stream:
            path=PurePosixPath(member.name)
            check(len(files)<128 and member.isfile() and member.size<=2097152 and not path.is_absolute() and '..' not in path.parts and '\\' not in member.name and member.name not in files,'archive_entry')
            files[member.name]=stream.extractfile(member).read(2097153);check(len(files[member.name])==member.size,'entry_length')
    inventory=report['archive']['entries'];check(set(files)=={row['path'] for row in inventory} and len(files)==len(inventory),'archive_set')
    check(sum(map(len,files.values()))<=8388608,'original_bound')
    for row in inventory:check(len(files[row['path']])==row['bytes'] and sha(files[row['path']])==row['sha256'],'entry_hash')
    check(strict_json(files['results.json'])=={k:v for k,v in report.items() if k!='archive'},'report_binding')
    facts=strict_json((HERE.parent/'fixtures-before-native.json').read_bytes());recipes=load('combined_windows_recipes',ROOT/facts['generator'])
    check('sha256:'+sha((ROOT/facts['generator']).read_bytes())==facts['generator_sha256'],'recipe_source')
    actual=list(api['actual_observation_tuples']);findings=[];ids=[]
    check(len(report['cases'])==4,'case_set')
    for row,fact,api_row in zip(report['cases'],facts['cases'],api['cases']):
        check(row['fixture']==fact==api_row['fixture'] and row['participant']=='disk-management' and row['kind']=='ui-layout','canonical_case')
        name=fact['name'];media=row['media'];binding=row['binding'];view=row['ui'];execution=view['observer_execution'];mmc=view['mmc_execution']
        check(media['removed'] and media['payload_unchanged'] and media['attachment_flags']==3 and not media['permanent_lifetime'] and not media['device_acl_changed'],'media_policy')
        check(media['detach_code']==0 and media['post_detach_path_error']!=0 and media['before']['file_id']==media['after']['file_id'],'media_identity')
        check(media['identity_after_attach']==media['identity_before_detach'] and media['attachment_uuid']==binding['attachment_uuid'],'held_media')
        check(binding['nonce']==media['nonce'] and binding['physical_path']==media['physical_path'],'locator_binding')
        check(binding['display_locator']=='Disk '+re_number(media['physical_path']),'current_locator')
        ids.append(media['attachment_uuid']);payload=recipes.generate(name)
        for point in ('before','after'):
            snapshot=media[point];footer=bytes.fromhex(snapshot['footer_hex']);check(len(footer)==512 and footer[:8]==b'conectix','footer')
            mutable=bytearray(footer);checksum=struct.unpack_from('>I',mutable,64)[0];mutable[64:68]=bytes(4)
            check(checksum==((~sum(mutable))&0xffffffff) and uuid.UUID(bytes_le=footer[68:84])==uuid.UUID(media['attachment_uuid']),'footer_identity')
            check(snapshot['payload_sha256']==fact['sha256'] and 'sha256:'+sha(payload+footer)==snapshot['file_sha256'],'media_bytes')
        check(media['before']['file_sha256']==media['after']['file_sha256'],'unchanged_container')
        check(execution['outcome']=='exited' and execution['exit_code']==0 and files[execution['stderr']['path']]==b'','observer_completion')
        raw=strict_json(files[execution['stdout']['path']])
        projection=project_ui(raw,dict(binding,actor_sid=actor,desktop=role['desktop'],observer_pid=execution['pid'],mmc_pid=mmc['pid']))
        actual.append(dict(name=name,participant='disk-management',kind='ui-layout'))
        findings.append(dict(name=name,fixture_sha256=fact['sha256'],windows_api_projection=api_row['windows_api']['projection'],
            matching_native_candidates=api_row['windows_api']['matching_native_candidates'],ui_projection=projection,
            extent_comparison='not_comparable: UI capacities are display text;no exact LBA/byte projection',
            native_conflict_retained=name=='gpt-conflicting'))
    check(len(set(ids))==4,'independent_ui_copies')
    check(report['actual_observation_tuples']==[v for v in actual if v['participant']=='disk-management'],'ui_tuple_set')
    complete_observations(facts['required_observations'],actual)
    cleanup=strict_json((directory/'cleanup-live.json').read_bytes())
    check(cleanup['actor_sid']==actor and not cleanup['owned_processes'] and cleanup['inaccessible_owner_queries']==0,'fresh_process_cleanup')
    check(all(cleanup[key] for key in ('qualification_absent','scratch_absent','actor_absent','actor_directory_absent','actor_hive_absent','actor_profile_key_absent','actor_backup_profile_key_absent')),'fresh_cleanup')
    result=dict(status='pass',campaign_complete=True,observations=12,expected_observations=12,single_run_all_participants=False,
        native_api_source_revision=api['source_revision'],ui_source_revision=revision,windows_registry=report['windows_registry'],
        findings=findings,ui_archive_bytes=archive.stat().st_size,ui_archive_entries=len(files),ui_original_bytes=sum(map(len,files.values())),
        all_owned_media_retired=True,all_owned_processes_retired=True,profile_and_membership_retired=True,
        service_before=report['service_before'],service_after=report['service_after'],
        storage_provider_admitted=False,owner_accepted=False,release_qualified=False,full_0_1_0_complete=False)
    (directory/'combined-replay.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(result))

def report_source_files():return ('source/runtime/command/json.cpp','source/runtime/command/json.h','tests/differential/windows_ui_probe.cpp','tests/corpus/windows_partitions.py')
def re_number(path):
    import re
    match=re.search(r'([0-9]+)$',path);check(match is not None,'physical_mapping');return str(int(match[1]))

if __name__=='__main__':main()
