# One stopped guest campaign only; run in the existing PowerShell Direct session.
$ErrorActionPreference='Stop'
$root='C:\ProgramData\DiskEd\qualification'
$nonce='8fa6e3000a5f4181b5cd9ea11e83a7c2'
if([Security.Principal.WindowsIdentity]::GetCurrent().Name-ne'BLACKGLASS-HYPE\Agents'-or
   [Net.Dns]::GetHostName()-ne'BlackGlass-HyperV'-or
   (Get-ItemProperty 'HKLM:\HARDWARE\DESCRIPTION\System\BIOS').SystemProductName-ne'Virtual Machine'){
    throw 'Exact authorized guest coordinator required'
}
function Plain([string]$Path){
    $item=Get-Item -LiteralPath $Path -Force
    while($item){
        if($item.Attributes-band[IO.FileAttributes]::ReparsePoint){throw 'Linked recovery path'}
        $item=if($item.PSIsContainer){$item.Parent}else{$item.Directory}
    }
}
Plain $root
$state=[IO.File]::ReadAllText("$root\scratch\state.json")|ConvertFrom-Json
$owner=[IO.File]::ReadAllText("$root\scratch\owner.json")|ConvertFrom-Json
$actor=[IO.File]::ReadAllText("$root\scratch\ordinary-actor.json")|ConvertFrom-Json
$setup=[IO.File]::ReadAllText("$root\setup-result.json")|ConvertFrom-Json
$ack=[IO.File]::ReadAllText("$root\stop-acknowledged.json")|ConvertFrom-Json
$grants=[IO.File]::ReadAllText("$root\recovered-grants.json")|ConvertFrom-Json
$retired=[IO.File]::ReadAllText("$root\source-retired.json")|ConvertFrom-Json
if($state.nonce-ne$nonce-or$owner.nonce-ne$nonce-or$actor.nonce-ne$nonce-or
   $ack.nonce-ne$nonce-or-not$ack.owned_job_processes_retired-or$ack.command-ne'build'-or
   $grants.nonce-ne$nonce-or$grants.status-ne'pass'-or
   $grants.source_revision-ne'59a39c93b4f3d8f2edfb915a8e15deb1759af8b1'-or
   $retired.nonce-ne$nonce-or-not$retired.source_removed-or[IO.Directory]::Exists("$root\source")-or
   -not$setup.interactive_dispatch.quiescent){throw 'Prior recovery/quiescence differs'}
foreach($key in @('object_namespace','window_station','crypto_device','null_build','null_user')){
    if($actor.PSObject.Properties[$key]-and$actor.$key.phase-ne'retired'){throw 'Owned grant retirement incomplete'}
}
if($actor.name-ne'DiskEdTest-8fa6e300'-or$actor.sid-ne'S-1-5-21-385394198-2603589104-1765785984-1157'){
    throw 'Disposable account identity differs'
}
$profile='C:\Users\'+$actor.name
$profileKey='HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$actor.sid
if((Test-Path -LiteralPath $profile)-or(Test-Path -LiteralPath $profileKey)){
    throw 'Unexpected disposable profile;preserve for review'
}
$account=Get-LocalUser -Name $actor.name -ErrorAction SilentlyContinue
if($account-and($account.SID.Value-ne$actor.sid-or$account.Description-ne('DiskEd test '+$nonce))){
    throw 'Account ownership changed'
}
foreach($name in $state.profile_names){
    if($name-notmatch'^org\.disked\.worker\.[0-9a-f]{32}$'){throw 'Profile name differs'}
    $path=Join-Path $env:LOCALAPPDATA ('Packages\'+$name)
    if(Test-Path -LiteralPath $path){throw 'Worker profile mapping remains;preserve media'}
}
$image=[IO.Path]::GetFullPath("$root\scratch\disked-proof.vhd")
if($state.image-ne$image-or$state.size_mib-ne512-or$setup.image_uuid-ne$state.image_uuid){throw 'Media identity differs'}
$capacity=[long]512*1MB
$uuid=[string]$state.image_uuid
function Footer {
    Plain $image
    if((Get-Item -LiteralPath $image).Length-ne($capacity+512)){throw 'Unexpected fixed VHD length'}
    $file=[IO.File]::Open($image,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
    try{
        $null=$file.Seek(-512,[IO.SeekOrigin]::End);$bytes=New-Object byte[] 512
        if($file.Read($bytes,0,512)-ne512){throw 'Short VHD footer'}
    }finally{$file.Dispose()}
    if([Text.Encoding]::ASCII.GetString($bytes,0,8)-ne'conectix'-or
       $bytes[60]-ne0-or$bytes[61]-ne0-or$bytes[62]-ne0-or$bytes[63]-ne2){throw 'Not a fixed VHD'}
    $sum=0L;$checksum=0L
    for($i=0;$i-lt512;$i++){if($i-lt64-or$i-ge68){$sum+=$bytes[$i]}}
    for($i=64;$i-lt68;$i++){$checksum=($checksum-shl8)-bor$bytes[$i]}
    if($checksum-ne([uint32]::MaxValue-$sum)){throw 'VHD footer checksum differs'}
    $size=0L;for($i=48;$i-lt56;$i++){$size=($size-shl8)-bor$bytes[$i]}
    if($size-ne$capacity-or([BitConverter]::ToString($bytes,68,16)).Replace('-','')-ne$uuid){
        throw 'VHD capacity or UUID differs'
    }
}
if(Test-Path -LiteralPath $image){
    $null=Footer
    $mounted=Get-DiskImage -ImagePath $image
    if(-not$mounted.Attached){throw 'Expected owned attachment absent;inspect before reuse'}
    $disk=$mounted|Get-Disk
    if($disk.IsBoot-or$disk.IsSystem-or$disk.Size-ne$capacity-or
       $disk.BusType-notin@('File Backed Virtual','Virtual')-or$disk.UniqueId-ne$setup.disk_unique_id){
        throw 'Owned virtual disk binding differs'
    }
    if($state.drive-notmatch'^[R-Z]:\\$'){throw 'Scratch drive differs'}
    $letter=$state.drive.Substring(0,1)
    $volume=Get-Volume -DriveLetter $letter
    $partition=Get-Partition -DriveLetter $letter
    if($volume.UniqueId-ne$state.volume_unique_id-or$volume.FileSystem-ne'NTFS'-or
       $volume.FileSystemLabel-ne'DiskEdProof'-or$partition.DiskNumber-ne$disk.Number){
        throw 'Owned volume/partition binding differs'
    }
    Dismount-DiskImage -ImagePath $image|Out-Null
    $null=Footer
    Remove-Item -LiteralPath $image
}elseif(Get-Volume -UniqueId $state.volume_unique_id -ErrorAction SilentlyContinue){
    throw 'Owned volume survives missing backing path;preserve state'
}
if(Test-Path -LiteralPath $image){throw 'Owned image removal incomplete'}
if($account){Remove-LocalUser -SID ([Security.Principal.SecurityIdentifier]::new($actor.sid))}
if(Get-LocalUser -Name $actor.name -ErrorAction SilentlyContinue){throw 'Disposable account remains'}
$actor.phase='retired'
$actor|Add-Member -NotePropertyName profile_absent -NotePropertyValue $true -Force
[IO.File]::WriteAllText("$root\scratch\ordinary-actor.json",($actor|ConvertTo-Json -Depth 8)+"`n",[Text.UTF8Encoding]::new($false))
$setup.image_removed=$true
$setup|Add-Member -NotePropertyName actor_removed -NotePropertyValue $true -Force
$setup|Add-Member -NotePropertyName actor_profile_absent -NotePropertyValue $true -Force
$recovery=[ordered]@{status='pass';scope='Owned cleanup recovery only;original native result remains interrupted';nonce=$nonce;
    image_uuid=$uuid;image_removed=$true;actor_removed=$true;actor_profile_absent=$true;
    worker_profile_mappings_absent=$true;source_removed=$true;unrelated_processes_killed=$false;
    grants_sha256=(Get-FileHash -LiteralPath "$root\recovered-grants.json" -Algorithm SHA256).Hash.ToLowerInvariant();
    observed_at=[DateTime]::UtcNow.ToString('o')}
$setup|Add-Member -NotePropertyName cleanup_recovery -NotePropertyValue $recovery -Force
[IO.File]::WriteAllText("$root\setup-result.json",($setup|ConvertTo-Json -Depth 8)+"`n",[Text.UTF8Encoding]::new($false))
$recovery|ConvertTo-Json -Depth 4
