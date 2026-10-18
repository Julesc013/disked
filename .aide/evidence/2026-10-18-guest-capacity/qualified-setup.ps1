# Windows PowerShell 5.1 guest setup: one new bounded file, never an existing disk.
param([bool]$GuestInvocation=$false,[ValidateSet(32,512)][int]$SizeMiB=32)
$ErrorActionPreference='Stop'
$root=if($GuestInvocation){'C:\ProgramData\DiskEd\qualification'}else{$PSScriptRoot}
$environmentVerified=$false
$scratch=Join-Path $root 'scratch'
$image=Join-Path $scratch 'disked-proof.vhd'
$nonce=[guid]::NewGuid().ToString('N')
$capacity=[long]$SizeMiB*1MB
$uuid=$null;$diskId=$null;$created=$false;$attached=$false;$workersStopped=$false
$result=[ordered]@{schema='org.disked.guest-capacity-setup/1';started_at=[DateTime]::UtcNow.ToString('o');status='not_run';image=$image;size_mib=$SizeMiB;image_removed=$false}
function Plain([string]$Path){
    $item=Get-Item -LiteralPath $Path -Force
    while($item){if($item.Attributes -band [IO.FileAttributes]::ReparsePoint){throw 'Linked setup path.'};$item=if($item.PSIsContainer){$item.Parent}else{$item.Directory}}
}
function Footer {
    Plain $image
    if((Get-Item -LiteralPath $image).Length -ne ($capacity+512)){throw 'Unexpected fixed VHD length.'}
    $file=[IO.File]::Open($image,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
    try{$null=$file.Seek(-512,[IO.SeekOrigin]::End);$bytes=New-Object byte[] 512;if($file.Read($bytes,0,512)-ne512){throw 'Short VHD footer.'}}finally{$file.Dispose()}
    if([Text.Encoding]::ASCII.GetString($bytes,0,8)-ne'conectix' -or $bytes[60]-ne0 -or $bytes[61]-ne0 -or $bytes[62]-ne0 -or $bytes[63]-ne2){throw 'Not a fixed VHD.'}
    $sum=0L;$checksum=0L
    for($i=0;$i-lt512;$i++){if($i-lt64-or$i-ge68){$sum+=$bytes[$i]}}
    for($i=64;$i-lt68;$i++){$checksum=($checksum-shl8)-bor$bytes[$i]}
    if($checksum-ne([uint32]::MaxValue-$sum)){throw 'Invalid VHD footer checksum.'}
    $size=0L;for($i=48;$i-lt56;$i++){$size=($size-shl8)-bor$bytes[$i]};if($size-ne$capacity){throw 'Unexpected virtual capacity.'}
    $id=([BitConverter]::ToString($bytes,68,16)).Replace('-','')
    if($uuid -and $id-ne$uuid){throw 'VHD identity changed.'}
    return $id
}
function BoundDisk {
    $null=Footer
    $mounted=Get-DiskImage -ImagePath $image
    if(-not$mounted.Attached){throw 'Owned image is not attached.'}
    $disk=$mounted|Get-Disk
    if($disk.IsBoot -or $disk.IsSystem -or $disk.Size-ne$capacity -or $disk.BusType-notin@('File Backed Virtual','Virtual')){throw 'Wrong owned-image disk.'}
    if($diskId -and $disk.UniqueId-ne$diskId){throw 'Disk identity changed.'}
    return $disk
}
try{
    if($root-ne'C:\ProgramData\DiskEd\qualification' -or [Net.Dns]::GetHostName()-ne'BlackGlass-HyperV' -or
        [Security.Principal.WindowsIdentity]::GetCurrent().Name-ne'BLACKGLASS-HYPE\Agents' -or
        (Get-ItemProperty 'HKLM:\HARDWARE\DESCRIPTION\System\BIOS').SystemProductName-ne'Virtual Machine'){throw 'Wrong execution environment.'}
    $environmentVerified=$true
    Plain $root
    if(([IO.DriveInfo]::new('C:\')).AvailableFreeSpace-lt20GB){throw 'Guest OS reserve missing.'}
    if(Test-Path -LiteralPath $scratch){throw 'Existing scratch; inspect before reuse.'}
    $manifest=Get-Content -LiteralPath (Join-Path $root 'source-manifest.json') -Raw|ConvertFrom-Json
    foreach($entry in $manifest.files){if((Get-FileHash -LiteralPath (Join-Path $root $entry.path) -Algorithm SHA256).Hash-ne$entry.sha256){throw 'Transferred source changed.'}}
    New-Item -ItemType Directory -Path $scratch|Out-Null
    [IO.File]::WriteAllText((Join-Path $scratch 'owner.json'),('{"nonce":"'+$nonce+'"}'))
    $commands='create vdisk file="'+$image+'" type=fixed maximum='+$SizeMiB+"`r`nexit`r`n"
    [IO.File]::WriteAllText((Join-Path $scratch 'create.txt'),$commands,[Text.Encoding]::ASCII)
    $created=$true
    $diskpart=@(& "$env:WINDIR\System32\diskpart.exe" /s (Join-Path $scratch 'create.txt') 2>&1)
    $result.diskpart_output=($diskpart|ForEach-Object ToString)-join"`n"
    if($LASTEXITCODE-ne0){throw 'Fixed VHD creation failed.'}
    $uuid=Footer;$result.image_uuid=$uuid
    $expectedUuid=$uuid
    try{
        $uuid='not-the-owned-image';$rejected=$false
        try{$null=Footer}catch{if($_.Exception.Message-eq'VHD identity changed.'){$rejected=$true}else{throw}}
        if(-not$rejected){throw 'Image identity guard did not reject a stale expected UUID.'}
        $result.image_identity_guard_verified=$true
    }finally{$uuid=$expectedUuid}
    $python='C:\ProgramData\DiskEd\python314\python.exe'
    $profileNames=@(1..3|ForEach-Object{'org.disked.worker.'+[guid]::NewGuid().ToString('N')})
    $config=@{nonce=$nonce;image_uuid=$uuid;size_mib=$SizeMiB;profile_names=$profileNames;actor_sid=[Security.Principal.WindowsIdentity]::GetCurrent().User.Value}
    [IO.File]::WriteAllText((Join-Path $scratch 'attach-config.json'),($config|ConvertTo-Json))
    $backingAcl=(Get-Acl -LiteralPath $image).Sddl
    $nativePreference=$ErrorActionPreference
    try{
        $ErrorActionPreference='Continue'
        $attachLog=@(& $python -B (Join-Path $root 'attach-image.py') 2>&1)
        $attachCode=$LASTEXITCODE
    }finally{$ErrorActionPreference=$nativePreference}
    $attached=(Get-DiskImage -ImagePath $image).Attached
    if($attachCode-ne0 -or -not$attached){throw ('Owned image attachment failed: '+(($attachLog|ForEach-Object ToString)-join"`n"))}
    $attach=Get-Content -LiteralPath (Join-Path $scratch 'attach-result.json') -Raw|ConvertFrom-Json
    $result.attachment=$attach
    $result.backing_acl_unchanged=((Get-Acl -LiteralPath $image).Sddl-eq$backingAcl)
    if(-not$result.backing_acl_unchanged){throw 'Backing file ACL changed.'}
    $disk=BoundDisk
    if($disk.PartitionStyle-ne'RAW'){throw 'New image was not RAW.'}
    if($disk.IsOffline){$disk|Set-Disk -IsOffline $false}
    (BoundDisk)|Initialize-Disk -PartitionStyle MBR|Out-Null
    $disk=BoundDisk;$diskId=$disk.UniqueId;$result.disk_unique_id=$diskId
    $expectedDiskId=$diskId
    try{
        $diskId='not-the-owned-disk';$rejected=$false
        try{$null=BoundDisk}catch{if($_.Exception.Message-eq'Disk identity changed.'){$rejected=$true}else{throw}}
        if(-not$rejected){throw 'Disk identity guard did not reject a stale expected ID.'}
        $result.disk_identity_guard_verified=$true
    }finally{$diskId=$expectedDiskId}
    $partition=$disk|New-Partition -UseMaximumSize
    $fresh=BoundDisk
    $parts=@($fresh|Get-Partition)
    if($parts.Count-ne1 -or $parts[0].Offset-ne$partition.Offset -or $parts[0].Size-ne$partition.Size){throw 'Partition binding changed.'}
    $parts[0]|Format-Volume -FileSystem NTFS -AllocationUnitSize 4096 -NewFileSystemLabel 'DiskEdProof' -Confirm:$false|Out-Null
    $used=@((Get-Volume).DriveLetter)+@((Get-PSDrive -PSProvider FileSystem).Name)
    $letter=@('R','S','T','U','V','W','X','Y','Z')|Where-Object{$_-notin$used}|Select-Object -First 1
    if(-not$letter){throw 'No unused letter.'}
    $parts=@((BoundDisk)|Get-Partition)
    $parts[0]|Add-PartitionAccessPath -AccessPath "${letter}:\"
    $volume=Get-Volume -DriveLetter $letter
    if($volume.FileSystem-ne'NTFS' -or $volume.Size-gt$capacity -or $volume.FileSystemLabel-ne'DiskEdProof'){throw 'Unexpected proof volume.'}
    # Packages need read/traverse access to the newly formatted volume. Writes
    # remain granted only to the unique worker SID in its owned work directory.
    $volumeRoot="${letter}:\"
    $acl=Get-Acl -LiteralPath $volumeRoot
    $readRule=[Security.AccessControl.FileSystemAccessRule]::new([Security.Principal.SecurityIdentifier]::new('S-1-15-2-1'),[Security.AccessControl.FileSystemRights]::ReadAndExecute,[Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit',[Security.AccessControl.PropagationFlags]::None,[Security.AccessControl.AccessControlType]::Allow)
    $acl.AddAccessRule($readRule);Set-Acl -LiteralPath $volumeRoot -AclObject $acl
    $work="${letter}:\work";New-Item -ItemType Directory -Path $work|Out-Null
    $state=@{drive="${letter}:\";work=$work;image=$image;size_mib=$SizeMiB;image_uuid=$uuid;nonce=$nonce;volume_unique_id=$volume.UniqueId;profile_names=$profileNames;profile_sids=@($attach.profiles|ForEach-Object sid)}
    [IO.File]::WriteAllText((Join-Path $scratch 'state.json'),($state|ConvertTo-Json))
    $python='C:\ProgramData\DiskEd\python314\python.exe'
    $nativePreference=$ErrorActionPreference
    try{
        $ErrorActionPreference='Continue'
        $log=@(& $python -B (Join-Path $root 'tools\workspace.py') run -- $python -B (Join-Path $root 'guest-proof.py') 2>&1)
        $code=$LASTEXITCODE
    }finally{$ErrorActionPreference=$nativePreference}
    $result.runner_output=($log|ForEach-Object ToString)-join"`n";$result.runner_exit=$code
    $runner=($log|Select-Object -Last 1)|ConvertFrom-Json
    $workersStopped=($runner.workspace_removed-eq$true)
    if($code-ne0 -or -not$workersStopped){throw 'Guest proof or owned cleanup failed.'}
    $result.status='pass'
}catch{$result.status='fail';$result.error=$_.Exception.Message}
finally{
    try{
        if($attached){
            if(-not$workersStopped -and $result.Contains('runner_exit')){throw 'Worker/profile cleanup not established; preserve the small image.'}
            $null=BoundDisk
            Dismount-DiskImage -ImagePath $image|Out-Null
            $attached=$false
        }
        if($created -and(Test-Path -LiteralPath $image)){
            $null=Footer
            if((Get-Content -LiteralPath (Join-Path $scratch 'owner.json') -Raw|ConvertFrom-Json).nonce-ne$nonce){throw 'Scratch ownership changed.'}
            Remove-Item -LiteralPath $image
            $result.image_removed=-not(Test-Path -LiteralPath $image)
        }
    }catch{$result.status='fail';$result.cleanup_error=$_.Exception.Message}
    $result.finished_at=[DateTime]::UtcNow.ToString('o')
    if(-not$GuestInvocation -or $environmentVerified){
        [IO.File]::WriteAllText((Join-Path $root 'setup-result.json'),(($result|ConvertTo-Json -Depth 6)-replace"`r`n","`n")+"`n",[Text.UTF8Encoding]::new($false))
    }
}
if(-not$GuestInvocation -and $result.status-ne'pass'){exit 1}
