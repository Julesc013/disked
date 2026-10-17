"""Exercise cleanup only in tiny synthetic repositories owned by this test."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'tools/clean-scratch.ps1'
SHELL = shutil.which('pwsh') or shutil.which('powershell')


@unittest.skipUnless(os.name == 'nt' and SHELL and shutil.which('git'),
                     'Windows PowerShell and Git required')
class ScratchCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='disked-cleanup-test-')
        self.root = Path(self.temp.name).resolve()
        (self.root / 'tools').mkdir()
        self.script = self.root / 'tools/clean-scratch.ps1'
        shutil.copyfile(SCRIPT, self.script)
        self.git('init', '--quiet')
        (self.root / 'keep.txt').write_text('source sentinel', encoding='utf-8')
        self.git('add', 'keep.txt')
        self.git('-c', 'user.name=Cleanup Test', '-c', 'user.email=test@example.invalid',
                 'commit', '--quiet', '-m', 'fixture')
        self.scratch = self.root / '.aide-local'
        self.scratch.mkdir()

    def tearDown(self):
        self.temp.cleanup()

    def git(self, *args):
        return subprocess.run(['git', '-C', str(self.root), *args], check=True,
                              capture_output=True, text=True)

    def run_script(self, *args, shell=SHELL):
        return subprocess.run([shell, '-NoProfile', '-NonInteractive', '-File',
                               str(self.script), *args], cwd=self.root,
                              capture_output=True, text=True, timeout=30)

    def test_inspection_changes_nothing_then_opt_in_removes_only_scratch(self):
        nested = self.scratch / 'build'
        nested.mkdir()
        scratch = nested / 'object.bin'
        scratch.write_bytes(b'x' * 1024)
        before = self.git('rev-parse', 'HEAD').stdout
        p = self.run_script()
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertEqual(json.loads(p.stdout)['EligibleFiles'], 1)
        self.assertTrue(scratch.exists())
        p = self.run_script('-Delete', '-WorkersStopped')
        self.assertEqual(p.returncode, 0, p.stderr)
        report = json.loads(p.stdout)
        self.assertEqual(report['LogicalBytes'], 1024)
        self.assertFalse(nested.exists())
        self.assertEqual((self.root / 'keep.txt').read_text(), 'source sentinel')
        self.assertEqual(self.git('rev-parse', 'HEAD').stdout, before)

    def test_deletion_without_stopped_workers_is_refused(self):
        sentinel = self.scratch / 'keep.bin'
        sentinel.write_bytes(b'keep')
        p = self.run_script('-Delete')
        self.assertEqual(p.returncode, 1)
        self.assertEqual(sentinel.read_bytes(), b'keep')

    def test_tracked_scratch_refuses_before_any_deletion(self):
        sentinel = self.scratch / 'tracked.txt'
        sentinel.write_text('tracked')
        self.git('add', '-f', '.aide-local/tracked.txt')
        p = self.run_script('-Delete', '-WorkersStopped')
        self.assertEqual(p.returncode, 1)
        self.assertTrue(sentinel.exists())

    def test_nested_checkout_and_bare_repository_are_preserved(self):
        nested = self.scratch / 'checkout'
        subprocess.run(['git', 'init', '--quiet', str(nested)], check=True)
        dirty = nested / 'uncommitted.txt'
        dirty.write_text('uncommitted source')
        bare = self.scratch / 'bare.git'
        subprocess.run(['git', 'init', '--quiet', '--bare', str(bare)], check=True)
        (self.scratch / 'ordinary.tmp').write_bytes(b'removable')
        p = self.run_script('-Delete', '-WorkersStopped')
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertEqual(json.loads(p.stdout)['SkippedEntries'], 2)
        self.assertEqual(dirty.read_text(), 'uncommitted source')
        self.assertTrue((bare / 'HEAD').exists())
        self.assertFalse((self.scratch / 'ordinary.tmp').exists())

    def test_registered_worktree_survives_missing_git_marker(self):
        checkout = self.scratch / 'checkout'
        self.git('worktree', 'add', '--quiet', '--detach', str(checkout), 'HEAD')
        (checkout / '.git').unlink()
        p = self.run_script('-Delete', '-WorkersStopped')
        self.assertEqual(p.returncode, 2, p.stderr)
        self.assertIn('registered worktree', p.stdout)
        self.assertEqual((checkout / 'keep.txt').read_text(), 'source sentinel')

    def test_junction_is_never_followed_or_removed(self):
        outside = self.root / 'other-project'
        outside.mkdir()
        sentinel = outside / 'keep.txt'
        sentinel.write_text('other project')
        link = self.scratch / 'redirect'
        p = subprocess.run(['cmd.exe', '/d', '/c', 'mklink', '/J', str(link), str(outside)],
                           capture_output=True, text=True)
        self.assertEqual(p.returncode, 0, p.stderr)
        try:
            p = self.run_script('-Delete', '-WorkersStopped')
            self.assertEqual(p.returncode, 2, p.stderr)
            self.assertEqual(sentinel.read_text(), 'other project')
            self.assertTrue(link.exists())
        finally:
            link.rmdir()  # Unlink only; never recursively traverse its target.

    def test_readonly_file_produces_partial_result_without_attribute_changes(self):
        sentinel = self.scratch / 'readonly.txt'
        sentinel.write_text('readonly')
        sentinel.chmod(0o444)
        try:
            before = sentinel.stat().st_file_attributes
            p = self.run_script('-Delete', '-WorkersStopped')
            self.assertEqual(p.returncode, 2, p.stderr)
            self.assertEqual(sentinel.stat().st_file_attributes, before)
        finally:
            sentinel.chmod(0o666)

    def test_windows_powershell_51_compatibility(self):
        shell = shutil.which('powershell.exe')
        if not shell:
            self.skipTest('Windows PowerShell unavailable')
        p = self.run_script(shell=shell)
        if (p.returncode != 0 and 'UnauthorizedAccess' in p.stderr
                and 'running scripts is disabled on this system' in p.stderr):
            self.skipTest('Host execution policy blocks Windows PowerShell scripts; 5.1 runtime unverified')
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertEqual(json.loads(p.stdout)['Mode'], 'inspect')

    def test_windows_powershell_51_parser(self):
        shell = shutil.which('powershell.exe')
        if not shell:
            self.skipTest('Windows PowerShell unavailable')
        quoted = "'" + str(self.script).replace("'", "''") + "'"
        command = ('$errors=$null;$tokens=$null;'
                   '[System.Management.Automation.Language.Parser]::ParseFile('
                   + quoted + ',[ref]$tokens,[ref]$errors)|Out-Null;'
                   'if($errors.Count){$errors|Out-String|Write-Error;exit 1};'
                   '$PSVersionTable.PSVersion.ToString()')
        # Parse only. Do not change or bypass the host's script execution policy.
        p = subprocess.run([shell, '-NoProfile', '-NonInteractive', '-Command', command],
                           capture_output=True, text=True, timeout=30)
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertTrue(p.stdout.strip().startswith('5.1.'), p.stdout)


if __name__ == '__main__':
    unittest.main()
