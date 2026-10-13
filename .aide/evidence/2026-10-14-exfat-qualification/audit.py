"""Audit retained exact-source DE-W058 evidence; never infer unrun results."""
import argparse, hashlib, json
from pathlib import Path

def read(path): return json.loads(path.read_bytes())
def sha(path): return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()
def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('evidence',type=Path)
    args=parser.parse_args(); evidence=args.evidence.resolve()
    summary=read(evidence/'summary.json'); commands=read(evidence/'commands.json')
    assert summary['passed'] and summary['source_state']=='clean'
    assert not summary['owner_accepted'] and not summary['full_0_1_0_complete']
    assert all(c['exit_code']==0 for c in commands)
    names={c['name'] for c in commands}
    required={'gcc-c90','boundary-unit-tests','build','boundaries','native-tests','tooling',
              'spec-check','index','manifest','context','verify-context','product-launch',
              'command-discovery','disked-headers','disked-imports','disked-dependents',
              'exfat_probe-headers','exfat_probe-imports','exfat_probe-dependents','final-source-status'}
    assert required.issubset(names)
    cases=read(evidence/'exfat-cases.json')
    assert cases['passed'] and cases['methods']==8 and cases['cases']==2320
    catalog=read(evidence/'test-catalog.json')
    assert {'portable.exfat','portable.exfat_guard','portable.gpt','portable.fat',
            'build.boundaries'}.issubset(t['name'] for t in catalog['tests'])
    assert summary['native_test_groups']==len(catalog['tests'])
    assert summary['header_compilations']==len(read(evidence/'header-objects.json'))
    assert summary['tooling_run']==242 and summary['tooling_skips']==2
    assert read(evidence/'build-boundaries.json')['status']=='PASS'
    assert len(read(evidence/'source-inputs.json'))==len(read(evidence/'source-blob-bindings.json'))
    for artifact in summary['artifacts']:
        path=Path(artifact['path'])
        assert path.is_file() and sha(path)==artifact['sha256']
        assert path.stat().st_size==artifact['bytes']
        assert artifact['source_revision']==summary['source_revision']
    for artifact in read(evidence/'header-objects.json'):
        path=Path(artifact['path'])
        assert path.is_file() and sha(path)==artifact['sha256']
        assert path.stat().st_size==artifact['bytes']
    native_log=(evidence/'logs/native-tests.log').read_text(encoding='utf-8')
    assert '100% tests passed, 0 tests failed out of '+str(summary['native_test_groups']) in native_log
    assert not (evidence/'failure.json').exists()
    criteria=[
        dict(criterion=1,status='pass',evidence=['exfat-cases.json','logs/gcc-c90.log'],scope='Independent byte/integer/checksum geometry oracle across512..4096 sectors, main/backup, one/twoFAT, min/max and u64conversion boundaries.'),
        dict(criterion=2,status='pass',evidence=['exfat-cases.json','native-details.log'],scope='Rehashed contradictions, truncation, inaccessible tails, invalid calls and preserved output/input; read-only memory guards.'),
        dict(criterion=3,status='pass',evidence=['exfat-cases.json'],scope='Everychecksum word, excluded mutable fields, OEM/extended/reserved bytes. No bitmap allocation or TexFAT transaction claim.'),
        dict(criterion=4,status='pass',evidence=['summary.json','build-identity.json','header-objects.json','logs/exfat_probe-imports.log','logs/native-tests.log'],scope='Exact clean source, native build/header/import/artifact and full regression evidence; no host/provider/writer/fullrelease admission.')]
    result=dict(work_id='DE-W058',source_revision=summary['source_revision'],status='pass',criteria=criteria,owner_accepted=False,independent_human_review=False)
    (evidence/'criteria-audit.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('All four bounded DE-W058 criteria evidenced at '+summary['source_revision'])
if __name__=='__main__': main()
