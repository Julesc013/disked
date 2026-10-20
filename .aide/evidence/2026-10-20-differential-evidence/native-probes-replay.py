"""Bounded host replay of retained guest diagnostics; no native execution."""
import copy
import hashlib
import importlib.util
import io
import json
import lzma
import os
from pathlib import Path, PurePosixPath, PureWindowsPath
import sys
import tarfile

ROOT=Path(__file__).resolve().parents[3]
HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(ROOT/'tests/differential'))
from projections import field, native_projection, native_request, strict_json


def check(value,reason):
    if not value:raise ValueError(reason)


def digest(body):return 'sha256:'+hashlib.sha256(body).hexdigest()


def decode(path,limit):
    body=path.read_bytes();check(len(body)<=1048576,'compressed_bound')
    decoder=lzma.LZMADecompressor(format=lzma.FORMAT_XZ,memlimit=8*1024*1024)
    raw=decoder.decompress(body,max_length=limit+1)
    check(len(raw)<=limit and decoder.eof and not decoder.unused_data,'decompression_bound')
    return raw


def audit(files,proof,expected,recipes):
    report=strict_json(files['native-results.json']);outer=proof['probe_run'];inventory=outer['archive']['entries']
    check(set(files)=={v['path'] for v in inventory} and len(files)==len(inventory),'archive_entry_set')
    for row in inventory:
        check(len(files[row['path']])==row['bytes'] and digest(files[row['path']])=='sha256:'+row['sha256'],'entry_hash')
    check(report=={k:v for k,v in outer.items() if k!='archive'} and report['status']=='pass','report_binding')
    check([v['name'] for v in report['cases']]==[v['name'] for v in recipes]==[v['name'] for v in expected['cases']],'case_set')
    calls=proof['port_observations'];check(len(calls)==49,'execution_set')
    check(proof['status']=='pass' and proof['all_owned_processes_retired'] and proof['crypto_device_retired'],'worker_retirement')
    for call in calls:
        check(call['terminal'] and call['temporary_files_removed'] and call['job_retirement']['active_processes']==0,'call_retirement')
    for limit in proof['job_limits']:
        check(limit['flags']=='0x2208' and limit['job_commit_bytes']==268435456 and limit['process_limit']==8,'job_limits')
    check(proof['native_identity']['restricted'] and proof['native_identity']['in_job'] and
          not proof['native_identity']['elevated'] and not proof['native_identity']['appcontainer'],'token_profile')
    for row,call in zip(report['compilation'],calls[8:12]):
        check(row['argv']==call['argv'] and row['status']=='completed' and call['exit_code']==0,'compilation')
        for stream in ('stdout','stderr'):check(digest(files[row['raw'][stream]['path']])=='sha256:'+call['stream_sha256'][stream],'compile_stream')
    check(len(report['guards'])==2,'guard_set')
    for row,call in zip(report['guards'],calls[12:14]):
        check(row['status']=='completed' and call['exit_code']==0 and call['argv'][-1]=='--guard','guard_execution')
        check(files[row['raw']['stdout']['path']].rstrip()==expected['guard_stdout'][row['family']].encode() and
              files[row['raw']['stderr']['path']]==b'','guard_result')
    count=0
    for row,recipe,fact in zip(report['cases'],recipes,expected['cases']):
        data=files[row['fixture']['path']];check(data==recipe['data'] and digest(data)==fact['sha256'],'fixture_bytes')
        request=files[row['request']['path']]
        check(request==(json.dumps(native_request(data,recipe),separators=(',',':'))+'\n').encode(),'request_binding')
        call=calls[row['call_index']-1]
        check(call['outcome']=='exited' and call['exit_code']==0 and row['status']=='completed' and
              row['execution']=={k:call[k] for k in ('outcome','exit_code','elapsed_seconds','terminal')},'execution_result')
        check(len(call['argv'])==1 and PureWindowsPath(call['argv'][0]).name==row['family']+'-probe.exe' and
              'sha256:'+call['stdin_sha256']==digest(request) and call['stdin_bytes']==len(request),'native_call')
        check(row['file_before']==row['file_after'] and row['file_before']['bytes']==len(data) and
              row['input_unchanged'] is True and row['input_after']==row['fixture'],'fixture_preservation')
        check(row['executable_before_sha256']==row['executable_after_sha256']==report['artifacts'][row['family']]['sha256'],'executable_preservation')
        for stream in ('stdout','stderr'):
            body=files[row['raw'][stream]['path']]
            check(digest(body)=='sha256:'+call['stream_sha256'][stream] and len(body)==call['returned_bytes'][stream],'raw_stream_binding')
        check(files[row['raw']['stderr']['path']]==b'','native_diagnostics')
        value=strict_json(files[row['raw']['stdout']['path']]);checks=[]
        for path,wanted in fact['checks'].items():
            actual=field(value,path);check(type(actual) is type(wanted) and actual==wanted,'authored_fixture_check')
            checks.append(dict(path=path,expected=wanted,actual=actual,matched=True));count+=1
        check(row['checks']==checks,'retained_check_binding')
        check(row['projection']==native_projection(value,row['family']),'raw_projection')
    check(count==report['checks']==64,'check_count')
    conflict=next(v for v in report['cases'] if v['name']=='gpt-valid-disagreement')['projection']
    check(conflict['comparison']==2 and len(conflict['candidates'])==2 and conflict['candidates'][0]['rows']!=conflict['candidates'][1]['rows'],'retained_conflict')
    return dict(cases=35,checks=count,guards=2,native_calls=49,archive_entries=len(files),uncompressed_bytes=sum(len(v) for v in files.values()))


def main():
    check(bool(os.environ.get('DISKED_WORK_ROOT')),'managed_runner_required')
    receipt=strict_json(decode(HERE/'native-probes-result.json.xz',4194304));proof=receipt['guest']['proof']
    check(receipt['status']=='pass' and receipt['host_exit_code']==0,'guest_outcome')
    archive=HERE/'native-probes-observations.tar.xz';check(hashlib.sha256(archive.read_bytes()).hexdigest()==proof['archive_sha256'],'archive_hash')
    files={}
    with tarfile.open(fileobj=io.BytesIO(decode(archive,20*1024*1024)),mode='r:') as stream:
        for member in stream:
            path=PurePosixPath(member.name)
            check(len(files)<256 and member.isfile() and member.size<=2097152 and not path.is_absolute() and
                  path.as_posix()==member.name and '..' not in path.parts and '\\' not in member.name and member.name not in files,'archive_entry')
            body=stream.extractfile(member).read(2097153);check(len(body)==member.size,'archive_entry_size');files[member.name]=body
    expected=strict_json((HERE/'native-probes-expected.json').read_bytes())
    path=ROOT/'tests/corpus/partition_images.py';check(hashlib.sha256(path.read_bytes()).hexdigest()==expected['generator_sha256'],'generator_identity')
    spec=importlib.util.spec_from_file_location('retained_native_corpus',path);corpus=importlib.util.module_from_spec(spec);spec.loader.exec_module(corpus);recipes=corpus.recipes()
    for name,value in proof['probe_run']['source_inputs'].items():check(hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==value,'source_identity')
    for name in ('native-probes.py','native-port.py'):
        check(hashlib.sha256((HERE/name).read_bytes()).hexdigest()==proof['source_inputs'][name],'coordinator_identity')
    summary=audit(files,proof,expected,recipes);controls=[]
    for mode,reason in [('raw','entry_hash'),('missing','archive_entry_set'),('projection','raw_projection')]:
        changed=dict(files);altered=copy.deepcopy(proof)
        if mode=='raw':changed['cases/mbr-two.stdout']+=b' '
        elif mode=='missing':del changed['cases/mbr-two.img']
        else:
            report=strict_json(changed['native-results.json']);row=next(v for v in report['cases'] if v['name']=='mbr-two')
            row['projection']['candidates'][0]['rows'][0]['start']=2
            changed['native-results.json']=(json.dumps(report,indent=2)+'\n').encode()
            altered['probe_run']={**report,'archive':altered['probe_run']['archive']}
            descriptor=next(v for v in altered['probe_run']['archive']['entries'] if v['path']=='native-results.json')
            descriptor.update(bytes=len(changed['native-results.json']),sha256=hashlib.sha256(changed['native-results.json']).hexdigest())
        try:audit(changed,altered,expected,recipes)
        except ValueError as error:check(str(error)==reason,'negative_control_reason');controls.append(dict(control=mode,rejected_by=str(error)))
        else:raise ValueError('Negative replay control passed:'+mode)
    result=dict(status='pass',scope=__doc__,**summary,negative_controls=controls,source_inputs_verified=True,
        backing_logical_length_delta_bytes=receipt['host_backing_end_bytes']-receipt['host_backing_start_bytes'],allocated_backing_delta='not_measured',
        source_base='5f53e0df4c660626e22f1d36ee5805bc3e13f03c',working_tree_inputs=True,
        guest_cleanup=json.loads((HERE/'native-probes-cleanup.json').read_bytes()),reference_tests_run=False,finalized_comparison_packet=False,owner_accepted=False)
    (HERE/'native-probes-replay.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps(result))


if __name__=='__main__':main()
