"""Bind the completed bootstrap evidence and create an honest partial handoff."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import jsonschema

root = Path(__file__).resolve().parents[3]
folder = Path(__file__).resolve().parent


def load(path):
    return json.loads(path.read_bytes())


def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()


checks = []
for name in ('proof-32.json', 'proof-512.json'):
    receipt = load(folder / name)
    if receipt['status'] != 'pass' or not receipt['guest']['setup']['image_removed']:
        raise RuntimeError('Incomplete proof or cleanup')
    for entry in receipt['sources']['files']:
        relative = entry['path']
        path = root / relative if relative.startswith('tools/') else folder / (
            'qualified-setup.ps1' if relative == 'guest-proof.ps1' else relative)
        if sha(path)[7:] != entry['sha256'].lower():
            raise RuntimeError('Qualification source mismatch: ' + relative)
    checks.append({'receipt': name, 'bound_sources_verified': len(receipt['sources']['files'])})
tools, specs = load(folder / 'tooling-checks.json'), load(folder / 'spec-checks.json')
if not tools['passed'] or specs['status'] != 'pass':
    raise RuntimeError('Repository validation did not pass')
record = {'status': 'pass', 'proofs': checks, 'tooling_run': tools['tests_run'],
          'tooling_skipped': tools['skipped'], 'specification_tests_run': specs['specification_tests_run'],
          'specification_tests_skipped': specs['specification_tests_skipped'],
          'native_product_tests_run': False, 'owner_accepted': False,
          'guest_retirement_guard_full_remote_test': 'not_run',
          'native_source_changed': False}
(folder / 'checkpoint.json').write_text(json.dumps(record, indent=2)+'\n', encoding='utf-8', newline='\n')
changed = subprocess.check_output(['git', 'diff', '--name-only'], cwd=root, text=True).splitlines()
changed += [p.relative_to(root).as_posix() for p in sorted(folder.iterdir()) if p.is_file()]
handoff_path = root / '.aide/handoffs/2026-10-18-guest-capacity.json'
changed.append(handoff_path.relative_to(root).as_posix())
evidence = ['python-runtime.json', 'proof-32.json', 'proof-512.json', 'qualified-setup.ps1',
            'retirement-guard.json', 'final-observations.json', 'cleanups.json',
            'observations.json.xz', 'observations-index.json', 'tooling-checks.json',
            'spec-checks.json', 'coordinator-observations.json.xz', 'context-cleanup.json',
            'checkpoint.json', 'README.md']
handoff = {
    'schema': 'org.disked.handoff/1', 'work_id': 'DE-W105',
    'base_revision': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    'spec_manifest_digest': sha(root / 'spec/manifest.json'), 'status': 'partial',
    'files_read': ['AGENTS.md', 'spec/START-HERE.md', 'spec/index.md', 'spec/work/units.json',
                   'spec/schemas/handoff.schema.json', '.aide/programmes/disked-0.1.0.json',
                   'tools/windows-worker.py', 'tools/workspace.py', 'tools/qualify-storage.py',
                   'tools/connect-vm.ps1', 'tests/tools/test_windows_worker.py',
                   'tests/tools/test_storage_setup.py', 'docs/development-storage.md',
                   '.aide/evidence/2026-10-18-guest-start/result.json'],
    'files_changed': sorted(set(changed)),
    'summary': 'Agents remains primary; Codex is the enabled administrator emergency spare with its original profile and owner-supplied password. No Codex login or guest Jules use. Installed no global software: a 37,630,185-byte project-owned portable Python copy passed verification. Guest 32/512 MiB fixed-filesystem allocation denial, outside/descendant/backing-write denial, non-elevated workers, job interruption and inner-controller death/profile recovery passed. Images, guest transfer/control copies and host managed work were removed. Early failures are compressed once with verified exact-byte recovery. Actual VM backing growth is recorded without claiming host-byte reclamation or attribution entirely to DiskEd. A later conservative retirement-guard repair passes pure cases; full remote-session interruption remains unverified. Native product sources are unchanged; guest compiler/build, DE-W105 Win32, owner acceptance and full 0.1.0 remain unfinished.',
    'tests': [
        {'command': 'python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-18-guest-capacity/validate-tools.py',
         'cwd': str(root), 'status': 'pass', 'exit_code': 0, 'evidence_path': str((folder / 'tooling-checks.json').relative_to(root).as_posix())},
        *[{'command': 'python -B tools/workspace.py run -- pwsh -NoProfile -File .aide/evidence/2026-10-18-guest-capacity/run-proof.ps1 -SizeMiB ' + size,
           'cwd': str(root), 'status': 'pass', 'exit_code': 0,
           'evidence_path': (folder / ('proof-' + size + '.json')).relative_to(root).as_posix()} for size in ('32', '512')],
        {'command': 'python -B tools/workspace.py run -- python -B .aide/evidence/2026-10-18-guest-capacity/validate-spec.py',
         'cwd': str(root), 'status': 'pass', 'exit_code': 0, 'evidence_path': (folder / 'spec-checks.json').relative_to(root).as_posix()},
        {'command': 'validate-retirement.ps1 pure guard; no disk operations',
         'cwd': str(root), 'status': 'pass', 'exit_code': 0, 'evidence_path': (folder / 'retirement-guard.json').relative_to(root).as_posix()},
        {'command': 'Native DE-W105 compiler/build/private Win32 qualification in the guest',
         'cwd': 'BlackGlass-HyperV', 'status': 'not_run', 'exit_code': None, 'evidence_path': None}],
    'artifacts': [{'path': (folder / name).relative_to(root).as_posix(), 'sha256': sha(folder / name)} for name in evidence],
    'blockers': ['Actual native compiler/build qualification and missing private Win32 tests are not yet run; no missing account or UAC approval is claimed.',
                 'Full remote-session interruption is not established by inner Python-controller death; preserve an image when worker retirement is uncertain.',
                 'Shared VM backing-file growth is real; deletion alone does not reclaim host allocation. Keep monitoring actual backing growth and free space.'],
    'next_safe_step': 'Continue the active goal with a bounded guest compiler/build campaign using the proven 512 MiB boundary and pinned C:\\BuildTools. Keep Agents primary/Codex spare, finite owned output and compact retention. Diagnose missing imports/read access or resource admission without rerunning unbounded historical recipes. Keep native and release claims unverified until actual results.',
    'performed_remote_writes': False}
jsonschema.Draft202012Validator(load(root / 'spec/schemas/handoff.schema.json')).validate(handoff)
handoff_path.write_text(json.dumps(handoff, indent=2)+'\n', encoding='utf-8', newline='\n')
print(json.dumps(record))
