"""Verify retained structure-review evidence; does not rerun native tests."""
import hashlib
import json
from pathlib import Path
import subprocess
import tarfile


def sha(data):
    return 'sha256:' + hashlib.sha256(data).hexdigest()


def main():
    evidence = Path(__file__).resolve().parent
    root = evidence.parents[2]
    inventory = json.loads((evidence / 'inventory.json').read_bytes())
    actual = {p.relative_to(evidence).as_posix() for p in evidence.rglob('*')
              if p.is_file() and '__pycache__' not in p.parts} - {'inventory.json'}
    assert actual == {v['path'] for v in inventory['files']}
    for item in inventory['files']:
        data = (evidence / item['path']).read_bytes()
        assert len(data) == item['bytes'] and sha(data) == item['sha256'], item['path']
    validation = json.loads((evidence / 'validation.json').read_bytes())
    assert validation['status'] == 'pass' and not validation['native_tests_run_in_followup']
    assert not validation['owner_accepted'] and not validation['release_ready']
    assert validation['spec_tool_tests'] == 224 and validation['spec_tool_skipped'] == 2
    assert validation['boundary_fixture_tests'] == 29 and validation['source_files'] == 218
    for record in validation['commands']:
        assert sha((root / record['evidence_path']).read_bytes()) == record['sha256']
    commands = json.loads((evidence / 'commands.json').read_bytes())
    assert validation['commands'] == commands
    assert len([r for r in commands if r['exit_code'] != 0]) == 2
    assert next(r for r in commands if r['evidence_path'].endswith('/verify-context.log'))['exit_code'] == 0
    assert next(r for r in commands if r['evidence_path'].endswith('/historical-gpt-index-retention.log'))['exit_code'] == 0
    for item in json.loads((evidence / 'advisory-inputs.json').read_bytes()):
        data = (root / item['path']).read_bytes()
        assert len(data) == item['bytes'] and sha(data) == item['sha256'], item['path']
    source = json.loads((evidence / 'source-inventory.json').read_bytes())
    base = validation['base_revision']
    paths = subprocess.check_output(['git', 'ls-tree', '-r', '--name-only', base, '--', 'source'], cwd=root).decode().splitlines()
    assert set(paths) == {v['path'] for v in source['files']}
    raw = subprocess.check_output(['git', 'cat-file', '--batch'], cwd=root,
        input=('\n'.join(base + ':' + v['path'] for v in source['files']) + '\n').encode())
    position = 0
    for item in source['files']:
        end = raw.index(b'\n', position)
        header = raw[position:end].split()
        assert len(header) == 3 and header[1] == b'blob', item['path']
        size = int(header[2])
        data = raw[end + 1:end + size + 1]
        position = end + size + 2
        assert sha(data) == item['sha256'], item['path']
    with tarfile.open(evidence / 'context.tar.gz', 'r:gz') as archive:
        members = archive.getmembers()
        assert all(m.isfile() and not m.name.startswith('/') and '..' not in Path(m.name).parts for m in members)
        manifest = json.loads(archive.extractfile('manifest.json').read())
        assert manifest == json.loads((evidence / 'context-manifest.json').read_bytes())
        assert sha(archive.extractfile('context.md').read()) == manifest['payload_sha256']
        assert any(v['path'] == 'spec/architecture/repository.md' for v in manifest['files'])
        assert any(v['path'] == 'docs/structure-review.md' for v in manifest['files'])
        for item in manifest['files']:
            if item['delivery'] == 'artifact':
                data = archive.extractfile('artifacts/' + item['path']).read()
                assert len(data) == item['bytes'] and sha(data) == item['sha256'], item['path']
    github = json.loads((evidence / 'github-observations.json').read_bytes())
    assert github['github_login'] == 'Julesc013'
    assert github['setup_pr']['headRefOid'] == '0fc1f90de0699379a0b4064b805d86fc51a7332f'
    assert next(v for v in github['setup_pr']['statusCheckRollup'] if v['name'] == 'native-windows')['conclusion'] == 'FAILURE'
    assert github['disked_releases'] == github['setup_releases'] == []
    print(json.dumps(dict(status='pass', retained_files=len(actual), source_files=len(paths),
                         scope='Retained integrity, not native execution or acceptance.')))


if __name__ == '__main__':
    main()
