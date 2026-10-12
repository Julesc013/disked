"""Verify retained FAT allocation evidence at its exact source, without rerunning."""
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
    assert not any(summary[key] for key in ('reader_host_io','product_dispatch_admitted','filesystem_health_qualified','owner_accepted','unit_complete','release_ready'))
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
    assert summary['native_test_groups']==87 and summary['independent_header_compilations']==8
    assert summary['fat_test_methods']==19 and summary['fat_cases']==1335
    assert cases['passed'] and cases['tests_run']==19 and cases['cases']==1335
    assert sum(row['cases'] for row in cases['batches'])==1335
    assert len(re.findall(r'^Test Passed\.$',(evidence/'native-details.log').read_text(encoding='utf-8'),re.MULTILINE))==87
    assert {'configure','build','gcc-c90','native-tests','tooling','spec-check','verify-context','product-launch','final-source-status'} <= {r['name'] for r in receipts}
    for receipt in receipts:
        assert receipt['exit_code']==0 and (evidence/receipt['log']).is_file(),receipt['name']
    gcc=json.loads((evidence/'gcc-identity.json').read_bytes())
    assert gcc['version']=='15.2.0' and 'syntax only' in gcc['scope']
    assert (evidence/'logs/gcc-version.log').read_text(encoding='utf-8').strip()=='15.2.0'
    assert boundary['status']=='PASS' and not boundary['violations']
    assert 'disked_fat' not in boundary['targets']['disked']['build_closure']
    assert {'source/portable/fat/volume.c','source/portable/fat/allocation.c'} <= set(boundary['targets']['disked_fat']['sources'])
    assert set(usage['targets']['disked_fat']['headers'])=={'source/portable/fat/fat.h'}
    assert set(usage['targets']['disked_fat']['interface_headers'])=={'source/portable/fat/fat.h'}
    assert 'source/portable/fat/fat.h' in boundary['visible_headers']['fat_probe']
    assert 'source/portable/fat/fat.h' not in boundary['visible_headers']['disked']
    assert len(json.loads((evidence/'header-objects.json').read_bytes()))==8
    actual={p.relative_to(evidence).as_posix() for p in evidence.rglob('*')
            if p.is_file() and '__pycache__' not in p.parts} - {'retention.json'}
    assert actual==set(inventory['files']) and inventory['source_revision']==source
    for name,digest in inventory['files'].items():assert sha((evidence/name).read_bytes())==digest,name
    assert sha((evidence/'reproduce.py').read_bytes())==inputs['.aide/evidence/2026-10-13-fat-allocation/reproduce.py']
    print(json.dumps(dict(status='PASS',native_source_revision=source,
        current_revision=subprocess.check_output(['git','rev-parse','HEAD'],cwd=root).decode().strip(),
        source_blob_bindings=len(inputs),retained_files=len(actual),native_groups=87,
        fat_methods=19,fat_cases=1335,header_compilations=8,
        scope='FAT allocation metadata and named Windows regression; GCC strict-C90 syntax only',
        owner_accepted=False,release_ready=False),indent=2))


if __name__=='__main__':main()
