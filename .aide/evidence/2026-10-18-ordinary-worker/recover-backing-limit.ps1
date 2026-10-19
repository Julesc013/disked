# One-off run85 retirement after the host's shared-backing growth guard fired.
# No broad process termination, shared account change, reboot or compaction.
$ErrorActionPreference='Stop'
$repo='D:\Projects\DiskEd\disked'
$nonce='69df43625e864cd08fd0311fac9ceaeb'
$s=& (Join-Path $repo 'tools\connect-vm.ps1') -OpenSession
try {
    $result=Invoke-Command -Session $s -ArgumentList $nonce -ScriptBlock {
        param($Nonce)
        $ErrorActionPreference='Stop'
        $r='C:\ProgramData\DiskEd\qualification'
        if($env:COMPUTERNAME-ne'BLACKGLASS-HYPE'-or[Security.Principal.WindowsIdentity]::GetCurrent().Name-ne'BLACKGLASS-HYPE\Agents'){throw 'Exact guest coordinator required.'}
        $ancestor=Get-Item -LiteralPath $r
        while($ancestor){if($ancestor.Attributes-band[IO.FileAttributes]::ReparsePoint){throw 'Linked root.'};$ancestor=$ancestor.Parent}
        $state=Get-Content -LiteralPath "$r\scratch\state.json" -Raw|ConvertFrom-Json
        $actor=Get-Content -LiteralPath "$r\scratch\ordinary-actor.json" -Raw|ConvertFrom-Json
        if($state.nonce-ne$Nonce-or$actor.nonce-ne$Nonce-or$actor.sid-ne'S-1-5-21-385394198-2603589104-1765785984-1086'-or$state.image_uuid-ne'E1386455CCC8B1499A9E38441F989CB5'-or$state.work-ne'R:\work'-or$state.size_mib-ne512){throw 'Run85 ownership changed.'}
        if(Get-ScheduledTask -TaskName ('DiskEd-Native-Interactive-'+$Nonce) -ErrorAction SilentlyContinue){throw 'Original interactive task remains.'}
        if(Test-Path -LiteralPath "$r\interactive-input.xml"){throw 'Original credential remains.'}
        $owned=@()
        foreach($p in Get-CimInstance Win32_Process){
            if($p.CommandLine-match'DiskEd\\qualification|R:\\work'){$owned+=,$p.ProcessId;continue}
            $owner=Invoke-CimMethod -InputObject $p -MethodName GetOwnerSid -ErrorAction SilentlyContinue
            if($owner.Sid-eq$actor.sid){$owned+=,$p.ProcessId}
        }
        if($owned.Count){throw ('Owned processes remain: '+($owned-join','))}
        $log=Get-ChildItem -LiteralPath 'R:\work\compile-x64' -Filter '*.log'|Sort-Object LastWriteTime|Select-Object -Last 1
        $tail=if($log){@(Get-Content -LiteralPath $log.FullName -Tail 35)}else{@()}
        $script=@'
import importlib.util,json
from pathlib import Path
r=Path('C:/ProgramData/DiskEd/qualification')
d=json.loads((r/'scratch/ordinary-actor.json').read_bytes())
assert d['nonce']=='69df43625e864cd08fd0311fac9ceaeb'
out={'status':'running','scope':'Run85 exact journaled delta retirement after externally verified process quiescence','reports':{}}
for filename,key in [('null-device.py','null_build'),('object-namespace.py','object_namespace'),('window-station.py','window_station')]:
 spec=importlib.util.spec_from_file_location('recovery_'+key,r/filename);m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 g=m.Grant('build',recovery=True) if key=='null_build' else m.Grant(recovery=True) if key=='object_namespace' else m.Grant()
 try:
  g.retire(quiescent=True);out['reports'][key]=g.report
 finally:g.close()
out['status']='pass'
(r/'forced-retirement.json').write_text(json.dumps(out,indent=2)+'\n',encoding='utf-8',newline='\n')
'@
        $helper="$r\forced-retirement.py"
        if(Test-Path -LiteralPath $helper){
            if([IO.File]::ReadAllText($helper)-ne$script){throw 'Recovery helper changed.'}
        }else{[IO.File]::WriteAllText($helper,$script,[Text.UTF8Encoding]::new($false))}
        $name='DiskEd-Recovery-'+$Nonce
        $wrapper=@'
& { $ErrorActionPreference='Continue'; $lines=@(& 'C:\ProgramData\DiskEd\python314\python.exe' -B 'C:\ProgramData\DiskEd\qualification\forced-retirement.py' 2>&1); $code=$LASTEXITCODE; $text=($lines|ForEach-Object ToString)-join [Environment]::NewLine; if($text.Length-gt16384){$text=$text.Substring($text.Length-16384)}; [IO.File]::WriteAllText('C:\ProgramData\DiskEd\qualification\forced-retirement-output.json',(@{exit_code=$code;output=$text}|ConvertTo-Json),[Text.UTF8Encoding]::new($false)); exit $code }
'@
        $encoded=[Convert]::ToBase64String([Text.Encoding]::Unicode.GetBytes($wrapper))
        $action=New-ScheduledTaskAction -Execute 'C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe' -Argument ('-NoProfile -NonInteractive -WindowStyle Hidden -EncodedCommand '+$encoded) -WorkingDirectory $r
        $principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value) -LogonType Interactive -RunLevel Highest
        $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::FromSeconds(120)) -MultipleInstances IgnoreNew
        Register-ScheduledTask -TaskName $name -Description ('DiskEd run85 recovery '+$Nonce) -Action $action -Principal $principal -Settings $settings|Out-Null
        try {
            Start-ScheduledTask -TaskName $name
            $until=[DateTime]::UtcNow.AddSeconds(125)
            do {Start-Sleep -Milliseconds 200;$task=Get-ScheduledTask -TaskName $name} while(($task.State-eq'Running'-or-not(Test-Path -LiteralPath "$r\forced-retirement.json"))-and[DateTime]::UtcNow-lt$until)
            if($task.State-eq'Running'){throw 'Retirement task still running.'}
            if(-not(Test-Path -LiteralPath "$r\forced-retirement.json")){
                if(Test-Path -LiteralPath "$r\forced-retirement-output.json"){throw ([IO.File]::ReadAllText("$r\forced-retirement-output.json"))}
                throw 'No retirement receipt or diagnostic.'
            }
            $retirement=Get-Content -LiteralPath "$r\forced-retirement.json" -Raw|ConvertFrom-Json
            if($retirement.status-ne'pass'){throw 'Delta retirement failed.'}
        } finally {
            $task=Get-ScheduledTask -TaskName $name
            if($task.State-eq'Running'){throw 'Preserve live recovery task.'}
            Unregister-ScheduledTask -TaskName $name -Confirm:$false
        }
        [pscustomobject]@{status='pass';nonce=$Nonce;owned_processes_observed=0;credential_absent=$true;retirement=$retirement;build_tail=$tail;pagefiles=@(Get-CimInstance Win32_PageFileUsage|Select-Object Name,AllocatedBaseSize,CurrentUsage,PeakUsage);guest_free_bytes=([IO.DriveInfo]::new('C:\')).AvailableFreeSpace;media_removed=$false;source_removed=$false;observed_at=[DateTime]::UtcNow.ToString('o')}
    }
    $result=$result|Select-Object * -ExcludeProperty PSComputerName,RunspaceId,PSShowComputerName
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'eighty-fifth-delta-retirement.json'),($result|ConvertTo-Json -Depth 12).Replace("`r`n","`n")+"`n",[Text.UTF8Encoding]::new($false))
    $result|Select-Object status,nonce,owned_processes_observed,media_removed,source_removed|ConvertTo-Json
} finally {Remove-PSSession -Session $s}
