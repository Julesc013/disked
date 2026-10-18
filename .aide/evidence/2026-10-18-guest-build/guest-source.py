"""Fixed-guest bounded source setup/retirement; never edits an existing checkout."""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'


def load(name, path):
    definition = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(definition)
    definition.loader.exec_module(module)
    return module


def main():
    if os.name != 'nt' or ROOT != Path('C:/ProgramData/DiskEd/qualification') or sys.argv[1:] not in (['prepare'], ['retire']):
        raise RuntimeError('Fixed guest source setup/retirement only')
    snapshot = load('snapshot', ROOT / 'source-snapshot.py')
    manifest = json.loads((ROOT / 'source.json').read_bytes())
    nonce = json.loads((ROOT / 'scratch/owner.json').read_bytes())['nonce']
    owner = ROOT / 'source-owner.json'
    if sys.argv[1] == 'prepare':
        if SOURCE.exists() or owner.exists():
            raise RuntimeError('Existing source state requires review')
        owner.write_text(json.dumps({'nonce': nonce, 'source': str(SOURCE), 'revision': manifest['revision'],
                                    'phase': 'preparing'})+'\n')
        result = snapshot.materialize(ROOT / 'source.pack', manifest, SOURCE, 'C:/Program Files/Git/cmd/git.exe')
        owner.write_text(json.dumps({'nonce': nonce, 'source': str(SOURCE), 'revision': manifest['revision'],
                                    'phase': 'verified'})+'\n')
        (ROOT / 'source-prepared.json').write_text(json.dumps(result, indent=2)+'\n', encoding='utf-8', newline='\n')
    else:
        state = json.loads(owner.read_bytes())
        if state['nonce'] != nonce or Path(state['source']) != SOURCE or state['revision'] != manifest['revision']:
            raise RuntimeError('Source ownership changed; preserve it')
        scoped = ROOT / 'scoped-directory-access.json'
        if scoped.exists():
            grant = json.loads(scoped.read_bytes())
            disk = json.loads((ROOT / 'scratch/state.json').read_bytes())
            paths = [str(Path('C:/')), str(Path('C:/ProgramData')), str(Path('C:/ProgramData/DiskEd')), str(ROOT)]
            if grant['nonce'] != nonce or grant['sid'] != disk['profile_sids'][0] or grant['paths'] != paths:
                raise RuntimeError('Scoped directory grant ownership changed')
            sid = grant['sid']
            literal_paths = ','.join("'"+p.replace("'", "''")+"'" for p in paths)
            api = "Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public static class DiskEdDirectoryAcl{[DllImport(\"advapi32.dll\",CharSet=CharSet.Unicode,SetLastError=true)]public static extern bool SetFileSecurity(string path,uint info,byte[] descriptor);}';"
            script = "$ErrorActionPreference='Stop';"+api+"$sid=[Security.Principal.SecurityIdentifier]::new('"+sid+"');$rule=[Security.AccessControl.FileSystemAccessRule]::new($sid,[Security.AccessControl.FileSystemRights]::ReadAndExecute,[Security.AccessControl.InheritanceFlags]::None,[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow);foreach($path in @("+literal_paths+")){$path=[IO.Path]::GetFullPath($path);$acl=Get-Acl -LiteralPath $path;if(-not @($acl.Access|Where-Object{$_.IdentityReference.Value-eq$sid.Value}).Count){continue};$acl.RemoveAccessRuleSpecific($rule);if(-not[DiskEdDirectoryAcl]::SetFileSecurity($path,4,$acl.GetSecurityDescriptorBinaryForm())){throw [ComponentModel.Win32Exception]::new([Runtime.InteropServices.Marshal]::GetLastWin32Error())}}"
            retired = subprocess.run([str(Path(os.environ['WINDIR']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
                                      '-NoProfile', '-Command', script], capture_output=True, timeout=30)
            if retired.returncode:
                raise RuntimeError('Scoped directory access retirement failed')
            grant['phase'] = 'retired'
            scoped.write_text(json.dumps(grant)+'\n', encoding='utf-8', newline='\n')
        snapshot.plain_ancestors(SOURCE)
        if state['phase'] == 'verified':
            for entry in manifest['files']:
                path = SOURCE / entry['path']
                snapshot.plain_ancestors(path)
                if hashlib.sha256(path.read_bytes()).hexdigest() != entry['sha256']:
                    raise RuntimeError('Source bytes changed; preserve the checkout')
            result = subprocess.run(['C:/Program Files/Git/cmd/git.exe', '-C', str(SOURCE), 'status', '--porcelain'],
                                    capture_output=True, env=dict(os.environ, GIT_OPTIONAL_LOCKS='0'), timeout=30)
            if result.returncode or result.stdout:
                raise RuntimeError('Source is not clean; preserve it')
        runner = load('source_workspace', ROOT / 'tools/workspace.py')
        if runner.tree_bytes(SOURCE, allocated=True, file_limit=20000, allow_links=False) > 96 * 1024 * 1024:
            raise RuntimeError('Unexpected source footprint; preserve it')
        # Exact newly owned temporary source; this existing cleanup checks
        # containment, refuses reparses and never changes shared hard-link attrs.
        runner.remove_owned_work(SOURCE, ROOT, 'source')
        (ROOT / 'source-retired.json').write_text(json.dumps({'status': 'pass', 'source_removed': not SOURCE.exists(),
                                                            'nonce': nonce})+'\n', encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
