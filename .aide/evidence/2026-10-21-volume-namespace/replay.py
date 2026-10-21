"""Bounded replay of the real ordinary-worker guest namespace evidence."""
import hashlib
import io
import json
import lzma
import os
from pathlib import Path,PurePosixPath
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/windows'));sys.path.insert(0,str(ROOT/'tests/differential'))
from native_volume_observations import MODES,validate
from projections import strict_json


def check(value,reason):
    if not value:raise ValueError(reason)


def sha(value):return hashlib.sha256(value).hexdigest()


def unpack(path,bound=8388608):
    body=path.read_bytes();check(len(body)<=1048576,'compressed_bound')
    decoder=lzma.LZMADecompressor(memlimit=8388608);raw=decoder.decompress(body,max_length=bound+1)
    check(len(raw)<=bound and decoder.eof and not decoder.unused_data,'decompression_bound');return raw


def main():
    check(bool(os.environ.get('DISKED_WORK_ROOT')),'managed_runner')
    directory=HERE/'capture';outer=strict_json(unpack(directory/'receipt.json.xz'))
    launch=strict_json(unpack(directory/'launch.json.xz'));g=outer['guest'];proof=g['proof'];report=proof['volume_namespace']
    revision=report['source_revision'];check(revision==launch['source_revision']==outer['sources']['base_revision'],'revision')
    check(outer['status']==launch['status']==proof['status']=='pass' and outer['host_exit_code']==0,'execution')
    check(g['identity']=='BLACKGLASS-HYPE\\Agents' and g['setup']['size_mib']==32,'guest')
    check(all(g['setup'][k] for k in ('image_removed','actor_removed','actor_profile_absent')),'setup_cleanup')
    check(proof['primitive_proof']['status']=='pass' and proof['all_owned_processes_retired'] and proof['crypto_device_retired'],'original_controls')
    check(len(proof['controls'])==8 and len(proof['port_observations'])==16,'port_set')
    for row in proof['port_observations']:
        check(row['terminal'] and row['temporary_files_removed'] and row['job_retirement']['active_processes']==0,'port_retirement')
    for row in proof['job_limits']:
        check(row['job_commit_bytes']==268435456 and row['process_limit']==8 and row['flags']=='0x2208','job_limits')
    aliases={'volume-namespace.py':HERE/'control.py','native-port.py':HERE.parent/'2026-10-20-differential-evidence/native-port.py',
        'native-port.cpp':HERE.parent/'2026-10-20-differential-evidence/native-port.cpp','windows_executor.py':ROOT/'tests/differential/windows_executor.py'}
    aliases.update({name:HERE.parent/'2026-10-18-ordinary-worker'/name for name in ('ordinary-worker.py','target.py','guest-proof.py','crypto-device.py')})
    aliases.update({path:ROOT/path for path in report['source_inputs']})
    for alias,path in aliases.items():
        body=subprocess.check_output(['git','show',revision+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)
        check(sha(body)==proof['source_inputs'][alias]==outer['generated_sha256'][alias],'source:'+alias)
    contract=strict_json(subprocess.check_output(['git','show',revision+':'+(HERE/'expected.json').relative_to(ROOT).as_posix()],cwd=ROOT))
    check([v['mode'] for v in contract['cases']]==list(MODES),'expected_cases')
    archive=directory/'retained.tar.xz';check(sha(archive.read_bytes())==proof['archive_sha256']==report['archive']['sha256'],'archive_hash')
    files={}
    with tarfile.open(fileobj=io.BytesIO(unpack(archive)),mode='r:') as stream:
        for member in stream:
            path=PurePosixPath(member.name)
            check(len(files)<32 and member.isfile() and member.size<=524288 and not path.is_absolute() and '..' not in path.parts and '\\' not in member.name and member.name not in files,'entry')
            files[member.name]=stream.extractfile(member).read(524289);check(len(files[member.name])==member.size,'entry_length')
    inventory=report['archive']['entries'];check(len(files)==len(inventory) and set(files)=={v['path'] for v in inventory},'entry_set')
    check(sum(map(len,files.values()))<=4194304,'original_bound')
    for row in inventory:check(len(files[row['path']])==row['bytes'] and sha(files[row['path']])==row['sha256'],'entry_hash')
    check(strict_json(files['results.json'])=={k:v for k,v in report.items() if k!='archive'},'raw_report')
    calls=[report['compile'],*report['cases'],report['imports']]
    check([row['call_index'] for row in calls]==list(range(9,17)),'call_accounting')
    for row in calls:
        port=proof['port_observations'][row['call_index']-1]
        check(row['argv']==port['argv'] and row['process_id']==port['process_id'] and row['exit_code']==port['exit_code'] and row['outcome']==port['outcome'],'execution_binding')
        for name in ('stdout','stderr'):
            item=row[name];check(len(files[item['path']])==item['bytes']==port['returned_bytes'][name] and sha(files[item['path']])==item['sha256']==port['stream_sha256'][name],'output_binding')
    check(report['witness_before']==report['witness_after']==dict(volume=report['known_volume'],mount=report['known_mount']),'target_witness')
    check(report['known_volume']==proof['primitive_proof']['capped_volume'],'original_cap_identity')
    cases=[];check(len(report['cases'])==len(MODES),'case_count')
    for row,expected in zip(report['cases'],contract['cases']):
        mode=expected['mode'];check(row['label']==mode[2:] and row['argv'][-1]==mode,'case_identity')
        check(row['outcome']=='exited' and row['exit_code']==expected['exit_code'] and not files[row['stderr']['path']],'case_execution')
        value=strict_json(files[row['stdout']['path']])
        projection=validate(value,mode,g['setup']['actor_sid'],row['process_id'],report['known_volume'],report['known_mount'])
        check(projection==row['review'],'case_review');cases.append(dict(mode=mode,result=projection))
    imports=files[report['imports']['stdout']['path']].decode('ascii');check('8664 machine (x64)' in imports,'machine')
    dlls=[line.strip() for line in imports.splitlines() if line.strip().lower().endswith('.dll')]
    os_version=next(line.split()[0] for line in imports.splitlines() if 'operating system version' in line)
    subsystem_version=next(line.split()[0] for line in imports.splitlines() if 'subsystem version' in line)
    cleanup=strict_json((directory/'cleanup-live.json').read_bytes())
    check(cleanup['actor_sid']==g['setup']['actor_sid'] and not cleanup['owned_processes'] and cleanup['inaccessible_owner_queries']==0,'fresh_process_cleanup')
    check(all(cleanup[k] for k in ('qualification_absent','scratch_absent','actor_absent','actor_directory_absent','actor_hive_absent','actor_profile_key_absent')),'fresh_owned_cleanup')
    result=dict(status='pass',source_revision=revision,scope='Selected real Windows10 guest volume namespace;not a public provider or full DE-W030',
        windows_registry=report['windows_registry'],cases=cases,port_calls=16,native_observer_cases=6,
        archive_bytes=archive.stat().st_size,archive_entries=len(files),original_bytes=sum(map(len,files.values())),
        executable=report['executable'],import_dlls=dlls,pe_operating_system_version=os_version,pe_subsystem_version=subsystem_version,
        owned_cleanup_verified=True,provider_admitted=False,physical_admitted=False,xp_qualified=False,owner_accepted=False,release_qualified=False,full_0_1_0_complete=False)
    (directory/'replay.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result))


if __name__=='__main__':main()
