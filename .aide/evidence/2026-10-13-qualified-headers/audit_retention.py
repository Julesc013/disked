"""Audit namespace/header ownership receipts at their exact native source."""
import hashlib
import json
from pathlib import Path
import re
import subprocess


def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def main():
    evidence = Path(__file__).resolve().parent
    root = evidence.parents[2]
    summary = json.loads((evidence/'summary.json').read_bytes())
    identity = json.loads((evidence/'build-identity.json').read_bytes())
    inputs = json.loads((evidence/'source-inputs.json').read_bytes())
    bindings = json.loads((evidence/'source-blob-bindings.json').read_bytes())
    commands = json.loads((evidence/'commands.json').read_bytes())
    inventory = json.loads((evidence/'retention.json').read_bytes())
    boundary = json.loads((evidence/'build-boundaries.json').read_bytes())
    usage = json.loads((evidence/'private-header-usage.json').read_bytes())
    source = summary['source_revision']
    assert summary['passed'] and summary['source_state'] == 'clean'
    assert not summary['owner_accepted'] and not summary['unit_complete'] and not summary['release_ready']
    assert identity['identity']['source_revision'] == source and identity['identity']['source_state'] == 'clean'
    assert set(inputs) == set(bindings) and len(inputs) == summary['source_input_count']
    raw = subprocess.check_output(['git','cat-file','--batch'], cwd=root,
                                  input=('\n'.join(source+':'+name for name in inputs)+'\n').encode())
    offset = 0
    for name in inputs:
        end = raw.index(b'\n', offset)
        header = raw[offset:end].split()
        assert len(header) == 3 and header[1] == b'blob', name
        size = int(header[2])
        data = raw[end+1:end+size+1]
        offset = end+size+2
        assert sha(data) == inputs[name] and header[0].decode() == bindings[name], name
    assert identity['inputs'] == {name: inputs[name] for name in identity['inputs']}
    assert len(identity['inputs']) == summary['product_input_count']
    assert summary['qualified_namespace'] and summary['compile_visibility_checked']
    assert summary['native_test_groups'] == 85 and summary['checker_negative_fixtures'] == 29
    assert summary['independent_header_compilations'] == 7
    assert summary['windows_adapter_executables_compiled'] == 20 and not summary['windows_physical_queries_run']
    assert {'configure','build','boundaries','windows-configure','windows-compile','native-tests','tooling','verify-context','product-launch','final-source-status'} <= {v['name'] for v in commands}
    for command in commands:
        assert command['exit_code'] == 0 and (evidence/command['log']).is_file(), command['name']
    native = (evidence/'native-details.log').read_text(encoding='utf-8')
    assert len(re.findall(r'^Test Passed\.$', native, re.MULTILINE)) == 85
    assert 'Ran 29 tests' in (evidence/'logs/checker-negative-fixtures.log').read_text(encoding='utf-8')
    assert boundary['status'] == 'PASS' and not boundary['violations']
    assert usage['schema'] == 'org.disked.private-header-usage/1'
    headers = {h for v in usage['targets'].values() for h in v['headers']}
    assert len(headers) == 80
    assert set(boundary['visible_headers']['json_codec_probe']) == {'source/runtime/command/json.h'}
    assert 'source/runtime/invocation/policy.h' not in boundary['visible_headers']['command_parser_probe']
    assert len(json.loads((evidence/'header-objects.json').read_bytes())) == 7
    windows = json.loads((evidence/'windows-artifacts.json').read_bytes())
    assert len(windows) == 20 and all(v['validation'] == 'compiled_not_launched' for v in windows)
    closure = set(boundary['targets']['disked']['build_closure'])
    assert not closure & {'disked_gpt_fixture_execution','disked_gpt_fixture_restoration','disked_gpt_fixture_files',
                          'disked_json_headers','disked_command_headers','disked_invocation_headers','disked_presentation_headers'}
    retained = {p.relative_to(evidence).as_posix() for p in evidence.rglob('*')
                if p.is_file() and '__pycache__' not in p.parts} - {'retention.json'}
    assert retained == set(inventory['files']) and inventory['source_revision'] == source
    for name, expected in inventory['files'].items():
        assert sha((evidence/name).read_bytes()) == expected, name
    assert sha((evidence/'reproduce.py').read_bytes()) == inputs['.aide/evidence/2026-10-13-qualified-headers/reproduce.py']
    current = subprocess.check_output(['git','rev-parse','HEAD'], cwd=root).decode().strip()
    print(json.dumps(dict(status='PASS', native_source_revision=source, current_revision=current,
                         retained_files=len(retained), source_blob_bindings=len(inputs),
                         declared_main_headers=len(headers), native_groups=85, checker_tests=29,
                         standalone_windows_compiled=20, physical_queries_run=False,
                         owner_accepted=False, release_ready=False), indent=2))


if __name__ == '__main__':
    main()
