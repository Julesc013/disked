$ErrorActionPreference='Stop'
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$source=Join-Path $PSScriptRoot 'inspect-interactive.py'
$hash=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
$nonce=[Guid]::NewGuid().ToString('N')
$session=$null
$record=@{status='running';scope='Read-only temporary Agents interactive task; no DiskEd, worker or GUI qualification';nonce=$nonce;payload_sha256=$hash}
try{
    $session=& (Join-Path $repo 'tools\connect-vm.ps1') -OpenSession
    Invoke-Command -Session $session -ArgumentList $nonce -ScriptBlock {
        param($nonce)
        if($env:COMPUTERNAME-ne'BLACKGLASS-HYPE'-or[Security.Principal.WindowsIdentity]::GetCurrent().Name-ne'BLACKGLASS-HYPE\Agents'){throw 'Wrong guest coordinator.'}
        $root='C:\ProgramData\DiskEd\interactive-check'
        if(Test-Path -LiteralPath $root){throw 'Existing interactive probe; no adoption.'}
        $parent=Get-Item -LiteralPath 'C:\ProgramData\DiskEd'
        if($parent.Attributes-band[IO.FileAttributes]::ReparsePoint){throw 'Linked parent.'}
        New-Item -ItemType Directory -Path $root|Out-Null
        $owner=@{nonce=$nonce;user_sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;session_id=3}
        [IO.File]::WriteAllText((Join-Path $root 'owner.json'),($owner|ConvertTo-Json))
    }
    Copy-Item -LiteralPath $source -Destination 'C:\ProgramData\DiskEd\interactive-check\run.py' -ToSession $session
    $record.guest=Invoke-Command -Session $session -ArgumentList $nonce,$hash -ScriptBlock {
        param($nonce,$hash)
        $ErrorActionPreference='Stop'
        $root='C:\ProgramData\DiskEd\interactive-check'
        $owner=Get-Content -LiteralPath (Join-Path $root 'owner.json') -Raw|ConvertFrom-Json
        if($owner.nonce-ne$nonce-or$owner.user_sid-ne[Security.Principal.WindowsIdentity]::GetCurrent().User.Value){throw 'Wrong ownership.'}
        if((Get-FileHash -LiteralPath (Join-Path $root 'run.py') -Algorithm SHA256).Hash.ToLowerInvariant()-ne$hash){throw 'Payload changed.'}
        $name='DiskEd-Interactive-'+$nonce
        $description='DiskEd owned read-only interactive probe '+$nonce
        $registered=$false;$quiescent=$false
        $report=@{status='running';task_name=$name;cleanup=$false}
        try{
            $action=New-ScheduledTaskAction -Execute 'C:\ProgramData\DiskEd\python314\python.exe' -Argument '-B "C:\ProgramData\DiskEd\interactive-check\run.py"' -WorkingDirectory $root
            $principal=New-ScheduledTaskPrincipal -UserId $owner.user_sid -LogonType Interactive -RunLevel Highest
            $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::FromSeconds(60)) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
            Register-ScheduledTask -TaskName $name -Description $description -Action $action -Principal $principal -Settings $settings|Out-Null
            $registered=$true
            Start-ScheduledTask -TaskName $name
            $until=[DateTime]::UtcNow.AddSeconds(40)
            do{
                Start-Sleep -Milliseconds 250
                $task=Get-ScheduledTask -TaskName $name
                if($task.Description-ne$description){throw 'Task ownership changed.'}
                if((Test-Path -LiteralPath (Join-Path $root 'observation.json'))-and$task.State-ne'Running'){break}
            }while([DateTime]::UtcNow-lt$until)
            if($task.State-eq'Running'-or-not(Test-Path -LiteralPath (Join-Path $root 'observation.json'))){throw 'Interactive observation unavailable.'}
            $quiescent=$true
            $file=Get-Item -LiteralPath (Join-Path $root 'observation.json')
            if($file.Length-gt32768-or($file.Attributes-band[IO.FileAttributes]::ReparsePoint)){throw 'Invalid observation.'}
            $report.observation=Get-Content -LiteralPath $file.FullName -Raw|ConvertFrom-Json
            if($report.observation.nonce-ne$nonce-or$report.observation.status-ne'pass'){throw 'Interactive identity/display check failed.'}
            $report.status='pass'
        }catch{$report.status='fail';$report.error=$_.Exception.Message}
        finally{
            if($registered){
                $task=Get-ScheduledTask -TaskName $name
                if($task.Description-ne$description){throw 'Preserve changed task.'}
                if($task.State-eq'Running'){
                    Stop-ScheduledTask -TaskName $name
                    $until=[DateTime]::UtcNow.AddSeconds(5)
                    do{Start-Sleep -Milliseconds 100;$task=Get-ScheduledTask -TaskName $name}while($task.State-eq'Running'-and[DateTime]::UtcNow-lt$until)
                }
                if($task.State-eq'Running'){throw 'Owned task retirement uncertain; preserve files.'}
                $quiescent=$true
                Unregister-ScheduledTask -TaskName $name -Confirm:$false
            }else{$quiescent=$true}
            if($quiescent){
                if([IO.Path]::GetFullPath($root)-ne'C:\ProgramData\DiskEd\interactive-check'){throw 'Cleanup containment changed.'}
                $items=@(Get-ChildItem -LiteralPath $root -Force)
                foreach($item in $items){if($item.PSIsContainer-or($item.Attributes-band[IO.FileAttributes]::ReparsePoint)-or$item.Name-notin@('owner.json','run.py','observation.json')){throw 'Unexpected owned probe entry; preserve.'}}
                foreach($item in $items){Remove-Item -LiteralPath $item.FullName}
                Remove-Item -LiteralPath $root
                $report.cleanup=-not(Test-Path -LiteralPath $root)
            }
        }
        $report
    }
    if($record.guest.status-ne'pass'-or-not$record.guest.cleanup){throw 'Interactive observation failed.'}
    $record.status='pass'
}catch{$record.status='fail';$record.error=$_.Exception.Message;throw}
finally{
    if($session){Remove-PSSession -Session $session}
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'interactive-session-check.json'),($record|ConvertTo-Json -Depth 8)+"`n",[Text.UTF8Encoding]::new($false))
}
