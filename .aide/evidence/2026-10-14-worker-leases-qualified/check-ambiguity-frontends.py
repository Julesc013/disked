"""Supplement immutable-source qualification with actual ambiguous-media UI outcomes."""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

root = Path.cwd()
parser = argparse.ArgumentParser()
parser.add_argument('--campaign', type=Path, required=True)
args = parser.parse_args()
campaign = args.campaign.resolve()
source = campaign / 'source'
exe = campaign / 'build/Release/disked.exe'
console_fixture = Path(__file__).resolve().with_name('ambiguity-console-fixture.py')
assert console_fixture.is_file()
sys.path.insert(0, str(source / 'tests/frontend'))
sys.path.insert(0, str(source / 'tests/images'))
from gui_fixture import Gui, U, wait
from test_exfat_capture import Volume
from test_exfat_file import write, file_digest
from test_exfat_upcase import mapping

def sha(path):
    return 'sha256:' + hashlib.sha256(path.read_bytes()).hexdigest()

revision = subprocess.check_output(['git', '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip()
identity = json.loads((campaign / 'build/generated/build-identity.json').read_bytes())
assert identity['identity']['source_revision'] == revision
assert identity['identity']['source_state'] == 'clean'
assert not subprocess.check_output(['git', '-C', str(source), 'status', '--porcelain']).strip()
before_exe = sha(exe)
records = []
passed = False
try:
    with tempfile.TemporaryDirectory(prefix='disked-exfat-ambiguous-ui-') as temporary:
        folder = Path(temporary).resolve()
        table = mapping(); table[128:130] = [65535, 2]
        volume = Volume(compressed=False, table=table, offset=173)
        path = folder / 'generated.img'; write(volume, path)
        before_file = file_digest(path)
        options = ['--view', 'exfat', '--volume-offset', str(volume.offset), '--volume-bytes', str(volume.length)]
        baseline = subprocess.run([str(exe), '--json', 'image', 'inspect', str(path), *options],
                                  capture_output=True, timeout=20)
        assert baseline.returncode == 4 and not baseline.stderr
        expected = json.loads(baseline.stdout)
        def validate(value):
            assert value['status'] == expected['status'] == 'failed'
            assert value['diagnostics'] == expected['diagnostics']
            result = value['result']; observation = result['observation']
            assert not observation['applicable'] and not result['authorizes_effects']
            assert observation['upcase']['selection'] == 'ambiguous'
            assert 'mapping_sha256' not in observation['upcase']
            assert observation['upcase']['candidates'] == expected['result']['observation']['upcase']['candidates']
            assert result['worker']['worker']['observation'] == 'exited'
        validate(expected)
        records.append(dict(frontend='cli', command=baseline.args, exit_code=4,
                            response_sha256='sha256:' + hashlib.sha256(baseline.stdout).hexdigest()))
        gui = Gui(exe, ['--gui', 'image', 'inspect', str(path), *options], render=True)
        try:
            assert not U.IsWindowEnabled(gui.child(110))
            gui.click(109); assert gui.details()['reviewed'] and 'status' not in gui.details()
            gui.click(110)
            actual = wait(lambda: gui.details() if 'status' in gui.details() else None)
            validate(actual)
            records.append(dict(frontend='gui', response=actual, native=gui.observation()))
        finally: gui.close()
        assert gui.code == 0 and not gui.created_files
        for frontend in ['tui', 'shell']:
            report = folder / (frontend + '.json')
            startup = subprocess.STARTUPINFO(); startup.dwFlags = subprocess.STARTF_USESHOWWINDOW; startup.wShowWindow = 0
            command = [sys.executable, str(console_fixture),
                str(exe), frontend, 'image.inspect', str(path), '-', str(report), json.dumps(options)]
            result = subprocess.run(command, cwd=folder, creationflags=subprocess.CREATE_NEW_CONSOLE,
                                    startupinfo=startup, timeout=35, env=dict(os.environ, PYTHONPATH=str(source / 'tests/frontend')))
            observation = json.loads(report.read_bytes())
            assert result.returncode == 0, observation
            validate(observation['response'])
            assert all(observation['restored'].values())
            records.append(dict(frontend=frontend, command=command, observation=observation))
            report.unlink()
        assert set(p.name for p in folder.iterdir()) == {'generated.img'}
        assert file_digest(path) == before_file
    assert sha(exe) == before_exe
    passed = True
finally:
    (campaign / 'exfat-ambiguity-frontends.json').write_text(json.dumps(dict(passed=passed,
        source_revision=revision, artifact_sha256=before_exe,
        cases=len(records), records=records), indent=2) + '\n', encoding='utf-8', newline='\n')
print('Ambiguous exFAT outcomes agree in CLI/GUI/TUI/shell; source and host state preserved')
