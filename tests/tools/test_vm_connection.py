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

    @unittest.skipUnless(os.name == 'nt', 'Windows DPAPI credential persistence')
    def test_supplied_agents_is_saved_only_after_guest_and_account_verification(self):
        identity = self.run_ps('[Security.Principal.WindowsIdentity]::GetCurrent().Name')
        if identity.stdout.strip().lower() != r'blackglass-win1\jules':
            self.skipTest('Fixed helper requires the approved Jules host identity')
        for case in ('verified', 'verified_qualified', 'wrong_guest', 'guest_jules', 'guest_codex', 'wrong_domain'):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix='disked-vm-save-') as directory:
                env = dict(os.environ, LOCALAPPDATA=directory)
                path = str(HELPER).replace("'", "''")
                dns = 'wrong-guest' if case == 'wrong_guest' else 'BlackGlass-HyperV'
                user = {'guest_jules': 'Jules', 'guest_codex': 'Codex'}.get(case, 'Agents')
                domain = 'OTHER' if case == 'wrong_domain' else 'BLACKGLASS-HYPE'
                supplied = r'BLACKGLASS-HYPE\Agents' if case == 'verified_qualified' else 'Agents'
                command = (
                    "$ErrorActionPreference='Stop'; $global:diskedMockClosed=$false; "
                    "function Get-Credential { throw 'UNEXPECTED_PROMPT' }; "
                    "function Get-VM { [pscustomobject]@{Name='Windows 10';State='Running'} }; "
                    "function New-PSSession { param($VMId,$Credential); "
                    "if ([string]$VMId -ne '3ebbe558-91b9-435b-96e4-0c8199bd38ad' -or "
                    f"$Credential.UserName -ne '{supplied}') {{ throw 'WRONG_CONNECTION' }}; 'mock-session' }}; "
                    "function Invoke-Command { [pscustomobject]@{computer='BLACKGLASS-HYPE';"
                    f"dns_name='{dns}';model='Virtual Machine';identity='{domain}\\{user}';"
                    "elevated=$true;os_version='10.0.19045'} }; "
                    "function Remove-PSSession { $global:diskedMockClosed=$true }; "
                    f"$value=[Management.Automation.PSCredential]::new('{supplied}',"
                    "(ConvertTo-SecureString 'fixture-only' -AsPlainText -Force)); "
                    f"try {{ & '{path}' -SetupCredential -GuestCredential $value | Out-Null; "
                    "$outcome='verified' } catch { $outcome=$_.Exception.Message }; "
                    "[pscustomobject]@{outcome=$outcome;closed=$global:diskedMockClosed} | ConvertTo-Json -Compress")
                result = self.run_ps(command, env)
                self.assertEqual(result.returncode, 0, result.stderr)
                observed = json.loads(result.stdout.strip().splitlines()[-1])
                self.assertTrue(observed['closed'], observed)
                credential = Path(directory) / 'DiskEd/credentials/vm-3ebbe558-91b9-435b-96e4-0c8199bd38ad.xml'
                if case.startswith('verified'):
                    self.assertEqual(observed['outcome'], 'verified')
                    self.assertTrue(credential.is_file())
                    self.assertNotIn(b'fixture-only', credential.read_bytes())
                else:
                    self.assertIn('Unexpected guest identity', observed['outcome'])
                    self.assertFalse(credential.exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows credential path check')
    def test_invalid_local_inputs_never_authenticate_or_prompt(self):
        # Mock the connection boundary to fail the test if a refusal reaches it.
        # Only ordinary temporary metadata is written; no real credential read.
        identity = self.run_ps('[Security.Principal.WindowsIdentity]::GetCurrent().Name')
        if identity.stdout.strip().lower() != r'blackglass-win1\jules':
            self.skipTest('Fixed helper requires the approved Jules host identity')
        for case in ('missing', 'oversized', 'wrong_type', 'existing_setup',
                     'blank', 'jules', 'codex', 'supplied_blank', 'supplied_jules', 'supplied_codex'):
            with self.subTest(case=case), tempfile.TemporaryDirectory(prefix='disked-vm-refusal-') as directory:
                credential = Path(directory) / 'DiskEd/credentials/vm-3ebbe558-91b9-435b-96e4-0c8199bd38ad.xml'
                if case not in ('missing', 'supplied_blank', 'supplied_jules', 'supplied_codex'):
                    credential.parent.mkdir(parents=True)
                    if case in ('blank', 'jules', 'codex'):
                        value = "[Security.SecureString]::new()" if case == 'blank' else "(ConvertTo-SecureString 'fixture-only' -AsPlainText -Force)"
                        user = 'Jules' if case == 'jules' else 'Codex'
                        saved = self.run_ps(
                            f"[Management.Automation.PSCredential]::new('{user}',{value}) | "
                            f"Export-Clixml -LiteralPath '{str(credential).replace(chr(39), chr(39)*2)}'")
                        self.assertEqual(saved.returncode, 0, saved.stderr)
                    else:
                        credential.write_text('x' * 65537 if case == 'oversized' else
                                              '<Objs Version="1.1.0.1" xmlns="http://schemas.microsoft.com/powershell/2004/04"><S>not a credential</S></Objs>',
                                              encoding='utf-8')
                env = dict(os.environ, LOCALAPPDATA=directory)
                before = credential.read_bytes() if credential.exists() else None
                path = str(HELPER).replace("'", "''")
                expected = {'missing': 'Guest credential not configured',
                            'oversized': 'Oversized guest credential file',
                            'wrong_type': 'Invalid guest credential file',
                            'existing_setup': 'A guest credential already exists',
                            'blank': 'requires a nonempty password',
                            'jules': 'Only the guest Agents',
                            'codex': 'Only the guest Agents',
                            'supplied_blank': 'requires a nonempty password',
                            'supplied_jules': 'Only the guest Agents',
                            'supplied_codex': 'Only the guest Agents'}[case]
                setup = ' -SetupCredential' if case == 'existing_setup' else ''
                if case.startswith('supplied_'):
                    value = "[Security.SecureString]::new()" if case == 'supplied_blank' else "(ConvertTo-SecureString 'fixture-only' -AsPlainText -Force)"
                    user = {'supplied_jules': 'Jules', 'supplied_codex': 'Codex'}.get(case, 'Agents')
                    setup = f" -SetupCredential -GuestCredential ([Management.Automation.PSCredential]::new('{user}',{value}))"
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
                if case in ('missing', 'supplied_blank', 'supplied_jules', 'supplied_codex'):
                    self.assertFalse(credential.exists())
                else:
                    self.assertEqual(credential.read_bytes(), before)


if __name__ == '__main__':
    unittest.main()
