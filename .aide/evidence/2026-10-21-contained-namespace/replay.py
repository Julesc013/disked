"""Verify complete identified native cases and retained injected regression evidence."""
import hashlib
import io
import json
import lzma
import os
from pathlib import Path,PurePosixPath
import subprocess
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
sys.path[:0]=[str(ROOT/'tests/windows'),str(ROOT/'tests/differential')]
from native_namespace_observations import validate
from projections import strict_json


def check(value,reason):
    if not value:raise ValueError(reason)


def sha(value):return hashlib.sha256(value).hexdigest()


def unpack(path):
    body=path.read_bytes();check(len(body)<=1048576,'compressed_bound')
    decoder=lzma.LZMADecompressor(memlimit=8388608);raw=decoder.decompress(body,max_length=8388609)
    check(len(raw)<=8388608 and decoder.eof and not decoder.unused_data,'decompression_bound');return raw


def main():
    check(bool(os.environ.get('DISKED_WORK_ROOT')),'managed_runner');directory=HERE/'capture'
    outer=strict_json(unpack(directory/'receipt.json.xz'));launch=strict_json(unpack(directory/'launch.json.xz'))
    guest=outer['guest'];proof=guest['proof'];report=proof['contained_namespace'];revision=report['source_revision']
    check(outer['status']==launch['status']==proof['status']=='pass' and outer['host_exit_code']==0,'execution')
    check(revision==outer['sources']['base_revision']==launch['source_revision'],'source_revision')
    check(guest['identity']=='BLACKGLASS-HYPE\\Agents' and guest['setup']['size_mib']==32,'guest')
    check(report['status']=='native_containment_and_publication_pass' and report['port_calls']==60,'result')
    check(len(proof['controls'])==8 and len(proof['port_observations'])==60 and proof['primitive_proof']['status']=='pass','original_controls')
    check(proof['all_owned_processes_retired'] and proof['crypto_device_retired'],'retirement')
    for row in proof['port_observations']:check(row['terminal'] and row['temporary_files_removed'] and row['job_retirement']['active_processes']==0,'port_retirement')
    for row in proof['job_limits']:check(row['flags']=='0x2208' and row['job_commit_bytes']==268435456 and row['process_limit']==8,'job_limits')
    aliases={'contained-namespace.py':HERE/'control.py','native-port.py':HERE.parent/'2026-10-20-differential-evidence/native-port.py',
        'native-port.cpp':HERE.parent/'2026-10-20-differential-evidence/native-port.cpp','windows_executor.py':ROOT/'tests/differential/windows_executor.py'}
    aliases.update({name:HERE.parent/'2026-10-18-ordinary-worker'/name for name in ('ordinary-worker.py','target.py','guest-proof.py','crypto-device.py')})
    aliases.update({path:ROOT/path for path in report['source_inputs']})
    for alias,path in aliases.items():
        body=subprocess.check_output(['git','show',revision+':'+path.relative_to(ROOT).as_posix()],cwd=ROOT)
        check(sha(body)==proof['source_inputs'][alias]==outer['generated_sha256'][alias],'source:'+alias)
    contract=strict_json(subprocess.check_output(['git','show',revision+':'+(HERE/'expected.json').relative_to(ROOT).as_posix()],cwd=ROOT))
    archive=directory/'retained.tar.xz';check(sha(archive.read_bytes())==proof['archive_sha256']==report['archive']['sha256'],'archive_hash')
    files={}
    with tarfile.open(fileobj=io.BytesIO(unpack(archive)),mode='r:') as stream:
        for member in stream:
            path=PurePosixPath(member.name)
            check(len(files)<128 and member.isfile() and member.size<=2097152 and not path.is_absolute() and '..' not in path.parts and '\\' not in member.name and member.name not in files,'entry')
            files[member.name]=stream.extractfile(member).read(2097153);check(len(files[member.name])==member.size,'entry_length')
    inventory=report['archive']['entries'];check(set(files)=={v['path'] for v in inventory} and len(files)==len(inventory),'entry_set')
    for row in inventory:check(len(files[row['path']])==row['bytes'] and sha(files[row['path']])==row['sha256'],'entry_hash')
    check(sum(map(len,files.values()))<=8388608 and strict_json(files['results.json'])=={k:v for k,v in report.items() if k!='archive'},'report_binding')
    check(report['witness_before']==report['witness_after']==report['known_volume']==proof['primitive_proof']['capped_volume'],'target_witness')
    check([a['name'] for a in report['architectures']]==[a['name'] for a in contract['arches']],'architecture_set')
    summaries=[]
    for arch,expected in zip(report['architectures'],contract['arches']):
        check(arch['pointer_bytes']==expected['pointer_bytes'] and len(arch['cases'])==len(contract['cases']),'case_set')
        code=arch['executable']['sha256'];check(arch['executables']['native_namespace_probe.exe']==arch['executable'],'code_unchanged')
        all_calls=arch['compilation']+arch['cases']+arch['guards']+arch['regressions']+[arch['imports']]
        for call in all_calls:
            port=proof['port_observations'][call['call_index']-1]
            check(call['argv']==port['argv'] and call['process_id']==port['process_id'] and call['exit_code']==port['exit_code'] and call['outcome']==port['outcome'],'execution_binding')
            for stream in ('stdout','stderr'):
                item=call[stream];body=files[item['path']]
                check(len(body)==item['bytes']==port['returned_bytes'][stream] and sha(body)==item['sha256']==port['stream_sha256'][stream],'stream_binding')
        for case,expected_case in zip(arch['cases'],contract['cases']):
            check(case['label']==arch['name']+'-'+expected_case and case['argv'][-1]==expected_case and case['exit_code']==0 and not files[case['stderr']['path']],'case_identity')
            validate(strict_json(files[case['stdout']['path']]),expected_case,expected['pointer_bytes'],code,report['known_volume'],report['known_mount'])
        check(len(arch['regressions'])==3 and len(arch['guards'])==2,'additional_sets')
        for regression in arch['regressions']:
            item=regression['regression_evidence'];body=files[item['path']];check(sha(body)==item['sha256'] and len(body)==item['bytes'],'regression_bundle')
            bundle=strict_json(body);entries={row['path']:row for row in bundle['all_entry_hashes']}
            for name,text in bundle['retained_utf8'].items():check(len(text.encode())==entries[name]['bytes'] and sha(text.encode())==entries[name]['sha256'],'legacy_retained_stream')
            result=strict_json(bundle['retained_utf8']['results.json']);check(result['status']=='pass' and result['pointer_bytes']==expected['pointer_bytes'] and result['assertions']==len(result['checks']) and all(c['passed'] is True for c in result['checks']),'legacy_checks')
            if regression['label'].endswith('-worker'):
                for prefix in ('native_table','native_error'):
                    value=strict_json(bundle['retained_utf8'][prefix+'-binding-refused.stdout'])['observations'][-1]
                    check(value['result'] is None and not value['admitted'] and value['worker']['exit_code']=='3','legacy_native_guard')
        summaries.append(dict(name=arch['name'],native_cases=len(arch['cases']),legacy=[r['summary'] for r in arch['regressions']],executables=arch['executables']))
    check(all(guest['setup'][k] for k in ('image_removed','actor_removed','actor_profile_absent')),'owned_cleanup')
    cleanup=strict_json((directory/'cleanup-live.json').read_bytes());check(cleanup['actor_sid']==guest['setup']['actor_sid'] and not cleanup['owned_processes'] and cleanup['inaccessible_owner_queries']==0,'fresh_process_cleanup')
    check(all(cleanup[k] for k in ('qualification_absent','scratch_absent','actor_absent','actor_directory_absent','actor_hive_absent','actor_profile_key_absent')),'fresh_cleanup')
    result=dict(status='pass',source_revision=revision,architectures=summaries,new_native_cases=30,legacy_controllers=206,execution_port_calls=60,
        archive_bytes=archive.stat().st_size,archive_entries=len(files),original_bytes=sum(map(len,files.values())),new_native_streams_complete=True,all_legacy_success_payloads_retained=False,
        owned_cleanup_verified=True,full_product_qualified=False,provider_admitted=False,owner_accepted=False,release_qualified=False,full_0_1_0_complete=False)
    (directory/'replay.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n');print(json.dumps(result))


if __name__=='__main__':main()
