"""Fixed-guest bounded source setup/retirement; never edits an existing checkout."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
SOURCE = ROOT / 'source'

# SetFileSecurity changes just the named directory. Do not replace it with a
# tree-propagating ACL setter for temporary ancestor read access.
ACL_PRELUDE = r'''
$ErrorActionPreference='Stop'
Add-Type -TypeDefinition 'using System;using System.Runtime.InteropServices;public static class DiskEdDirectoryAcl{[DllImport("advapi32.dll",CharSet=CharSet.Unicode,SetLastError=true)]public static extern bool SetFileSecurity(string path,uint info,byte[] descriptor);}'
function Edit-DiskEdDescriptor {
    param([byte[]]$Descriptor,[Security.Principal.SecurityIdentifier]$Sid,[bool]$Add)
    $raw=[Security.AccessControl.RawSecurityDescriptor]::new($Descriptor,0)
    if($null-eq$raw.DiscretionaryAcl -or $raw.DiscretionaryAcl.Count-gt4096){throw 'Missing or oversized DACL.'}
    $matches=@()
    for($i=0;$i-lt$raw.DiscretionaryAcl.Count;$i++){
        $ace=$raw.DiscretionaryAcl[$i]
        if($ace-is[Security.AccessControl.KnownAce] -and $ace.SecurityIdentifier-eq$Sid){$matches+=,$i}
    }
    if($Add){
        if($matches.Count){throw 'Fresh package already has a directory rule.'}
        $view=[Security.AccessControl.DirectorySecurity]::new()
        $view.SetSecurityDescriptorBinaryForm($Descriptor)
        $position=$raw.DiscretionaryAcl.Count
        if($view.AreAccessRulesCanonical){
            for($i=0;$i-lt$raw.DiscretionaryAcl.Count;$i++){
                if(([int]$raw.DiscretionaryAcl[$i].AceFlags-band16)-ne0){$position=$i;break}
            }
        }
        $ace=[Security.AccessControl.CommonAce]::new([Security.AccessControl.AceFlags]::None,
            [Security.AccessControl.AceQualifier]::AccessAllowed,0x1200a9,$Sid,$false,$null)
        $raw.DiscretionaryAcl.InsertAce($position,$ace)
    }elseif($matches.Count){
        if($matches.Count-ne1){throw 'Unexpected duplicate package rules.'}
        $ace=$raw.DiscretionaryAcl[$matches[0]]
        if($ace-isnot[Security.AccessControl.CommonAce] -or $ace.IsCallback -or
            $ace.AceQualifier-ne[Security.AccessControl.AceQualifier]::AccessAllowed -or
            $ace.AceFlags-ne[Security.AccessControl.AceFlags]::None -or $ace.AccessMask-ne0x1200a9){
            throw 'Package directory rule differs from the admitted read rule.'
        }
        $raw.DiscretionaryAcl.RemoveAce($matches[0])
    }
    $bytes=[byte[]]::new($raw.BinaryLength)
    $raw.GetBinaryForm($bytes,0)
    return ,$bytes
}
function Dacl-Bytes {
    param([byte[]]$Descriptor)
    $raw=[Security.AccessControl.RawSecurityDescriptor]::new($Descriptor,0)
    $bytes=[byte[]]::new($raw.DiscretionaryAcl.BinaryLength)
    $raw.DiscretionaryAcl.GetBinaryForm($bytes,0)
    return ,$bytes
}
'''


def directory_script(sid, paths, add):
    expected = [str(Path('C:/')), str(Path('C:/ProgramData')), str(Path('C:/ProgramData/DiskEd')), str(ROOT)]
    if not re.fullmatch(r'S-1-15-2-(?:[0-9]+-)*[0-9]+', sid) or paths != expected:
        raise RuntimeError('Unexpected package or directory access scope')
    literals = ','.join("'"+p.replace("'", "''")+"'" for p in paths)
    body = r'''
$sid=[Security.Principal.SecurityIdentifier]::new('SID_VALUE')
$add=ADD_VALUE
$owned=[IO.Path]::GetFullPath('OWNED_VALUE')
foreach($path in @(PATH_VALUES)){
    $path=[IO.Path]::GetFullPath($path)
    try{
        $acl=Get-Acl -LiteralPath $path
        $before=$acl.GetSecurityDescriptorBinaryForm()
        [pscustomobject]@{path=$path;phase='before';add=$add;canonical=$acl.AreAccessRulesCanonical;
            descriptor=[Convert]::ToBase64String($before)}|ConvertTo-Json -Compress
        if($add -and -not$acl.AreAccessRulesCanonical -and $path-ne$owned){throw 'Noncanonical shared ancestor; preserved.'}
        $after=Edit-DiskEdDescriptor $before $sid $add
        if([Convert]::ToBase64String((Dacl-Bytes $before))-ne[Convert]::ToBase64String((Dacl-Bytes $after))){
            if(-not[DiskEdDirectoryAcl]::SetFileSecurity($path,4,$after)){
                throw [ComponentModel.Win32Exception]::new([Runtime.InteropServices.Marshal]::GetLastWin32Error())
            }
        }
        $observed=(Get-Acl -LiteralPath $path).GetSecurityDescriptorBinaryForm()
        if([Convert]::ToBase64String((Dacl-Bytes $observed))-ne[Convert]::ToBase64String((Dacl-Bytes $after))){
            throw 'Directory DACL differs from the exact requested edit.'
        }
        [pscustomobject]@{path=$path;phase='after';add=$add;descriptor=[Convert]::ToBase64String($observed)}|ConvertTo-Json -Compress
    }catch{throw ('Directory access at '+$path+': '+$_.Exception.Message)}
}
'''
    return ACL_PRELUDE + body.replace('SID_VALUE', sid).replace('ADD_VALUE', '$true' if add else '$false').replace(
        'OWNED_VALUE', str(ROOT).replace("'", "''")).replace('PATH_VALUES', literals)


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
            script = directory_script(sid, paths, False)
            retired = subprocess.run([str(Path(os.environ['WINDIR']) / 'System32/WindowsPowerShell/v1.0/powershell.exe'),
                                      '-NoProfile', '-EncodedCommand', base64.b64encode(script.encode('utf-16-le')).decode('ascii')], capture_output=True, timeout=30)
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
