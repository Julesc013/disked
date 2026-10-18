"""Verify current native/tool evidence and record the remaining product work."""
import hashlib
import json
from pathlib import Path
import subprocess
import jsonschema

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


compiler = json.loads((HERE / 'compiler-results.json').read_bytes())
assert compiler['status'] == 'pass' and compiler['guest']['setup']['image_removed']
for entry in compiler['sources']['files']:
    name = entry['path']
    if name.startswith('tools/'):
        path = ROOT / name
    elif name in ('guest-proof.ps1', 'attach-image.py'):
        path = ROOT / '.aide/evidence/2026-10-18-guest-capacity' / name
    else:
        path = HERE / ('compiler-driver.py' if name == 'guest-proof.py' else name)
    assert sha(path)[7:] == entry['sha256'].lower(), name
tools = json.loads((HERE / 'tooling-checks.json').read_bytes())
snapshot = json.loads((HERE / 'source-snapshot-tests.json').read_bytes())
assert tools['passed'] and snapshot['status'] == 'pass'
assert sha(HERE / 'source-snapshot.py')[7:] == snapshot['source_sha256']
for name, expected in tools['source_hashes'].items():
    assert sha(ROOT / name)[7:] == expected
artifacts = ['compiler-results.json', 'compiler-cleanup.json', 'tooling-checks.json',
             'source-snapshot-tests.json', 'context.json', 'final-observations.json',
             'observations.json.xz', 'observations-index.json', 'README.md']
changed = subprocess.check_output(['git', 'diff', '--name-only'], cwd=ROOT, text=True).splitlines()
changed += [p.relative_to(ROOT).as_posix() for p in HERE.iterdir() if p.is_file()]
target = ROOT / '.aide/handoffs/2026-10-18-guest-native.json'
changed.append(target.relative_to(ROOT).as_posix())
record = {
    'schema': 'org.disked.handoff/1', 'work_id': 'DE-W105',
    'base_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
    'spec_manifest_digest': sha(ROOT / 'spec/manifest.json'), 'status': 'partial',
    'files_read': ['AGENTS.md', 'spec/START-HERE.md', 'spec/index.md', 'spec/work/units.json',
                   'spec/catalog/ntfs-name-order-command-prototype.json',
                   'spec/schemas/handoff.schema.json', '.aide/programmes/disked-0.1.0.json',
                   'tools/windows-worker.py', 'tests/tools/test_windows_worker.py', 'tools/workspace.py',
                   'tools/build-bootstrap.py', 'tools/workspace.cmake', 'tools/build-inputs.json',
                   'CMakeLists.txt', 'tools/ntfs-win32-fixture.py',
                   '.aide/evidence/2026-10-18-guest-capacity/README.md'],
    'files_changed': sorted(set(changed)),
    'summary': 'Pinned MSVC/SDK compiled, linked and launched retained static-runtime x64 and Win32 probes inside the proven guest cap. Both verified exact compiler/pointer/PE identity, AppContainer=1, elevation=0 and outside-write error5; direct imports and artifact hashes retained. Initial compiler D8018 and the subsequent native/Python temporary-path diagnostic are preserved in one verified compressed archive. Worker now creates its native package temporary directory in fresh owned work, validates it before reuse and refuses a replaced junction.106 tooling tests pass/one skip; seven actual tiny Git fixtures validate bounded exact shallow/sparse source transport without history or unselected blobs. Product sources are unchanged; actual DiskEd export/build/native supplement remains next. Image, objects, executables, mappings, guest source/report copy and context packs removed; no backing-file growth during successful compiler run. Agents primary, Codex spare; host UAC/shared VM resources unchanged. No product, owner or release qualification.',
    'tests': [
        {'command': 'python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-18-guest-native/validate-tools.py', 'cwd': str(ROOT), 'status': 'pass', 'exit_code': 0, 'evidence_path': (HERE / 'tooling-checks.json').relative_to(ROOT).as_posix()},
        {'command': 'python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-18-guest-native/compiler-campaign.py', 'cwd': str(ROOT), 'status': 'pass', 'exit_code': 0, 'evidence_path': (HERE / 'compiler-results.json').relative_to(ROOT).as_posix()},
        {'command': 'python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-18-guest-native/test-source-snapshot.py', 'cwd': str(ROOT), 'status': 'pass', 'exit_code': 0, 'evidence_path': (HERE / 'source-snapshot-tests.json').relative_to(ROOT).as_posix()},
        {'command': 'Current structure/manifest and fresh DE-W105 context generation/verification', 'cwd': str(ROOT), 'status': 'pass', 'exit_code': 0, 'evidence_path': (HERE / 'context.json').relative_to(ROOT).as_posix()},
        {'command': 'Actual DiskEd source export/product build/eighteen-group private Win32 supplement', 'cwd': 'BlackGlass-HyperV', 'status': 'not_run', 'exit_code': None, 'evidence_path': None}],
    'artifacts': [{'path': (HERE / name).relative_to(ROOT).as_posix(), 'sha256': sha(HERE / name)} for name in artifacts],
    'blockers': ['Actual clean DiskEd snapshot/export/product build and DE-W105 private Win32 supplement remain unrun; no missing account, UAC or compiler-probe authority.',
                 'Native direct-import observations do not establish transitive dependencies, full product or other-platform support.'],
    'next_safe_step': 'From a clean checkpoint export the exact selected source with the tested bounded shallow/sparse helper. Materialize it in the Agents guest, create one bounded512MiB worker workspace and obtain a pinned x64 CMake File API codemodel. Build/qualify the private Win32 fixture with all18 groups/12 headers/9 executable observations, retaining compact source-bound results and cleaning disposable output. Keep original broader0.1.0/owner/storage/release gates real.',
    'performed_remote_writes': False}
jsonschema.Draft202012Validator(json.loads((ROOT / 'spec/schemas/handoff.schema.json').read_bytes())).validate(record)
target.write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps({'status': 'pass', 'source_bindings_verified': len(compiler['sources']['files']),
                  'tooling_tests': tools['tests_run'], 'snapshot_tests': snapshot['tests_run'],
                  'native_architectures': list(compiler['guest']['proof']['architectures'])}))
