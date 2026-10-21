"""Replay the coordinator conformance packet; never execute retained commands."""
import copy
import hashlib
import importlib.util
import io
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tarfile

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
OLD = HERE.parent/'2026-10-20-differential-evidence'
sys.path.insert(0,str(ROOT/'tests/differential'))
from compare import compare
from collector import Output
from evidence import canonical_digest, digest
from projections import strict_json

def load(name,path):
    spec=importlib.util.spec_from_file_location(name,path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module);return module

def check(value,reason):
    if not value:raise ValueError(reason)

def main():
    check(bool(os.environ.get('DISKED_WORK_ROOT')),'managed_runner_required')
    native=load('native_control_replay',OLD/'native-probes-replay.py')
    receipt=strict_json(native.decode(HERE/'receipt.json.xz',8388608));proof=receipt['guest']['proof']
    expected=strict_json((HERE/'expected.json').read_bytes());controls=proof['probe_run']['coordinator_controls']
    check(receipt['status']=='pass' and receipt['host_exit_code']==0 and controls['status']=='pass','guest_success')
    archive=HERE/'retained.tar.xz'
    check(hashlib.sha256(archive.read_bytes()).hexdigest()==proof['archive_sha256'],'archive_hash')
    files={}
    with tarfile.open(fileobj=io.BytesIO(native.decode(archive,20*1024*1024)),mode='r:') as stream:
        for member in stream:
            path=PurePosixPath(member.name)
            check(len(files)<expected['limits']['archive_entries'] and member.isfile() and member.size<=2097152 and
                  not path.is_absolute() and path.as_posix()==member.name and '..' not in path.parts and
                  '\\' not in member.name and member.name not in files,'archive_entry')
            body=stream.extractfile(member).read(2097153);check(len(body)==member.size,'entry_size');files[member.name]=body
    check(sum(map(len,files.values()))<=expected['limits']['retained_original_bytes'],'original_bound')
    corpus=load('control_replay_corpus',ROOT/'tests/corpus/partition_images.py')
    baseline=copy.deepcopy(proof)
    baseline['port_observations']=baseline['port_observations'][:expected['native_baseline']['port_calls']]
    native_summary=native.audit(files,baseline,strict_json((OLD/'native-probes-expected.json').read_bytes()),corpus.recipes())
    calls=proof['port_observations']
    check(len(calls)==expected['total_port_calls']==controls['total_port_calls'],'exact_execution_set')
    for call in calls:
        check(call['terminal'] and call['temporary_files_removed'] and call['job_retirement']['active_processes']==0,'job_retirement')
    for name,value in controls['source_inputs'].items():check(digest((ROOT/name).read_bytes())==value,'source_input')
    for row in controls['compilation']:
        call=calls[row['call_index']-1]
        check(row['status']=='completed' and row['argv']==call['argv'] and call['exit_code']==0,'fixture_build')
        for stream in ('stdout','stderr'):check(digest(files[row['raw'][stream]['path']])=='sha256:'+call['stream_sha256'][stream],'fixture_build_raw')
    packet=Path(os.environ['DISKED_WORK_ROOT'])/'coordinator-replay';packet.mkdir()
    output=Output(packet)
    prefix='coordinator-packet/'
    for path,body in files.items():
        if path.startswith(prefix):output.artifact(path[len(prefix):],body)
    manifest=strict_json((packet/'manifest.json').read_bytes())
    snapshot=controls['frozen_manifest_sha256']
    check(snapshot==canonical_digest(manifest),'frozen_snapshot')
    check(manifest['selection']==dict(mode='explicit',names=expected['cases']),'selected_cases')
    check([[v[k] for k in ('name','participant','kind')] for v in manifest['expected_observations']]==expected['expected_tuples'],'tuple_set')
    participant=expected['participants'][1]
    records={who:strict_json((packet/'collections'/digest(who.encode())[7:23]/'results.json').read_bytes()) for who in expected['participants']}
    result=compare(manifest,records['native'],{participant:records[participant]},artifact_root=packet,expected_manifest_sha256=snapshot)
    retained=strict_json((packet/'coordinator/comparison.json').read_bytes())
    check(result==retained and result['complete_success'] and result['evidence_status']=='complete' and result['comparison_status']=='disagreement','comparison_replay')
    check(controls['positive']['receipt']==strict_json((packet/'coordinator/results.json').read_bytes()),'coordinator_receipt')
    selected_calls=[calls[index-1] for index in controls['positive']['calls']]
    check(len(selected_calls)==6,'actual_call_count')
    observations=records['native']['observations']+records[participant]['observations']
    for observation,call in zip(observations,selected_calls):
        check(observation['argv']==call['argv'] and observation['execution']['elapsed_seconds']==call['elapsed_seconds'] and
              observation['outcome']==call['outcome'] and observation['exit_code']==call['exit_code']==0,'actual_execution')
        for stream in ('stdout','stderr'):
            check(observation['raw'][stream]['sha256']=='sha256:'+call['stream_sha256'][stream],'collected_stream')
    negative=[]
    for mode in expected['negative_replay']:
        changed=copy.deepcopy(records)
        if mode=='missing':changed[participant]['observations'].pop()
        elif mode=='duplicate':changed[participant]['observations'].append(copy.deepcopy(changed[participant]['observations'][0]))
        elif mode=='wrong_geometry':changed[participant]['observations'][0]['unit']=4096
        else:changed[participant]['observations'][0]['stdout']+='tampered'
        value=compare(manifest,changed['native'],{participant:changed[participant]},artifact_root=packet,expected_manifest_sha256=snapshot)
        check(not value['complete_success'],'negative_replay')
        negative.append(dict(name=mode,evidence_status=value['evidence_status'],complete_success=False))
    check(negative==controls['negative_replay'],'negative_replay_binding')
    for target,row in zip(expected['negative_execution'],controls['negative_execution']):
        check(row['name']==target['name'] and not row['receipt']['complete_success'] and row['outer_jobs_retired'] and
              len(row['calls'])==target['native_calls'],'negative_execution')
        original=strict_json(files[row['name']+'/coordinator/results.json'])
        check(original==row['receipt'] and original['quiescence_unknown'],'interrupted_receipt')
        for index in row['calls']:check(len(calls[index-1]['argv'])==1,'no_fake_reference_execution')
    check(controls['actual_independent_reference_calls']==0 and controls['actual_reference_fixture_calls']==4 and
          controls['independent_reference_run'] is False and controls['full_campaign_qualified'] is False,'scope')
    cleanup=strict_json((HERE/'cleanup.json').read_bytes()) if (HERE/'cleanup.json').exists() else strict_json(native.decode(HERE/'cleanup.json.xz',1048576))
    summary=dict(status='pass',scope=__doc__,native_baseline=native_summary,port_calls=len(calls),
        evidence_status=result['evidence_status'],comparison_status=result['comparison_status'],complete_success=result['complete_success'],
        negative_replay=negative,negative_execution=controls['negative_execution'],archive_bytes=archive.stat().st_size,
        archive_entries=len(files),original_bytes=sum(map(len,files.values())),independent_reference_run=False,
        full_campaign_qualified=False,cleanup=cleanup,source_revision=controls['source_revision'])
    (HERE/'replay.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf-8',newline='\n')
    print(json.dumps({k:v for k,v in summary.items() if k not in ('negative_execution','cleanup')}))

if __name__=='__main__':main()
