"""Pure ACL edit checks: no file-security API call, guest or product process."""
import base64
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess

HERE = Path(__file__).resolve().parent
definition = importlib.util.spec_from_file_location('guest_setup', HERE/'guest-source.py')
setup = importlib.util.module_from_spec(definition)
definition.loader.exec_module(setup)
test = r'''
$sid=[Security.Principal.SecurityIdentifier]::new('S-1-15-2-111-222-333-444-555-666-777')
$count=0
function Assert-Check {param([bool]$Value);if(-not$Value){throw 'ACL regression assertion failed.'};$script:count++}
function Bytes {param($Value);$b=[byte[]]::new($Value.BinaryLength);$Value.GetBinaryForm($b,0);return ,$b}
$cases=@('O:SYG:SYD:(D;;FW;;;WD)(A;;FA;;;SY)(A;ID;FR;;;BU)',
         'O:SYG:SYD:(A;ID;FR;;;BU)(D;;FW;;;WD)(A;;FA;;;SY)')
foreach($sddl in $cases){
    $original=Bytes ([Security.AccessControl.RawSecurityDescriptor]::new($sddl))
    $added=Edit-DiskEdDescriptor $original $sid $true
    $restored=Edit-DiskEdDescriptor $added $sid $false
    Assert-Check ([Convert]::ToBase64String($original)-eq[Convert]::ToBase64String($restored))
    $missing=Edit-DiskEdDescriptor $original $sid $false
    Assert-Check ([Convert]::ToBase64String($original)-eq[Convert]::ToBase64String($missing))
    $duplicate=$false;try{$null=Edit-DiskEdDescriptor $added $sid $true}catch{$duplicate=$_.Exception.Message-eq'Fresh package already has a directory rule.'}
    Assert-Check $duplicate
    $raw=[Security.AccessControl.RawSecurityDescriptor]::new($added,0)
    $found=@($raw.DiscretionaryAcl|Where-Object{$_-is[Security.AccessControl.KnownAce]-and$_.SecurityIdentifier-eq$sid})
    Assert-Check ($found.Count-eq1-and$found[0].AceFlags-eq[Security.AccessControl.AceFlags]::None-and$found[0].AccessMask-eq0x1200a9)
    $bad=[Security.AccessControl.RawSecurityDescriptor]::new($original,0)
    $bad.DiscretionaryAcl.InsertAce(0,[Security.AccessControl.CommonAce]::new([Security.AccessControl.AceFlags]::None,[Security.AccessControl.AceQualifier]::AccessDenied,0x1200a9,$sid,$false,$null))
    $denied=$false;try{$null=Edit-DiskEdDescriptor (Bytes $bad) $sid $false}catch{$denied=$_.Exception.Message-eq'Package directory rule differs from the admitted read rule.'}
    Assert-Check $denied
}
[pscustomobject]@{status='pass';cases=$cases.Count;assertions=$count;filesystem_security_api_called=$false}|ConvertTo-Json -Compress
'''
script = setup.ACL_PRELUDE + test
process = subprocess.run([str(Path(os.environ['WINDIR'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),
    '-NoProfile','-EncodedCommand',base64.b64encode(script.encode('utf-16-le')).decode('ascii')],
    capture_output=True, timeout=30)
record = dict(status='pass' if process.returncode == 0 else 'fail', exit_code=process.returncode,
    scope='Unprivileged host memory-only descriptor editing; no filesystem-security API, guest or product execution',
    stdout=process.stdout.decode(errors='replace')[-16384:],stderr=process.stderr.decode(errors='replace')[-16384:],
    source_sha256=hashlib.sha256((HERE/'guest-source.py').read_bytes()).hexdigest())
(HERE/'directory-validation.json').write_text(json.dumps(record,indent=2)+'\n',encoding='utf-8',newline='\n')
print(json.dumps(record))
raise SystemExit(process.returncode)
