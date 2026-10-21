"""Replay native/Windows raw observations without executing retained commands."""
import hashlib
import importlib.util
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath
import struct
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/differential'))
from projections import field, native_projection, strict_json
from windows_observations import request, native_expectations, api_projection, matching_candidates

def check(value,reason):
    if not value:raise ValueError(reason)
def sha(body):return 'sha256:'+hashlib.sha256(body).hexdigest()
def decode(path,bound):
    body=path.read_bytes();check(len(body)<=1048576,'compressed_bound')
    reader=lzma.LZMADecompressor(memlimit=8*1024*1024)
    result=reader.decompress(body,max_length=bound+1)
    check(len(result)<=bound and reader.eof and not reader.unused_data,'decompression_bound');return result

def main():
    check(bool(os.environ.get('DISKED_WORK_ROOT')),'managed_runner_required')
    directory=HERE/'api';outer=strict_json(decode(directory/'receipt.json.xz',8388608));proof=outer['guest']['proof']
    report=proof['windows_reference'];expected=strict_json((HERE/'api-expected.json').read_bytes())
    facts=strict_json((HERE/'fixtures-before-native.json').read_bytes())
    check(outer['status']=='pass' and outer['host_exit_code']==0 and proof['status']=='pass','run_success')
    check(report['status']=='available_native_api_slice_pass' and report['evidence_status']=='incomplete' and
          report['campaign_complete'] is False and proof['campaign_complete'] is False,'scope')
    check(proof['all_owned_processes_retired'] and proof['all_owned_media_retired'] and proof['crypto_device_retired'],'retirement')
    archive=directory/'retained.tar.xz';check(sha(archive.read_bytes())=='sha256:'+proof['archive_sha256'],'archive_hash')
    files={}
    with tarfile.open(fileobj=io.BytesIO(decode(archive,12582912)),mode='r:') as stream:
        for member in stream:
            path=PurePosixPath(member.name)
            check(len(files)<256 and member.isfile() and member.size<=2097152 and not path.is_absolute() and
                  path.as_posix()==member.name and '..' not in path.parts and '\\' not in member.name and member.name not in files,'archive_entry')
            body=stream.extractfile(member).read(2097153);check(len(body)==member.size,'entry_size');files[member.name]=body
    inventory=report['archive']['entries']
    check(len(files)==len(inventory) and set(files)=={v['path'] for v in inventory},'entry_set')
    check(sum(map(len,files.values()))<=8388608,'original_bound')
    for row in inventory:check(len(files[row['path']])==row['bytes'] and sha(files[row['path']])=='sha256:'+row['sha256'],'entry_hash')
    check(strict_json(files['results.json'])=={k:v for k,v in report.items() if k!='archive'},'report_binding')
    for path,value in report['source_inputs'].items():check(sha((ROOT/path).read_bytes())==value,'source_identity')
    aliases={'windows-reference.py':HERE/'control.py','windows-reference-media.py':HERE/'media.py',
             'native-port.py':HERE.parent/'2026-10-20-differential-evidence/native-port.py',
             'windows_executor.py':ROOT/'tests/differential/windows_executor.py'}
    for alias,path in aliases.items():check(sha(path.read_bytes())=='sha256:'+proof['source_inputs'][alias],'controller_source_identity')
    spec=importlib.util.spec_from_file_location('replay_windows_fixtures',ROOT/facts['generator'])
    fixtures=importlib.util.module_from_spec(spec);spec.loader.exec_module(fixtures)
    check(sha((ROOT/facts['generator']).read_bytes())==facts['generator_sha256'],'generator_identity')
    check([fixtures.describe(name) for name in fixtures.CASES]==facts['cases'],'authored_facts')
    calls=proof['port_observations'];check(len(calls)==expected['port_calls']==25,'call_set')
    for call in calls:
        check(call['terminal'] and call['temporary_files_removed'] and call['job_retirement']['active_processes']==0,'call_retirement')
    for limit in proof['job_limits']:check(limit['flags']=='0x2208' and limit['job_commit_bytes']==268435456 and limit['process_limit']==8,'job_limits')
    def execution(row):
        call=calls[row['call_index']-1]
        check(row['argv']==call['argv'] and row['execution']=={k:call[k] for k in ('outcome','exit_code','elapsed_seconds','terminal')},'call_binding')
        for stream in ('stdout','stderr'):
            body=files[row['raw'][stream]['path']]
            check(sha(body)=='sha256:'+call['stream_sha256'][stream] and len(body)==call['returned_bytes'][stream],'stream_binding')
        return call
    check(len(report['compilation'])==5 and len(report['guards'])==3,'build_guard_set')
    for row in report['compilation']:check(execution(row)['exit_code']==0 and row['status']=='completed','build')
    for row in report['guards']:
        call=execution(row)
        if row['label']=='guards/invalid-handle':check(call['exit_code']==2 and not files[row['raw']['stdout']['path']],'invalid_handle')
        else:
            family=row['label'].split('/')[-1]
            check(call['exit_code']==0 and files[row['raw']['stdout']['path']].rstrip()==expected['native_guard_stdout'][family].encode(),'native_guard')
    execution(report['abi_call']);check(report['abi']==expected['sdk_abi']==strict_json(files['api-abi.stdout']),'sdk_abi')
    actual=[];findings=[]
    check([v['fixture'] for v in report['cases']]==facts['cases'],'case_set')
    for row in report['cases']:
        fact=row['fixture'];name=fact['name'];data=fixtures.generate(name)
        native=row['native'];call=execution(native['call']);payload=files[native['request']['path']]
        check(payload==(json.dumps(request(data,fact),separators=(',',':'))+'\n').encode() and sha(payload)=='sha256:'+call['stdin_sha256'],'native_request')
        value=strict_json(files[native['call']['raw']['stdout']['path']]);checks=[]
        for path,wanted in native_expectations(fact).items():
            observed=field(value,path);check(type(observed) is type(wanted) and observed==wanted,'native_fact')
            checks.append(dict(path=path,expected=wanted,actual=observed,matched=True))
        check(checks==native['checks'] and native_projection(value,fact['family'])==native['projection'],'native_projection')
        check(native['source']['sha256']==fact['sha256'] and native['source']['unchanged'] and native['source_removed'],'native_source')
        actual.append(dict(name=name,participant='native',kind='partition-candidates'))
        api=row['windows_api'];call=execution(api['call']);body=files[api['request']['path']];argument=strict_json(body)
        check(sha(body)=='sha256:'+call['stdin_sha256'] and len(call['argv'])==1,'delegated_request')
        media=row['media'];transfer=media['transfers'][0]
        check(len(media['transfers'])==1 and transfer['handle']==argument['handle'] and transfer['pid']==call['process_id'] and
              transfer['access']=='GENERIC_READ' and transfer['inheritable'] is False and transfer['suspended_job_member'],'capability')
        value=strict_json(files[api['call']['raw']['stdout']['path']]);projection=api_projection(value,report['abi'])
        operation='completed' if value['queries']['layout']['success'] else 'refused'
        check(api['operation_status']==operation,'operation_outcome')
        check(projection==api['projection'] and value['attachment_uuid']==media['attachment_uuid']==argument['attachment_uuid'] and
              value['nonce']==media['nonce']==argument['nonce'],'api_projection')
        check(media['attachment_flags']==3 and media['permanent_lifetime'] is False and media['parent_access']=='GENERIC_READ' and
              media['device_acl_changed'] is False and media['detach_code']==0 and media['post_detach_path_error']!=0 and media['removed'],'media_retirement')
        check(media['before']['file_id']==media['after']['file_id'] and media['payload_unchanged'],'media_identity')
        for snapshot in ('before','after'):
            observed=media[snapshot];footer=bytes.fromhex(observed['footer_hex']);check(len(footer)==512,'footer_size')
            mutable=bytearray(footer);checksum=struct.unpack_from('>I',mutable,64)[0];mutable[64:68]=bytes(4)
            check(footer[:8]==b'conectix' and struct.unpack_from('>Q',footer,48)[0]==4194304 and
                  checksum==((~sum(mutable))&0xffffffff) and observed['payload_sha256']==fact['sha256'] and
                  sha(data+footer)==observed['file_sha256'],'media_hash')
        matches=matching_candidates(native['projection'],projection)
        check(matches==api['matching_native_candidates'],'candidate_comparison')
        check(api['comparison_status']==('not_comparable' if projection is None else 'agreement' if matches else 'disagreement'),'comparison_dimensions')
        if name=='gpt-conflicting':check(native['projection']['comparison']==2 and len(native['projection']['candidates'])==2,'conflict_retained')
        actual.append(dict(name=name,participant='windows-api',kind='drive-layout-ex'))
        check(row['ui']==dict(status='not_run'),'no_ui_substitution')
        findings.append(dict(name=name,operation_status=operation,winerror=value['queries']['layout']['winerror'],
                             windows_projection=projection,matching_candidates=matches,ui='not_run'))
    missing=[v for v in facts['required_observations'] if v not in actual]
    check(actual==report['actual_observation_tuples'] and len(actual)==8 and len(missing)==4 and
          missing==report['missing_observations'] and report['ui_observations']==proof['ui_observations']==0,'incomplete_expected_set')
    result=dict(status='available_native_api_slice_pass',evidence_status='incomplete',campaign_complete=False,
        source_revision=report['source_revision'],port_calls=25,observations=8,missing_observations=missing,findings=findings,
        archive_bytes=archive.stat().st_size,archive_entries=len(files),original_bytes=sum(map(len,files.values())),
        all_owned_media_retired=True,all_owned_processes_retired=True,owner_accepted=False,release_qualified=False)
    (directory/'replay.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result))

if __name__=='__main__':main()
