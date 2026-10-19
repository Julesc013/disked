"""Adapt the qualified guest cap setup for the ordinary-token experiment."""
import ast
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import traceback

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
PRIOR=HERE.parent/'2026-10-18-guest-capacity'

def once(text, before, after):
    if text.count(before)!=1:raise ValueError('Template identity changed: '+before[:90])
    return text.replace(before,after,1)

CREATE_ACTOR=r'''
    $actorName='DiskEdTest-'+$nonce.Substring(0,8)
    $actorDescription='DiskEd test '+$nonce
    if(Get-LocalUser -Name $actorName -ErrorAction SilentlyContinue){throw 'Disposable actor already exists; no adoption.'}
    $actorJournal=Join-Path $scratch 'ordinary-actor.json'
    $actorState=@{phase='creating';name=$actorName;nonce=$nonce;description=$actorDescription}
    [IO.File]::WriteAllText($actorJournal,($actorState|ConvertTo-Json))
    if(-not$ActorPassword-or$ActorPassword.Length-eq0){throw 'Owner-supplied guest test credential required.'}
    $actorSecure=$ActorPassword
    $actorSecret=([Management.Automation.PSCredential]::new($actorName,$actorSecure)).GetNetworkCredential().Password
    $newActor=New-LocalUser -Name $actorName -Password $actorSecure -Description $actorDescription -PasswordNeverExpires -AccountNeverExpires
    $actorSid=$newActor.SID.Value
    Add-LocalGroupMember -SID ([Security.Principal.SecurityIdentifier]::new('S-1-5-32-545')) -Member $actorName
    $actorProfile='C:\Users\'+$actorName
    $actorProfileKey='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$actorSid
    if((Test-Path -LiteralPath $actorProfile)-or(Test-Path -LiteralPath $actorProfileKey)){throw 'Disposable actor unexpectedly has a profile.'}
    $actorState.phase='created';$actorState.sid=$actorSid
    [IO.File]::WriteAllText($actorJournal,($actorState|ConvertTo-Json))
    $env:DISKED_TEST_ACTOR_NAME=$actorName
    $env:DISKED_TEST_ACTOR_PASS=$actorSecret
    $env:DISKED_TEST_ACTOR_SID=$actorSid
    $result.actor_name=$actorName;$result.actor_sid=$actorSid
'''

RETIRE_ACTOR=r'''
        if($actorName){
            Assert-WorkersStopped $workersStarted $workersStopped
            if($workersStarted){
                $proof=Get-Content -LiteralPath (Join-Path $root 'proof-result.json') -Raw|ConvertFrom-Json
                if(-not$proof.all_owned_processes_retired){throw 'Owned actor process retirement unverified.'}
                if($proof.scope-like'Per-image loader*' -and (-not$proof.image_registry_removed-or-not$proof.diagnostic_image_removed-or-not$proof.original_runtime_preserved)){
                    throw 'Preserve actor journal: diagnostic image/registry retirement unverified.'
                }
            }
            $existing=Get-LocalUser -Name $actorName -ErrorAction SilentlyContinue
            if($existing){
                if($existing.Description-ne$actorDescription-or($actorSid-and$existing.SID.Value-ne$actorSid)){throw 'Actor ownership changed; preserve account.'}
                if(-not$actorSid){$actorSid=$existing.SID.Value}
                $profile='C:\Users\'+$actorName
                $profileKey='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$actorSid
                if((Test-Path -LiteralPath $profile)-or(Test-Path -LiteralPath $profileKey)){throw 'Unexpected actor profile requires owned cleanup review.'}
                Remove-LocalUser -SID ([Security.Principal.SecurityIdentifier]::new($actorSid))
                if(Get-LocalUser -Name $actorName -ErrorAction SilentlyContinue){throw 'Disposable actor removal did not complete.'}
                $actorState.phase='retired';$actorState.profile_absent=$true
                [IO.File]::WriteAllText($actorJournal,($actorState|ConvertTo-Json))
            }
            $result.actor_removed=$true;$result.actor_profile_absent=$true
        }
'''

def main():
    work=Path(os.environ['DISKED_WORK_ROOT'])
    if (HERE/'result.json').exists():raise ValueError('Review and retain the previous attempt first')
    stage=work/'ordinary-proof';stage.mkdir()
    for name in ('ordinary-worker.py','target.py','guest-proof.py','loader-observer.py','loader-forensics.py'):
        data=(HERE/name).read_bytes();ast.parse(data);(stage/name).write_bytes(data)
    expected=json.loads((HERE.parent/'2026-10-18-guest-build/ordinary-token-expectations.json').read_bytes())
    expected.update(experiment='ordinary-token-32mib',source_base=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),initial_only_mib=32)
    diagnostic='--diagnostic' in sys.argv
    startup_diagnostic='--startup-diagnostic' in sys.argv
    loader_diagnostic='--loader-diagnostic' in sys.argv
    forensic='--loader-forensics' in sys.argv
    namespace='--namespace-diagnostic' in sys.argv
    if namespace:expected['namespace_diagnostic']=json.loads((HERE/'namespace-expectations.json').read_bytes())
    if forensic:expected['loader_forensics']=json.loads((HERE/'forensic-expectations.json').read_bytes())
    if loader_diagnostic:expected['loader_diagnostic']=json.loads((HERE/'loader-expectations.json').read_bytes())
    if startup_diagnostic:
        expected['startup_diagnostic']=json.loads((HERE/'startup-diagnostic-expectations.json').read_bytes())
    if diagnostic:
        expected['launch_diagnostic']=json.loads((HERE/'launch-diagnostic-expectations.json').read_bytes())
        expected.update(experiment='WithToken startup parameter isolation',variants=expected['launch_diagnostic']['variants'],
            admission='Diagnostic only. Each successful child must report its actual restricted nonelevated/non-AppContainer token. No excluded canary or undeclared standard handle may reach a candidate. Full protected-record,capacity,outside-write and interruption checks remain pending.')
    else:expected['selected_profile']=json.loads((HERE/'full-profile-expectations.json').read_bytes())
    (stage/'expected.json').write_text(json.dumps(expected,indent=2)+'\n',encoding='utf-8',newline='\n')
    setup=(PRIOR/'guest-proof.ps1').read_text()
    setup=once(setup,'[int]$SizeMiB=32)','[int]$SizeMiB=32,[Security.SecureString]$ActorPassword)')
    setup=once(setup,"$environmentVerified=$false","$environmentVerified=$false\n$actorName=$null;$actorSid=$null;$actorDescription=$null")
    marker=next(line for line in setup.splitlines() if "[IO.File]::WriteAllText((Join-Path $scratch 'owner.json')" in line)
    setup=once(setup,marker,marker+'\n'+CREATE_ACTOR)
    setup=once(setup,"actor_sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value","actor_sid=$actorSid")
    if diagnostic:setup=once(setup,"(Join-Path $root 'guest-proof.py') 2>&1)","(Join-Path $root 'guest-proof.py') --diagnostic 2>&1)")
    if startup_diagnostic:setup=once(setup,"(Join-Path $root 'guest-proof.py') 2>&1)","(Join-Path $root 'guest-proof.py') --startup-diagnostic 2>&1)")
    if loader_diagnostic:setup=once(setup,"(Join-Path $root 'guest-proof.py') 2>&1)","(Join-Path $root 'guest-proof.py') --loader-diagnostic 2>&1)")
    if forensic:setup=once(setup,"(Join-Path $root 'guest-proof.py') 2>&1)","(Join-Path $root 'guest-proof.py') --loader-forensics 2>&1)")
    if namespace:setup=once(setup,"(Join-Path $root 'guest-proof.py') 2>&1)","(Join-Path $root 'guest-proof.py') --namespace-diagnostic 2>&1)")
    setup=once(setup,"[Security.Principal.SecurityIdentifier]::new('S-1-15-2-1')","[Security.Principal.SecurityIdentifier]::new($actorSid)")
    setup=once(setup,'        if($attached){',RETIRE_ACTOR+'\n        if($attached){')
    setup=once(setup,"    $result.finished_at=[DateTime]::UtcNow.ToString('o')", "    $env:DISKED_TEST_ACTOR_NAME=$null;$env:DISKED_TEST_ACTOR_PASS=$null;$env:DISKED_TEST_ACTOR_SID=$null\n    $actorSecret=$null;$actorSecure=$null\n    $result.finished_at=[DateTime]::UtcNow.ToString('o')")
    (stage/'guest-proof.ps1').write_text(setup,encoding='utf-8',newline='\n')
    attach=(PRIOR/'attach-image.py').read_text()
    attach=once(attach,"(A;;GA;;;' + config['actor_sid']", "(A;;0x1301bf;;;' + config['actor_sid']")
    attach=once(attach,"''.join('(A;;0x1301bf;;;' + p['sid'] + ')' for p in profiles)", "''")
    ast.parse(attach);(stage/'attach-image.py').write_text(attach,encoding='utf-8',newline='\n')
    root_line="$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\\..\\..'))"
    fixed_root="$root='"+str(ROOT).replace("'","''")+"'"
    host=once((PRIOR/'run-proof.ps1').read_text(),root_line,fixed_root)
    host=once(host,'org.disked.guest-capacity-campaign/1','org.disked.ordinary-token-campaign/1')
    host=once(host,"    $job=Invoke-Command -Session $session -AsJob", "    $credentialPath=Join-Path $env:LOCALAPPDATA 'DiskEd\\credentials\\vm-3ebbe558-91b9-435b-96e4-0c8199bd38ad.xml'\n    $testCredential=Import-Clixml -LiteralPath $credentialPath\n    if($testCredential-isnot[Management.Automation.PSCredential]-or$testCredential.UserName-notmatch'^(?:(?:\\.|BLACKGLASS-HYPE|BLACKGLASS-HYPERV)\\\\)?Agents$'){throw 'Expected protected Agents credential required.'}\n    $job=Invoke-Command -Session $session -AsJob")
    host=once(host,'-ArgumentList $true,$SizeMiB','-ArgumentList $true,$SizeMiB,$testCredential.Password')
    host=once(host,'    if($session){Remove-PSSession -Session $session}','    if($session){Remove-PSSession -Session $session}\n    $testCredential=$null')
    host=once(host,"        @{host=(Join-Path $PSScriptRoot 'guest-proof.py');relative='guest-proof.py'},", "        @{host=(Join-Path $PSScriptRoot 'ordinary-worker.py');relative='ordinary-worker.py'},\n        @{host=(Join-Path $PSScriptRoot 'target.py');relative='target.py'},\n        @{host=(Join-Path $PSScriptRoot 'guest-proof.py');relative='guest-proof.py'},")
    host=once(host,'    $selected=@(',"    $selected=@(\n        @{host=(Join-Path $PSScriptRoot 'loader-forensics.py');relative='loader-forensics.py'},\n        @{host=(Join-Path $PSScriptRoot 'loader-observer.py');relative='loader-observer.py'},")
    start=host.index("        $python='C:\\ProgramData\\DiskEd\\python314'")
    end=host.index('        New-Item -ItemType Directory',start)
    host=host[:start]+host[end:]
    host=once(host,"    foreach($file in $selected)","    $backing=@(Get-VMHardDiskDrive -VM $vm);if($backing.Count-ne1){throw 'Unexpected VM backing topology.'}\n    $backingPath=$backing[0].Path;$result.host_backing_start_bytes=(Get-Item -LiteralPath $backingPath).Length\n    foreach($file in $selected)")
    host=once(host,'        Start-Sleep -Seconds 1',"        if(((Get-Item -LiteralPath $backingPath).Length-$result.host_backing_start_bytes)-gt1GB){Stop-Job -Job $job;throw 'Shared backing growth reached campaign ceiling.'}\n        Start-Sleep -Seconds 1")
    host=once(host,"    if($result.guest.setup.status-ne'pass'", "    $result.host_backing_end_bytes=(Get-Item -LiteralPath $backingPath).Length\n    if(-not$result.guest.setup.actor_removed-or-not$result.guest.setup.actor_profile_absent){throw 'Actor/account cleanup unverified.'}\n    if($result.guest.setup.status-ne'pass'")
    (stage/'run-proof.ps1').write_text(host,encoding='utf-8',newline='\n')
    cleanup=once((PRIOR/'clean-proof.ps1').read_text(),root_line,fixed_root)
    cleanup=once(cleanup,'$paths=@($Expected',"$extra=@(\"$root\\scratch\\ordinary-actor.json\",\"$root\\scratch\\outside\\baseline\",\"$root\\scratch\\outside\\forbidden\",\"$root\\scratch\\outside\\descendant-forbidden\",\"$root\\scratch\\outside\\inheritance-canary.bin\")\n        $paths=$extra+@($Expected")
    cleanup=once(cleanup,'$items.Count-gt32','$items.Count-gt40')
    (stage/'clean-proof.ps1').write_text(cleanup,encoding='utf-8',newline='\n')
    # Parse in Windows PowerShell 5.1 before any guest action.
    parser="$e=$null;$t=$null;foreach($f in Get-ChildItem -LiteralPath $args[0] -Filter '*.ps1'){$null=[Management.Automation.Language.Parser]::ParseFile($f.FullName,[ref]$t,[ref]$e);if($e.Count){throw ($e|Out-String)}}"
    check=subprocess.run([str(Path(os.environ['WINDIR'])/'System32/WindowsPowerShell/v1.0/powershell.exe'),'-NoProfile','-Command','& {'+parser+'} '+"'"+str(stage).replace("'","''")+"'"],capture_output=True,timeout=30)
    if check.returncode:raise RuntimeError(check.stderr.decode(errors='replace'))
    hashes={p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in stage.iterdir()}
    (HERE/'prepared.json').write_text(json.dumps(dict(status='pass',scope='Source/AST/template/Windows PowerShell5.1 parse only; no guest execution',generated_sha256=hashes),indent=2)+'\n',encoding='utf-8',newline='\n')
    if '--prepare-only' in sys.argv:return 0
    call=subprocess.run(['pwsh','-NoProfile','-File',str(stage/'run-proof.ps1'),'-SizeMiB','32'],cwd=ROOT,capture_output=True,timeout=600)
    raw=(stage/'proof-32.json').read_bytes();result=json.loads(raw)
    result['generated_sha256']=hashes;result['host_exit_code']=call.returncode
    result['experiment_kind']='launch-parameter diagnostic' if diagnostic else 'full ordinary-worker primitive proof'
    if startup_diagnostic:result['experiment_kind']='standard/restricted token and console diagnostic; no profile admission'
    if loader_diagnostic:result['experiment_kind']='minimal Python entry and native-import diagnostic; no profile admission'
    if forensic:result['experiment_kind']='owned per-image loader tracing; no profile admission'
    if namespace:result['experiment_kind']='existing object namespace access checks; no profile admission'
    result['host_error_tail']=call.stderr[-16384:].decode(errors='replace')
    (HERE/'result.json').write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8',newline='\n')
    if forensic:
        proof=result.get('guest',{}).get('proof',{})
        if not all(proof.get(name) for name in ('image_registry_removed','diagnostic_image_removed','original_runtime_preserved')):
            raise RuntimeError('Preserve guest actor journal: loader image/registry cleanup not established')
    if result.get('guest',{}).get('setup',{}).get('image_removed'):
        cleaned=subprocess.run(['pwsh','-NoProfile','-File',str(stage/'clean-proof.ps1'),'-SizeMiB','32'],cwd=ROOT,capture_output=True,timeout=60)
        if cleaned.returncode:
            (HERE/'cleanup-error.txt').write_bytes((cleaned.stdout+cleaned.stderr)[-16384:]);raise RuntimeError('Owned guest cleanup needs review')
        shutil.copyfile(stage/'cleanups.json',HERE/'cleanup.json')
    else:raise RuntimeError('Inspect owned account/image state before another attempt')
    return 0 if result['status']=='pass' and call.returncode==0 else 1

if __name__=='__main__':
    try: code=main()
    except Exception:
        (HERE/'runner-error.txt').write_text(traceback.format_exc()[-16384:],encoding='utf-8',newline='\n')
        raise
    raise SystemExit(code)
