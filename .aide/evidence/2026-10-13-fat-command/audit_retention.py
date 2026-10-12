"""Verify retained shared FAT command evidence at its exact source, without rerunning."""
import hashlib
import json
from pathlib import Path
import re
import subprocess


def sha(data):
    return 'sha256:'+hashlib.sha256(data).hexdigest()


def main():
    evidence=Path(__file__).resolve().parent; root=evidence.parents[2]
    summary=json.loads((evidence/'summary.json').read_bytes())
    identity=json.loads((evidence/'build-identity.json').read_bytes())
    inputs=json.loads((evidence/'source-inputs.json').read_bytes())
    bindings=json.loads((evidence/'source-blob-bindings.json').read_bytes())
    receipts=json.loads((evidence/'commands.json').read_bytes())
    inventory=json.loads((evidence/'retention.json').read_bytes())
    boundary=json.loads((evidence/'build-boundaries.json').read_bytes())
    usage=json.loads((evidence/'private-header-usage.json').read_bytes())
    cases=json.loads((evidence/'fat-cases.json').read_bytes())
    source=summary['source_revision']
    assert summary['passed'] and summary['source_state']=='clean'
    assert not any(summary[key] for key in ('physical_device_access','filesystem_health_qualified','owner_accepted','unit_complete','release_ready'))
    assert identity['identity']['source_revision']==source and identity['identity']['source_state']=='clean'
    assert len(inputs)==summary['source_input_count'] and set(inputs)==set(bindings)
    blobs=subprocess.check_output(['git','cat-file','--batch'],cwd=root,
        input=('\n'.join(source+':'+name for name in inputs)+'\n').encode())
    offset=0
    for name in inputs:
        end=blobs.index(b'\n',offset); fields=blobs[offset:end].split()
        assert len(fields)==3 and fields[1]==b'blob',name
        size=int(fields[2]); data=blobs[end+1:end+size+1];offset=end+size+2
        assert sha(data)==inputs[name] and fields[0].decode()==bindings[name],name
    assert identity['inputs']=={name:inputs[name] for name in identity['inputs']}
    assert len(identity['inputs'])==summary['product_input_count']
    assert summary['native_test_groups']==97 and summary['independent_header_compilations']==17
    assert summary['fat_test_methods']==19 and summary['fat_cases']==1335
    assert cases['passed'] and cases['tests_run']==19 and cases['cases']==1335
    directory=json.loads((evidence/'fat-directory-cases.json').read_bytes())
    assert summary['directory_test_methods']==19 and summary['directory_cases']==6790
    assert directory['passed'] and directory['tests_run']==19 and directory['cases']==6790
    assert sum(row['cases'] for row in directory['batches'])==6790
    captured=json.loads((evidence/'fat-capture-cases.json').read_bytes())
    assert summary['capture_test_methods']==20 and summary['capture_cases']==149
    assert captured['passed'] and captured['tests_run']==20 and captured['cases']==149
    assert sum(row['cases'] for row in captured['batches'])==149
    assert sum(row['cases'] for row in captured['batches'] if row['surface']=='ordinary-file')==11
    for name,methods,count in [('fat-allocation-scan',13,86),('fat-auxiliary',14,257),('fat-namespace',14,171)]:
        value=json.loads((evidence/(name+'-cases.json')).read_bytes())
        assert value['passed'] and value['tests_run']==methods and value['cases']==count
        assert sum(row['cases'] for row in value['batches'])==count
    assert summary['namespace_test_methods']==14 and summary['namespace_cases']==171
    names=json.loads((evidence/'fat-namespace-cases.json').read_bytes())
    assert sum(row['cases'] for row in names['batches'] if row['surface']=='ordinary-file')==21
    worker=json.loads((evidence/'fat-worker-cases.json').read_bytes())
    assert summary['worker_test_methods']==11 and summary['worker_cases']==109
    assert worker['passed'] and worker['tests_run']==11 and worker['cases']==109
    assert sum(row['cases'] for row in worker['batches'])==109
    assert len(worker['quota_observations'])==1
    quota=worker['quota_observations'][0]
    assert quota['fifth_error']=='observation_spawn_failed' and quota['fifth_never_launched']
    assert len(quota['peer_retirements'])==4 and all(p['worker']['observation']=='exited' for p in quota['peer_retirements'])
    catalog=json.loads((evidence/'logs/test-catalog.log').read_bytes())
    test=next(t for t in catalog['tests'] if t['name']=='image.fat_worker')
    assert any(p['name']=='RESOURCE_LOCK' and p['value']==['disked_fake_workers'] for p in test['properties'])
    test=next(t for t in catalog['tests'] if t['name']=='image.fat_commands')
    assert any(p['name']=='RESOURCE_LOCK' and p['value']==['disked_fake_workers'] for p in test['properties'])

    assert sum(row['cases'] for row in cases['batches'])==1335
    assert len(re.findall(r'^Test Passed\.$',(evidence/'native-details.log').read_text(encoding='utf-8'),re.MULTILINE))==97
    assert {'configure','build','gcc-c90','native-tests','tooling','spec-check','verify-context','product-launch','final-source-status'} <= {r['name'] for r in receipts}
    for receipt in receipts:
        assert receipt['exit_code']==0 and (evidence/receipt['log']).is_file(),receipt['name']
    gcc=json.loads((evidence/'gcc-identity.json').read_bytes())
    assert gcc['version']=='15.2.0' and 'syntax only' in gcc['scope']
    assert (evidence/'logs/gcc-version.log').read_text(encoding='utf-8').strip()=='15.2.0'
    assert boundary['status']=='PASS' and not boundary['violations']
    assert {'disked_fat','disked_fat_capture','disked_fat_file','disked_fat_namespace','disked_windows_file_names','disked_fat_inspection','disked_fat_reader'} <= set(boundary['targets']['disked']['build_closure'])
    assert not {'disked_fat_file_fault','disked_fat_worker_fault','disked_gpt_fixture_execution','disked_gpt_fixture_restoration','disked_gpt_fixture_files','disked_journal_prototype'} & set(boundary['targets']['disked']['build_closure'])
    assert not {'disked_gpt','disked_gpt_repair_planning','disked_map_observation'} & set(boundary['targets']['disked_fat_capture']['build_closure'])
    assert 'source/portable/fat/fat.h' not in boundary['visible_headers']['disked_fat_capture_headers']
    assert set(usage['targets']['disked_region_reader']['interface_headers'])=={'source/runtime/capture/region_reader.h'}
    assert {'source/portable/fat/volume.c','source/portable/fat/allocation.c','source/portable/fat/directory.c','source/portable/fat/auxiliary.c'} <= set(boundary['targets']['disked_fat']['sources'])
    assert set(usage['targets']['disked_fat']['headers'])=={'source/portable/fat/fat.h'}
    assert set(usage['targets']['disked_fat']['interface_headers'])=={'source/portable/fat/fat.h'}
    assert 'source/portable/fat/fat.h' in boundary['visible_headers']['fat_probe']
    assert 'source/portable/fat/fat.h' not in boundary['visible_headers']['disked']
    assert set(usage['targets']['disked_fat_namespace']['interface_headers'])=={'source/runtime/capture/fat_namespace.h'}
    assert set(usage['targets']['disked_windows_file_names']['interface_headers'])=={'source/platform/windows/file_names.h'}
    assert not {'disked_fat','disked_gpt','disked_command','disked_invocation'} & set(boundary['targets']['disked_fat_namespace']['build_closure'])
    assert 'source/runtime/capture/fat_namespace.h' in boundary['visible_headers']['disked_windows_file_names_headers']
    assert set(usage['targets']['disked_fat_snapshot']['interface_headers'])=={'source/providers/image/fat_snapshot.h'}
    assert set(usage['targets']['disked_fat_worker']['interface_headers'])=={'source/platform/windows/storage/fat_worker.h'}
    assert set(usage['targets']['disked_observation_worker']['interface_headers'])=={'source/platform/windows/storage/observation_worker.h'}
    assert {'disked_fat_snapshot','disked_fat_worker','disked_observation_worker'} <= set(boundary['targets']['disked']['build_closure'])
    command=json.loads((evidence/'fat-command-cases.json').read_bytes())
    assert summary['product_dispatch_admitted'] and summary['fat_command_cases']==61
    assert command['passed'] and command['cases']==61 and len(command['records'])==61
    for frontend in ('gui','tui','shell'):
        assert len([r for r in command['records'] if r['name'].startswith(frontend+'-')])==3
    assert set(usage['targets']['disked_fat_inspection']['interface_headers'])=={'source/runtime/capture/fat_inspection.h'}
    assert set(usage['targets']['disked_fat_reader']['interface_headers'])=={'source/platform/windows/storage/fat_reader.h'}
    assert len(json.loads((evidence/'header-objects.json').read_bytes()))==17
    actual={p.relative_to(evidence).as_posix() for p in evidence.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts} - {'retention.json'}
    assert actual==set(inventory['files']) and inventory['source_revision']==source
    for name,digest in inventory['files'].items():assert sha((evidence/name).read_bytes())==digest,name
    assert sha((evidence/'reproduce.py').read_bytes())==inputs['.aide/evidence/2026-10-13-fat-command/reproduce.py']
    assert sha((evidence/'audit_retention.py').read_bytes())==inputs['.aide/evidence/2026-10-13-fat-command/audit_retention.py']
    print(json.dumps(dict(status='PASS',native_source_revision=source,
        current_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip(),
        source_blob_bindings=len(inputs),retained_files=len(actual),native_groups=97,
        fat_methods=19,fat_cases=1335,directory_methods=19,directory_cases=6790,capture_methods=20,capture_cases=149,namespace_methods=14,namespace_cases=171,worker_methods=11,worker_cases=109,header_compilations=17,
        scope='owned FAT readers and named Windows regression; GCC strict-C90 syntax only',
        owner_accepted=False,release_ready=False),indent=2))


if __name__=='__main__':main()
