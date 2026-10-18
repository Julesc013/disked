"""Retain compact checkpoint state; does not build, connect, push or accept work."""
import hashlib
import json
import lzma
from pathlib import Path
import subprocess
import jsonschema

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
PREFIX = HERE.relative_to(ROOT).as_posix()

def write(path, value):
    path.write_text(json.dumps(value, indent=2)+'\n', encoding='utf-8', newline='\n')

def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()

for name in ('coordinator-checks.json', 'coordinator-checks-before-fixture-fix.json'):
    path = HERE / name
    data = json.loads(path.read_bytes())
    if 'log' in data:
        raw = path.read_bytes()
        compressed = path.with_suffix('.json.xz')
        compressed.write_bytes(lzma.compress(raw, preset=9 | lzma.PRESET_EXTREME))
        assert lzma.decompress(compressed.read_bytes()) == raw
        del data['log']
        data['raw_observations'] = compressed.relative_to(ROOT).as_posix()
        data['raw_observations_sha256'] = sha(compressed)
        write(path, data)

native = json.loads((HERE / 'eighth-directory-acl.json').read_bytes())
assert native['guest']['source_prepared']['status'] == 'pass'
source = native['exact_source']['revision']
final = json.loads((HERE / 'final-observations.json').read_bytes())
assert final['guest']['qualification_removed'] and final['local_context_bytes'] == 0
programme_path = ROOT / '.aide/programmes/disked-0.1.0.json'
programme = json.loads(programme_path.read_bytes())
next_action = ('Continue DE-W105 from the retained guest-build checkpoint. Diagnose the precise directory that '
    'caused the noncanonical-DACL refusal, retaining its original descriptor and adding a path-specific diagnostic. '
    'Prefer the freshly owned qualification-root boundary; do not reset shared ancestor ACLs or propagate permission '
    'changes to their children. Keep Agents primary and Codex emergency-only. Then export an exact current source '
    'revision, obtain its pinned x64 codemodel, and build/test all18 private Win32 groups/12 headers/9 executables '
    'inside the existing512MiB cap. Final wrapper cleanup/report fixes have syntax/retention checks but no native '
    'retest. Complete the full x64 product/build-gate qualification afterward. Preserve compact failed evidence, '
    'clean owned output, and do not repeat completed capacity/compiler qualification or request another VM restart.')
programme['next_action'] = next_action
slice_ = programme['in_progress_slice']
slice_['state'] = ('DE-W105 remains unfinished. Guest source verification and x64 CMake configuration passed at '
    'their recorded revisions. Historical fcd7a4a5 passed178 x64 native groups; private Win32 and amended build-gate '
    'qualification remain incomplete. Fixture-generator worker support ownership is fixed with119 coordinator tests '
    '(one expected skip). Latest guest campaign failed on directory DACL editing before configure; all owned output '
    'was recovered/removed. No source integration, owner acceptance or full0.1.0 claim.')
slice_['guest_execution_preparation'] = ('Source transport verified931 files and clean Git revisions; '
    '3f18a287 x64 configure passed. f72b18ef latest source was verified, but its configure/Win32 build/tests did not '
    'run after a directory DACL refusal. All remaining source/image/context output removed. See '+PREFIX+'/README.md.')
slice_['guest_build_checkpoint'] = {'source_revision': source, 'status': 'partial',
    'evidence': PREFIX+'/README.md', 'native_win32_build_passed': False, 'native_win32_groups_passed': 0,
    'final_recipe_native_retest': False, 'qualification_directory_removed': True}
gate = programme['execution_environment_gate']
gate.update(status='guest_source_verified_configure_observed_product_qualification_pending',
    observed_at=final['observed_at'], guest_source_snapshot_qualified=True,
    guest_source_snapshot_evidence=PREFIX+'/eighth-directory-acl.json',
    guest_source_snapshot_scope='931 selected inputs and exact clean Git identity; not a product build',
    guest_cmake_configure_source_revision='3f18a2879d44b76179f9fdb63ea339aaf59604f9',
    guest_cmake_configure_evidence=PREFIX+'/seventh-probe-support.json',
    native_product_build_qualified=False)
programme['execution_environment']['guest_account_policy']['last_verification_evidence'] = PREFIX+'/account-check.json'
programme['execution_environment']['vm']['native_campaign_run'] = True
programme['execution_environment']['vm']['backing_file_bytes'] = final['vm_backing_bytes']
programme['execution_environment']['latest_guest_build_observation'] = PREFIX+'/final-observations.json'
write(programme_path, programme)

todo_path = ROOT / 'TODO.MD'
todo = todo_path.read_text()
todo = todo.replace('Actual guest product build and remaining DE-W105 Win32 tests are next.',
    'Guest source verification and pinned x64 configure passed at recorded revisions. A fixture tooling fix passed '
    '119 coordinator tests (one skip); actual guest product build and remaining DE-W105 Win32 tests remain incomplete '
    'after a directory-permission compatibility failure. All disposable campaign output is removed.')
anchor = '- [ ] Build and qualify DiskEd itself in the guest; compiler probes do not\n'
extra = ('- [x] Materialize and verify 931 exact guest source inputs; obtain a pinned\n'
    '  x64 CMake configure. Preserve failed attempts, correct worker support ownership\n'
    '  in the fixture generator and retain 119 coordinator tests (one expected skip).\n'
    '  [Partial checkpoint](.aide/evidence/2026-10-18-guest-build/README.md); this is not a native Win32 pass.\n')
if extra not in todo:
    assert anchor in todo
    todo = todo.replace(anchor, extra+anchor)
todo_path.write_text(todo, encoding='utf-8', newline='\n')

changed = subprocess.check_output(['git', 'diff', '--name-only'], cwd=ROOT, text=True).splitlines()
changed += [p.relative_to(ROOT).as_posix() for p in HERE.iterdir() if p.is_file()]
target = ROOT / '.aide/handoffs/2026-10-18-guest-build.json'
changed.append(target.relative_to(ROOT).as_posix())
tools = json.loads((HERE / 'coordinator-checks.json').read_bytes())
assert (tools['tests_run'], tools['failures'], tools['errors'], tools['skipped']) == (119, 0, 0, 1)
artifacts = sorted(p for p in HERE.iterdir() if p.is_file())
handoff = dict(schema='org.disked.handoff/1', work_id='DE-W105',
    base_revision='0eb038b575c2cc619e8bf86ff2227eb75706e365', spec_manifest_digest=sha(ROOT/'spec/manifest.json'),
    status='partial', files_read=['AGENTS.md', 'spec/START-HERE.md', 'spec/index.md', 'spec/work/units.json',
        'spec/catalog/ntfs-name-order-command-prototype.json', 'spec/schemas/handoff.schema.json',
        'CMakeLists.txt', 'tools/ntfs-win32-fixture.py', 'tools/source-snapshot.py', 'tools/workspace.py',
        'tools/windows-worker.py', 'docs/development-storage.md', '.aide/programmes/disked-0.1.0.json'],
    files_changed=sorted(set(changed)),
    summary=('Agents is routine; Codex remains an enabled administrator emergency spare with its original profile '
        'and requested password updated without logging into Codex or changing Jules. Guest verified931 clean '
        'selected source files. Pinned x64 configure passed at3f18a287; no private Win32 build/test passed. '
        'Canonical generator now preserves the existing two worker probes\' memory_budget.cpp support and rejects '
        'unexpected support, with119 coordinator tests/one skip. Exact export optionally binds immutable commit '
        'catalogs/blobs while preserving working edits. Latest f72b18ef guest attempt refused noncanonical DACL '
        'editing before configure; original report-capture failure and recovered native receipt retained. '
        'Attempt8 raw archive was unavailable; do not claim its surviving tails are complete raw logs. '
        'All images, source/inputs and contexts removed; final wrapper retirement/report fixes have host checks '
        'only. Shared backing size unchanged during these attempts; no compaction/reclamation, product acceptance '
        'or release claim. Dev synchronization was not yet performed when this receipt was created.'),
    tests=[dict(command='Full coordinator tools suite via managed validate-coordinator.py', cwd=str(ROOT),
                status='pass', exit_code=0, evidence_path=PREFIX+'/coordinator-checks.json'),
        dict(command='Current structural1323 checks,420-file manifest and source-bound context verification',
             cwd=str(ROOT), status='pass', exit_code=0, evidence_path=PREFIX+'/context.json'),
        dict(command='Guest campaign: exact source verified, DACL update refused before product configure',
             cwd='BlackGlass-HyperV', status='fail', exit_code=1, evidence_path=PREFIX+'/eighth-directory-acl.json'),
        dict(command='Host recipe syntax, Windows PowerShell parse and streaming archive/hash checks',
             cwd=str(ROOT), status='pass', exit_code=0, evidence_path=PREFIX+'/checkpoint-checks.json'),
        dict(command='Owned source/image/input recovery and final resource observation', cwd='BlackGlass-HyperV',
             status='pass', exit_code=0, evidence_path=PREFIX+'/final-observations.json'),
        dict(command='Private Win32 build/groups, current full x64 build-gate qualification and final wrapper native retest',
             cwd='BlackGlass-HyperV', status='not_run', exit_code=None, evidence_path=None)],
    artifacts=[dict(path=p.relative_to(ROOT).as_posix(), sha256=sha(p)) for p in artifacts],
    blockers=['Native Win32/product qualification remains incomplete after the retained guest recipe failures; '
        'this is a repairable implementation issue, not missing account/elevation authority.'],
    next_safe_step=next_action, performed_remote_writes=False)
jsonschema.Draft202012Validator(json.loads((ROOT/'spec/schemas/handoff.schema.json').read_bytes())).validate(handoff)
write(target, handoff)
print(json.dumps(dict(status='pass', coordinator_tests=119, expected_skips=1,
    guest_source_verified=True, product_build_qualified=False, handoff=target.relative_to(ROOT).as_posix())))
