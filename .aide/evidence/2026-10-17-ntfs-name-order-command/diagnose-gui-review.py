"""Observe the existing GUI review gate using unchanged source and binary."""
import hashlib
import json
from pathlib import Path
import sys
import tempfile

root = Path.cwd().resolve()
sys.path[:0] = [str(root / 'tests/frontend'), str(root / 'tests/images')]
import ntfs_name_order_command_expectations as E
import test_ntfs_file as held
from gui_fixture import Gui, U, wait

ev = root / '.aide/evidence/2026-10-17-ntfs-name-order-command'
out = ev / 'gui-review-diagnostic'
out.mkdir()
exe = root / '.aide-local/report-phases-build/Release/disked.exe'
sha = lambda p: 'sha256:' + hashlib.sha256(p.read_bytes()).hexdigest()
failure = json.loads((ev / 'failed-working-gui/summary.json').read_bytes())
assert sha(exe) == failure['artifacts']['disked']
assert all(sha(root / p) == h for p, h in failure['sources'].items())
temp = tempfile.TemporaryDirectory(prefix='disked-name-order-gui-diagnostic-', dir=root / '.aide-local')
folder = Path(temp.name).resolve()
assert folder.parent == root / '.aide-local' and folder.name.startswith('disked-name-order-gui-diagnostic-')
events, ui = [], None
summary = dict(status='running', executable_sha256=sha(exe), production_source_and_binary_unchanged=True,
               qualification=False, native_wait_seconds=8, owner_accepted=False)


def save(name, value):
    (out / name).write_text(json.dumps(value, indent=2) + '\n', encoding='utf-8', newline='\n')


def observe(stage):
    raw = ui.text(101).encode('utf-8')
    p = out / ('details-' + str(len(events)) + '.txt')
    p.write_bytes(raw)
    event = dict(stage=stage, details=p.name, sha256=sha(p), summary=ui.text(102), notice=ui.text(103),
                 review_enabled=bool(U.IsWindowEnabled(ui.child(109))),
                 submit_enabled=bool(U.IsWindowEnabled(ui.child(110))), process_id=ui.process.pid)
    events.append(event)
    save('events.json', events)
    return json.loads(raw)


try:
    v = E.JointVolume(minor=1)
    owner = type('OwnedFixture', (), {})()
    owner.root, owner.index = folder, 0
    owner.skipTest = lambda reason: (_ for _ in ()).throw(AssertionError(reason))
    path = held.Tests.fixture(owner, v, 'generated.img')[1]
    before = held.file_digest(path)
    ui = Gui(exe, ['--gui', 'image', 'inspect', str(path), *E.options(v, reference=v.input['directory']['reference'])], render=True)
    initial = observe('initial-unreviewed')
    ui.click(110)
    inert = observe('submit-before-review')
    assert not initial['reviewed'] and not inert['reviewed'] and 'status' not in inert
    ui.click(109)
    reviewed = observe('explicit-review')
    assert reviewed['reviewed'] and 'status' not in reviewed
    ui.click(110)
    result = wait(lambda: ui.details() if 'status' in ui.details() else None)
    observe('explicit-submit-result')
    assert result['status'] == 'completed' and result['result']['scope'] == 'ordinary-local-file-ntfs-name-order'
    assert not result['result']['authorizes_effects']
    assert before == held.file_digest(path)
    summary.update(status='pass', source_before_sha256=before, source_after_sha256=held.file_digest(path),
                   cause='The failed harness submitted without Review. The existing GUI correctly left it inert. Explicit Review then Submit produced the expected result under the unchanged8-second observation wait.')
except BaseException as error:
    summary.update(status='fail', error=repr(error))
    if ui is not None:
        observe('exception-before-close')
    raise
finally:
    if ui is not None:
        ui.close()
        summary.update(parent_exit_code=ui.code, created_files=ui.created_files,
                       stderr_hex=ui.error.hex())
    save('summary.json', summary)
    assert folder.parent == root / '.aide-local' and folder.name.startswith('disked-name-order-gui-diagnostic-')
    temp.cleanup()
print(json.dumps(summary), flush=True)
