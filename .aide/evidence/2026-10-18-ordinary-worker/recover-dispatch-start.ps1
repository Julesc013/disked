# One-off recovery of run72: Python never opened the missing coordinator file.
# No process termination, ACL changes, existing media or unrelated accounts.
$ErrorActionPreference='Stop'
$repo='D:\Projects\DiskEd\disked'
$receipt=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'result.json') -Raw|ConvertFrom-Json
if($receipt.sources.base_revision-notmatch'^4d6803b3[0-9a-f]{32}$'){throw 'Only run72 receipt supported.'}
$session=& (Join-Path $repo 'tools\connect-vm.ps1') -OpenSession
try{
    $result=Invoke-Command -Session $session -ArgumentList ($receipt|ConvertTo-Json -Depth 30 -Compress) -ScriptBlock {
        param($ReceiptJson)
        $ErrorActionPreference='Stop';$receipt=$ReceiptJson|ConvertFrom-Json
        $root='C:\ProgramData\DiskEd\qualification';$image="$root\scratch\disked-proof.vhd"
        if([Security.Principal.WindowsIdentity]::GetCurrent().Name-ne'BLACKGLASS-HYPE\Agents'-or$env:COMPUTERNAME-ne'BLACKGLASS-HYPE'){throw 'Exact guest required.'}
        $ancestor=Get-Item -LiteralPath $root -Force
        while($ancestor){if($ancestor.Attributes-band[IO.FileAttributes]::ReparsePoint){throw 'Linked root.'};$ancestor=$ancestor.Parent}
        $state=Get-Content -LiteralPath "$root\scratch\state.json" -Raw|ConvertFrom-Json
        $actor=Get-Content -LiteralPath "$root\scratch\ordinary-actor.json" -Raw|ConvertFrom-Json
        $setup=Get-Content -LiteralPath "$root\setup-result.json" -Raw|ConvertFrom-Json
        $interactive=Get-Content -LiteralPath "$root\interactive-result.json" -Raw|ConvertFrom-Json
        if($state.nonce-ne'c7ca3fa011964c40a2adc167418b9f76'-or$state.size_mib-ne512-or$state.image-ne$image-or$state.image_uuid-ne$receipt.guest.setup.image_uuid){throw 'Owned media binding changed.'}
        if($actor.name-ne'DiskEdTest-c7ca3fa0'-or$actor.sid-ne$receipt.guest.setup.actor_sid-or$actor.nonce-ne$state.nonce-or$actor.phase-ne'created'){throw 'Actor binding changed.'}
        foreach($key in @('window_station','crypto_device','null_build','null_user')){if($actor.PSObject.Properties[$key]){throw 'Unexpected exception journal; no blind retirement.'}}
        if($interactive.nonce-ne$state.nonce-or$interactive.status-ne'finished'-or$interactive.exit_code-ne2-or$interactive.session_id-ne3-or$setup.runner_exit-ne2){throw 'Missing coordinator refusal not established.'}
        if(($interactive.output-join"`n")-notmatch "can't open file.*source.*tools.*workspace.py.*No such file or directory"){throw 'Different startup failure.'}
        if(Get-ScheduledTask -TaskName ('DiskEd-Native-Interactive-'+$state.nonce) -ErrorAction SilentlyContinue){throw 'Owned task remains.'}
        if(Test-Path -LiteralPath "$root\interactive-input.xml"){throw 'Credential remains.'}
        foreach($path in @('source','source-owner.json','proof-result.json','scoped-directory-access.json')){if(Test-Path -LiteralPath (Join-Path $root $path)){throw 'Coordinator effects exist; no prelaunch recovery.'}}
        if(@(Get-ChildItem -LiteralPath $state.work -Force).Count){throw 'Managed worker workspace exists.'}
        $live=@(Get-Process -IncludeUserName|Where-Object {$_.UserName-eq('BLACKGLASS-HYPE\'+$actor.name)})
        if($live.Count){throw 'Disposable actor processes remain.'}
        $user=Get-LocalUser -Name $actor.name
        if($user.SID.Value-ne$actor.sid-or$user.Description-ne('DiskEd test '+$state.nonce)){throw 'Account ownership changed.'}
        if((Test-Path -LiteralPath ('C:\Users\'+$actor.name))-or(Test-Path -LiteralPath ('HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$actor.sid))){throw 'Unexpected actor profile.'}
        $paths=@($receipt.sources.files|ForEach-Object{[IO.Path]::GetFullPath((Join-Path $root $_.path))})
        $paths+=@('source-manifest.json','setup-result.json','interactive-result.json','scratch\ordinary-actor.json','scratch\create.txt','scratch\owner.json','scratch\state.json','scratch\attach-config.json','scratch\attach-result.json','scratch\disked-proof.vhd')|ForEach-Object{Join-Path $root $_}
        $dirs=@();foreach($path in $paths){$parent=[IO.Path]::GetDirectoryName($path);while($parent-ne$root){if(-not$parent.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Path escaped root.'};if($parent-notin$dirs){$dirs+=,$parent};$parent=[IO.Path]::GetDirectoryName($parent)}}
        $queue=[Collections.Generic.Stack[string]]::new();$queue.Push($root);$count=0
        while($queue.Count){foreach($item in Get-ChildItem -LiteralPath $queue.Pop() -Force){$count++;if($count-gt100-or($item.Attributes-band[IO.FileAttributes]::ReparsePoint)){throw 'Unexpected/linked recovery entry.'};if($item.PSIsContainer){if($item.FullName-notin$dirs){throw 'Unexpected directory.'};$queue.Push($item.FullName)}elseif($item.FullName-notin$paths){throw 'Unexpected recovery file.'}}}
        foreach($entry in $receipt.sources.files){if((Get-FileHash -LiteralPath (Join-Path $root $entry.path) -Algorithm SHA256).Hash-ne$entry.sha256){throw 'Transferred source changed.'}}
        $file=Get-Item -LiteralPath $image;if($file.Length-ne(512MB+512)){throw 'Fixed media size changed.'}
        $stream=[IO.File]::Open($image,'Open','Read','ReadWrite');try{$null=$stream.Seek(-512,'End');$footer=New-Object byte[] 512;if($stream.Read($footer,0,512)-ne512){throw 'Short footer.'}}finally{$stream.Dispose()}
        $uuid=([BitConverter]::ToString($footer,68,16)).Replace('-','')
        if([Text.Encoding]::ASCII.GetString($footer,0,8)-ne'conectix'-or$uuid-ne$state.image_uuid-or$footer[60]-ne0-or$footer[61]-ne0-or$footer[62]-ne0-or$footer[63]-ne2){throw 'Fixed media UUID/type changed.'}
        $size=0L;for($i=48;$i-lt56;$i++){$size=($size-shl8)-bor$footer[$i]};if($size-ne512MB){throw 'Virtual capacity changed.'}
        $sum=0L;$checksum=0L;for($i=0;$i-lt512;$i++){if($i-lt64-or$i-ge68){$sum+=$footer[$i]}};for($i=64;$i-lt68;$i++){$checksum=($checksum-shl8)-bor$footer[$i]};if($checksum-ne([uint32]::MaxValue-$sum)){throw 'Footer checksum changed.'}
        $diskImage=Get-DiskImage -ImagePath $image;$disk=$diskImage|Get-Disk
        if(-not$diskImage.Attached-or$disk.IsBoot-or$disk.IsSystem-or$disk.Size-ne512MB-or$disk.UniqueId-ne$receipt.guest.setup.disk_unique_id-or$disk.BusType-notin@('Virtual','File Backed Virtual')){throw 'Owned disk identity changed.'}
        Dismount-DiskImage -ImagePath $image|Out-Null
        if((Get-DiskImage -ImagePath $image).Attached){throw 'Owned media still attached.'}
        Remove-LocalUser -SID ([Security.Principal.SecurityIdentifier]::new($actor.sid))
        if(Get-LocalUser -Name $actor.name -ErrorAction SilentlyContinue){throw 'Actor retirement failed.'}
        $bytes=0L;foreach($path in $paths){if(Test-Path -LiteralPath $path){$bytes+=(Get-Item -LiteralPath $path).Length;Remove-Item -LiteralPath $path}}
        foreach($path in @($dirs|Sort-Object Length -Descending)+@($root)){if(Test-Path -LiteralPath $path){Remove-Item -LiteralPath $path}}
        [pscustomobject]@{status='pass';scope='Run72 failed before coordinator open;owned fixed media/account/transferred metadata retirement only';nonce=$state.nonce;image_uuid=$uuid;actor_removed=$true;actor_profile_absent=$true;task_absent=$true;credential_absent=$true;qualified_root_absent=(-not(Test-Path -LiteralPath $root));logical_bytes_removed=$bytes;unrelated_processes_killed=$false;observed_at=[DateTime]::UtcNow.ToString('o')}
    }
    $result=$result|Select-Object * -ExcludeProperty PSComputerName,RunspaceId,PSShowComputerName
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'seventy-second-recovery.json'),($result|ConvertTo-Json -Depth 5).Replace("`r`n","`n")+"`n",[Text.UTF8Encoding]::new($false))
    $result|ConvertTo-Json
}finally{Remove-PSSession -Session $session}
