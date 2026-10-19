param([switch]$Child)
$ErrorActionPreference='Stop'
$root='C:\ProgramData\DiskEd\qualification'
$python='C:\ProgramData\DiskEd\python314\python.exe'
$inputPath=Join-Path $root 'interactive-input.xml'
$outputPath=Join-Path $root 'interactive-result.json'
$state=Get-Content -LiteralPath (Join-Path $root 'scratch\state.json') -Raw|ConvertFrom-Json
$expected=Get-Content -LiteralPath (Join-Path $root 'expected.json') -Raw|ConvertFrom-Json
if(-not$expected.interactive_ui-or$env:COMPUTERNAME-ne'BLACKGLASS-HYPE'-or[Security.Principal.WindowsIdentity]::GetCurrent().Name-ne'BLACKGLASS-HYPE\Agents'){throw 'Wrong interactive coordinator.'}
if($Child){
    $record=@{status='running';nonce=$state.nonce;session_id=[Diagnostics.Process]::GetCurrentProcess().SessionId;output=@();exit_code=$null}
    try{
        if($record.session_id-ne3){throw 'Agents session3 required.'}
        $runInput=Import-Clixml -LiteralPath $inputPath
        if($runInput.nonce-ne$state.nonce-or$runInput.user_sid-ne[Security.Principal.WindowsIdentity]::GetCurrent().User.Value){throw 'Interactive input identity changed.'}
        $actor=Get-Content -LiteralPath (Join-Path $root 'scratch\ordinary-actor.json') -Raw|ConvertFrom-Json
        if($runInput.credential-isnot[Management.Automation.PSCredential]-or$runInput.credential.UserName-ne$actor.name-or$runInput.actor_sid-ne$actor.sid){throw 'Actor credential identity changed.'}
        $env:DISKED_TEST_ACTOR_NAME=$actor.name
        $env:DISKED_TEST_ACTOR_SID=$actor.sid
        $env:DISKED_TEST_ACTOR_PASS=$runInput.credential.GetNetworkCredential().Password
        # The source tree is unpacked inside the managed coordinator. Bootstrap
        # every mode with the already hash-verified transferred tools runner.
        $workspace=Join-Path $root 'tools\workspace.py'
        $arguments=@('-B',$workspace,'run','--',$python,'-B',(Join-Path $root 'guest-proof.py'),$runInput.mode)
        $oldPreference=$ErrorActionPreference
        try{$ErrorActionPreference='Continue';$lines=@(& $python @arguments 2>&1);$code=$LASTEXITCODE}finally{$ErrorActionPreference=$oldPreference}
        $record.output=@($lines|ForEach-Object ToString)
        if([Text.Encoding]::UTF8.GetByteCount(($record.output-join"`n"))-gt65536){throw 'Interactive coordinator output bound.'}
        $record.exit_code=$code;$record.status='finished'
    }catch{$record.status='fail';$record.error=$_.Exception.Message}
    finally{
        $env:DISKED_TEST_ACTOR_NAME=$null;$env:DISKED_TEST_ACTOR_PASS=$null;$env:DISKED_TEST_ACTOR_SID=$null;$runInput=$null
        [IO.File]::WriteAllText($outputPath,($record|ConvertTo-Json -Depth 5)+"`n",[Text.UTF8Encoding]::new($false))
    }
    if($record.status-ne'finished'){exit 1}
    exit $record.exit_code
}
if((Test-Path -LiteralPath $inputPath)-or(Test-Path -LiteralPath $outputPath)){throw 'Existing interactive run; no adoption.'}
$actor=Get-Content -LiteralPath (Join-Path $root 'scratch\ordinary-actor.json') -Raw|ConvertFrom-Json
if($env:DISKED_TEST_ACTOR_NAME-ne$actor.name-or$env:DISKED_TEST_ACTOR_SID-ne$actor.sid){throw 'Actor environment changed.'}
$mode=if($expected.native_x64){'--native-x64'}elseif($expected.crypto_full){'--crypto-full'}else{throw 'Undeclared interactive mode.'}
$limit=if($expected.native_x64){7200}else{300}
$secure=ConvertTo-SecureString $env:DISKED_TEST_ACTOR_PASS -AsPlainText -Force
$runInput=@{nonce=$state.nonce;user_sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value;actor_sid=$actor.sid;mode=$mode;credential=[Management.Automation.PSCredential]::new($actor.name,$secure)}
$runInput|Export-Clixml -LiteralPath $inputPath
$acl=[Security.AccessControl.FileSecurity]::new()
$acl.SetAccessRuleProtection($true,$false)
foreach($sid in @('S-1-5-18',$runInput.user_sid)){
    $acl.AddAccessRule([Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new($sid),[Security.AccessControl.FileSystemRights]::FullControl,[Security.AccessControl.AccessControlType]::Allow))
}
Set-Acl -LiteralPath $inputPath -AclObject $acl
$runInput=$null;$secure=$null
$name='DiskEd-Native-Interactive-'+$state.nonce
$description='DiskEd owned interactive coordinator '+$state.nonce
$registered=$false;$quiescent=$false
try{
    $childCommand="& ([scriptblock]::Create([IO.File]::ReadAllText('C:\ProgramData\DiskEd\qualification\interactive-run.ps1'))) -Child"
    $taskArguments='-NoProfile -NonInteractive -WindowStyle Hidden -Command "'+$childCommand+'"'
    $action=New-ScheduledTaskAction -Execute "$env:WINDIR\System32\WindowsPowerShell\v1.0\powershell.exe" -Argument $taskArguments -WorkingDirectory $root
    $principal=New-ScheduledTaskPrincipal -UserId ([Security.Principal.WindowsIdentity]::GetCurrent().User.Value) -LogonType Interactive -RunLevel Highest
    $settings=New-ScheduledTaskSettingsSet -ExecutionTimeLimit ([TimeSpan]::FromSeconds($limit)) -MultipleInstances IgnoreNew -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
    Register-ScheduledTask -TaskName $name -Description $description -Action $action -Principal $principal -Settings $settings|Out-Null
    $registered=$true
    Start-ScheduledTask -TaskName $name
    $until=[DateTime]::UtcNow.AddSeconds($limit+30)
    do{
        Start-Sleep -Milliseconds 500
        $task=Get-ScheduledTask -TaskName $name
        if($task.Description-ne$description){throw 'Task ownership changed.'}
        if((Test-Path -LiteralPath $outputPath)-and$task.State-ne'Running'){break}
    }while([DateTime]::UtcNow-lt$until)
    if($task.State-eq'Running'-or-not(Test-Path -LiteralPath $outputPath)){throw 'Interactive task did not finish.'}
    $quiescent=$true
    $file=Get-Item -LiteralPath $outputPath
    if($file.Length-gt131072-or($file.Attributes-band[IO.FileAttributes]::ReparsePoint)){throw 'Invalid interactive result.'}
    $record=Get-Content -LiteralPath $outputPath -Raw|ConvertFrom-Json
    if($record.nonce-ne$state.nonce-or$record.session_id-ne3-or$record.status-ne'finished'-or$null-eq$record.exit_code){throw 'Interactive result incomplete.'}
}finally{
    if($registered){
        $task=Get-ScheduledTask -TaskName $name
        if($task.Description-ne$description){throw 'Preserve changed interactive task.'}
        if($task.State-eq'Running'){
            Stop-ScheduledTask -TaskName $name
            $until=[DateTime]::UtcNow.AddSeconds(10)
            do{Start-Sleep -Milliseconds 100;$task=Get-ScheduledTask -TaskName $name}while($task.State-eq'Running'-and[DateTime]::UtcNow-lt$until)
        }
        if($task.State-eq'Running'){throw 'Interactive task retirement uncertain; preserve owned state.'}
        $quiescent=$true
        Unregister-ScheduledTask -TaskName $name -Confirm:$false
        if(Get-ScheduledTask -TaskName $name -ErrorAction SilentlyContinue){throw 'Task removal unverified.'}
    }
    if($quiescent-and(Test-Path -LiteralPath $inputPath)){
        $file=Get-Item -LiteralPath $inputPath
        if($file.Attributes-band[IO.FileAttributes]::ReparsePoint){throw 'Preserve linked interactive credential.'}
        Remove-Item -LiteralPath $inputPath
    }
}
$summary=@{interactive_task=$name;session_id=3;quiescent=$quiescent;task_removed=$true;credential_removed=(-not(Test-Path -LiteralPath $inputPath))}
[pscustomobject]@{output=@($record.output|ForEach-Object {[string]$_});exit_code=[int]$record.exit_code;metadata=$summary}
