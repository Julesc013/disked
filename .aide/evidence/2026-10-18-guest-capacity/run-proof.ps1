#Requires -Version 7.0
# Host coordinates; disk creation, attachment and all workers stay in the guest.
param([ValidateSet(32,512)][int]$SizeMiB=32)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$guestRoot='C:\ProgramData\DiskEd\qualification'
$session=$null
$result=[ordered]@{schema='org.disked.guest-capacity-campaign/1';started_at=[DateTime]::UtcNow.ToString('o');status='not_run';host_test_media_mounted=$false;native_product_tests_run=$false}
try {
    if(-not$env:DISKED_WORK_ROOT){throw 'Use the managed host workspace runner.'}
    foreach($drive in 'C:\','D:\'){if(([IO.DriveInfo]::new($drive)).AvailableFreeSpace-lt20GB){throw 'Host free-space reserve missing.'}}
    $selected=@(
        @{host=(Join-Path $root 'tools\workspace.py');relative='tools/workspace.py'},
        @{host=(Join-Path $root 'tools\windows-worker.py');relative='tools/windows-worker.py'},
        @{host=(Join-Path $root 'tools\qualify-storage.py');relative='tools/qualify-storage.py'},
        @{host=(Join-Path $PSScriptRoot 'guest-proof.py');relative='guest-proof.py'},
        @{host=(Join-Path $PSScriptRoot 'guest-proof.ps1');relative='guest-proof.ps1'},
        @{host=(Join-Path $PSScriptRoot 'attach-image.py');relative='attach-image.py'},
        @{host=(Join-Path $PSScriptRoot 'expected.json');relative='expected.json'}
    )
    $files=@($selected|ForEach-Object{[pscustomobject]@{path=$_.relative;bytes=(Get-Item -LiteralPath $_.host).Length;sha256=(Get-FileHash -LiteralPath $_.host -Algorithm SHA256).Hash}})
    $manifest=@{schema='org.disked.guest-proof-sources/1';base_revision=(& git -C $root rev-parse HEAD);files=$files}
    $manifestFile=Join-Path $env:DISKED_WORK_ROOT 'source-manifest.json'
    [IO.File]::WriteAllText($manifestFile,($manifest|ConvertTo-Json -Depth 5),[Text.UTF8Encoding]::new($false))
    $result.sources=$manifest
    $session=& (Join-Path $root 'tools\connect-vm.ps1') -OpenSession
    Invoke-Command -Session $session -ScriptBlock {
        if([Security.Principal.WindowsIdentity]::GetCurrent().Name-ne'BLACKGLASS-HYPE\Agents'){throw 'Wrong guest account.'}
        if(Test-Path -LiteralPath 'C:\ProgramData\DiskEd\qualification'){throw 'Existing qualification workspace; inspect before reuse.'}
        if(Test-Path -LiteralPath 'C:\ProgramData\DiskEd\runtime-transfer'){throw 'Runtime transfer cleanup incomplete.'}
        $python='C:\ProgramData\DiskEd\python314'
        # The public interpreter/stdlib needs read/execute access from AppContainer;
        # grant no write access and do not change any host or user-profile ACL.
        $acl=Get-Acl -LiteralPath $python
        $rule=[Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-15-2-1'),[Security.AccessControl.FileSystemRights]::ReadAndExecute,[Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit',[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow)
        $acl.AddAccessRule($rule);Set-Acl -LiteralPath $python -AclObject $acl
        New-Item -ItemType Directory -Path 'C:\ProgramData\DiskEd\qualification\tools'|Out-Null
    }
    $vm=Get-VM -Id '3ebbe558-91b9-435b-96e4-0c8199bd38ad'
    foreach($file in $selected){Copy-VMFile -VM $vm -FileSource Host -SourcePath $file.host -DestinationPath (Join-Path $guestRoot $file.relative)}
    Copy-VMFile -VM $vm -FileSource Host -SourcePath $manifestFile -DestinationPath (Join-Path $guestRoot 'source-manifest.json')
    # Send trusted local source as a remoting script; do not alter guest policy.
    $job=Invoke-Command -Session $session -AsJob -FilePath (Join-Path $PSScriptRoot 'guest-proof.ps1') -ArgumentList $true,$SizeMiB
    $result.remote_job_id=$job.Id
    while($job.State-in@('NotStarted','Running')){
        foreach($drive in 'C:\','D:\'){if(([IO.DriveInfo]::new($drive)).AvailableFreeSpace-lt20GB){Stop-Job -Job $job;throw 'Host reserve reached; owned remote campaign stopped.'}}
        Start-Sleep -Seconds 1
    }
    $jobErrors=@();$remoteLog=@(Receive-Job -Job $job -ErrorVariable jobErrors -ErrorAction Continue)
    $result.remote_job_state=[string]$job.State
    $result.remote_output=($remoteLog|ForEach-Object ToString)-join"`n"
    $result.remote_errors=($jobErrors|ForEach-Object ToString)-join"`n"
    Remove-Job -Job $job
    if($result.remote_job_state-eq'Failed'){throw ('Guest invocation failed: '+$result.remote_errors)}
    $result.guest=Invoke-Command -Session $session -ScriptBlock {
        $root='C:\ProgramData\DiskEd\qualification'
        $setup=Get-Content -LiteralPath "$root\setup-result.json" -Raw|ConvertFrom-Json
        $proof=$null;if(Test-Path -LiteralPath "$root\proof-result.json"){$proof=Get-Content -LiteralPath "$root\proof-result.json" -Raw|ConvertFrom-Json}
        [pscustomobject]@{identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name;setup=$setup;proof=$proof;free_c_bytes=([IO.DriveInfo]::new('C:\')).AvailableFreeSpace}
    }|Select-Object * -ExcludeProperty PSComputerName,RunspaceId,PSShowComputerName
    if($result.guest.setup.status-ne'pass' -or $result.guest.proof.status-ne'pass' -or -not$result.guest.setup.image_removed){throw 'Guest capacity/confinement proof did not pass.'}
    $result.status='pass'
}catch{$result.status='fail';$result.error=$_.Exception.Message;throw}
finally{
    if($session){Remove-PSSession -Session $session}
    $result.finished_at=[DateTime]::UtcNow.ToString('o')
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot "proof-$SizeMiB.json"),(($result|ConvertTo-Json -Depth 16)-replace"`r`n","`n")+"`n",[Text.UTF8Encoding]::new($false))
    $result|ConvertTo-Json -Depth 16
}
