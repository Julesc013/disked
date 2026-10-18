"""Guest-credential refusal checks: never prompt, authenticate or change a VM."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / 'tools/connect-vm.ps1'
PWSH = shutil.which('pwsh')


@unittest.skipUnless(PWSH, 'PowerShell 7 not available')
class VmConnectionTests(unittest.TestCase):
    def run_ps(self, command, env=None):
        return subprocess.run([PWSH, '-NoProfile', '-NonInteractive', '-Command', command],
                              env=env, capture_output=True, text=True, timeout=20)

    def test_script_parses(self):
        path = str(HELPER).replace("'", "''")
        command = (
            "$tokens=$null; $errors=$null; "
            f"[Management.Automation.Language.Parser]::ParseFile('{path}',"
            '[ref]$tokens,[ref]$errors) | Out-Null; '
            'if ($errors.Count) { throw ($errors | Out-String) }')
        result = self.run_ps(command)
        self.assertEqual(result.returncode, 0, result.stderr)

    @unittest.skipUnless(os.name == 'nt', 'Windows credential path check')
    def test_invalid_local_inputs_never_authenticate_or_prompt(self):
        # Mock the connection boundary to fail the test if a refusal reaches it.
        # Only ordinary temporary metadata is written; no real credential read.
        identity = self.run_ps('[Security.Principal.WindowsIdentity]::GetCurrent().Name')
        if identity.stdout.strip().lower() != r'blackglass-win1\jules':
            self.skipTest('Fixed helper requires the approved Jules host identity')
        for case in ('missing', 'oversized', 'wrong_type', 'existing_setup'):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix='disked-vm-refusal-') as directory:
                credential = Path(directory) / 'DiskEd/credentials/vm-3ebbe558-91b9-435b-96e4-0c8199bd38ad.xml'
                if case != 'missing':
                    credential.parent.mkdir(parents=True)
                    credential.write_text('x' * 65537 if case == 'oversized' else
                                          '<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><S>not a credential</S></Objs>',
                                          encoding='utf-8')
                env = dict(os.environ, LOCALAPPDATA=directory)
                before = credential.read_bytes() if credential.exists() else None
                path = str(HELPER).replace("'", "''")
                expected = {'missing': 'Guest credential not configured',
                            'oversized': 'Oversized guest credential file',
                            'wrong_type': 'Invalid guest credential file',
                            'existing_setup': 'A guest credential already exists'}[case]
                setup = ' -SetupCredential' if case == 'existing_setup' else ''
                command = (
                    "$ErrorActionPreference='Stop'; "
                    "function Get-Credential { throw 'UNEXPECTED_PROMPT' }; "
                    "function New-PSSession { throw 'UNEXPECTED_AUTHENTICATION' }; "
                    "function Get-VM { throw 'UNEXPECTED_VM_QUERY' }; "
                    f"try {{ & '{path}'{setup}; throw 'UNEXPECTED_SUCCESS' }} "
                    "catch { $_.Exception.Message | ConvertTo-Json -Compress }")
                result = self.run_ps(command, env)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(expected, json.loads(result.stdout))
                if case == 'missing':
                    self.assertFalse(credential.exists())
                else:
                    self.assertEqual(credential.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
