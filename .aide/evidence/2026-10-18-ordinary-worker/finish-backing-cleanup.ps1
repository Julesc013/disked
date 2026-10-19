# Run85 only. All three temporary grants must already have retired successfully.
$ErrorActionPreference='Stop'
$repo='D:\Projects\DiskEd\disked'
$s=& (Join-Path $repo 'tools\connect-vm.ps1') -OpenSession
$record=@{status='running';scope='Exact run85 forced-interruption recovery;no product qualification';observed_at=[DateTime]::UtcNow.ToString('o')}
try {
    $result=Invoke-Command -Session $s -ScriptBlock {
        $ErrorActionPreference='Stop'
        $r='C:\ProgramData\DiskEd\qualification';$nonce='69df43625e864cd08fd0311fac9ceaeb'
        if($env:COMPUTERNAME-ne'BLACKGLASS-HYPE'-or[Security.Principal.WindowsIdentity]::GetCurrent().Name-ne'BLACKGLASS-HYPE\Agents'){throw 'Exact guest required.'}
        $state=Get-Content -LiteralPath "$r\scratch\state.json" -Raw|ConvertFrom-Json
        $a=Get-Content -LiteralPath "$r\scratch\ordinary-actor.json" -Raw|ConvertFrom-Json
        if($state.nonce-ne$nonce-or$a.nonce-ne$nonce-or$a.sid-ne'S-1-5-21-385394198-2603589104-1765785984-1086'-or$state.image-ne"$r\scratch\disked-proof.vhd"-or$state.image_uuid-ne'E1386455CCC8B1499A9E38441F989CB5'){throw 'Ownership changed.'}
        foreach($key in 'null_build','object_namespace','window_station'){if($a.$key.phase-ne'retired'){throw 'Grant retirement incomplete.'}}
        if(Get-ScheduledTask -TaskName ('DiskEd-Native-Interactive-'+$nonce) -ErrorAction SilentlyContinue){throw 'Original task remains.'}
        if(Get-ScheduledTask -TaskName ('DiskEd-Recovery-'+$nonce) -ErrorAction SilentlyContinue){throw 'Recovery task remains.'}
        if(Test-Path -LiteralPath "$r\interactive-input.xml"){throw 'Credential remains.'}
        if(@(Get-CimInstance Win32_Process|Where-Object {$_.CommandLine-match'DiskEd\\qualification|R:\\work'}).Count){throw 'Owned worker remains.'}
        $manifest=Get-Content -LiteralPath "$r\source-manifest.json" -Raw|ConvertFrom-Json
        foreach($entry in $manifest.files){if((Get-FileHash -LiteralPath (Join-Path $r $entry.path) -Algorithm SHA256).Hash-ne$entry.sha256){throw 'Transferred helper changed.'}}
        $python='C:\ProgramData\DiskEd\python314\python.exe'
        & $python -B "$r\guest-source.py" retire
        if($LASTEXITCODE-ne0){throw 'Exact owned source retirement failed.'}
        $sourceRetired=Get-Content -LiteralPath "$r\source-retired.json" -Raw|ConvertFrom-Json
        if(-not$sourceRetired.source_removed-or$sourceRetired.nonce-ne$nonce){throw 'Source retirement incomplete.'}
        # The original managed coordinator was force-terminated. Its existing
        # runner recovers only its root-bound stale workspace/profile journal.
        $lines=@(& $python -B "$r\tools\workspace.py" run -- $python -B -c pass)
        if($LASTEXITCODE-ne0){throw 'Stale coordinator/profile cleanup failed.'}
        $runner=($lines|Select-Object -Last 1)|ConvertFrom-Json
        if(-not$runner.workspace_removed-or$runner.status-ne'pass'){throw 'Coordinator cleanup unverified.'}
        $u=Get-LocalUser -Name $a.name
        if($u.SID.Value-ne$a.sid-or$u.Description-ne('DiskEd test '+$nonce)){throw 'Actor changed.'}
        if((Test-Path -LiteralPath ('C:\Users\'+$a.name))-or(Test-Path -LiteralPath ('HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\'+$a.sid))){throw 'Unexpected actor profile.'}
        Remove-LocalUser -SID ([Security.Principal.SecurityIdentifier]::new($a.sid))
        if(Get-LocalUser -Name $a.name -ErrorAction SilentlyContinue){throw 'Actor removal incomplete.'}
        $image=$state.image
        $file=Get-Item -LiteralPath $image
        if(($file.Attributes-band[IO.FileAttributes]::ReparsePoint)-or$file.Length-ne(512MB+512)){throw 'Media length/type changed.'}
        $stream=[IO.File]::Open($image,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::ReadWrite)
        try{$null=$stream.Seek(-512,[IO.SeekOrigin]::End);$footer=New-Object byte[] 512;if($stream.Read($footer,0,512)-ne512){throw 'Short footer.'}}finally{$stream.Dispose()}
        if([Text.Encoding]::ASCII.GetString($footer,0,8)-ne'conectix'-or([BitConverter]::ToString($footer,68,16)).Replace('-','')-ne$state.image_uuid){throw 'Media UUID changed.'}
        $media=Get-DiskImage -ImagePath $image;$disk=$media|Get-Disk
        if(-not$media.Attached-or$disk.IsBoot-or$disk.IsSystem-or$disk.Size-ne512MB-or$disk.UniqueId-ne'60022480E1386455CCC838441F989CB5'-or$disk.BusType-notin@('Virtual','File Backed Virtual')){throw 'Owned attached disk identity changed.'}
        Dismount-DiskImage -ImagePath $image|Out-Null
        if((Get-DiskImage -ImagePath $image).Attached){throw 'Media still attached.'}
        Remove-Item -LiteralPath $image
        if(Test-Path -LiteralPath $image){throw 'Media deletion incomplete.'}
        # The remaining small transfer/receipt tree has one checked, fixed root.
        # Refuse links and unexpected bulk before invoking existing owned cleanup.
        $items=@(Get-ChildItem -LiteralPath $r -Recurse -Force)
        if($items.Count-gt100){throw 'Unexpected remaining entries.'}
        foreach($item in $items){if($item.Attributes-band[IO.FileAttributes]::ReparsePoint){throw 'Linked metadata.'};if(-not$item.FullName.StartsWith($r+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Metadata escaped root.'}}
        $code="import importlib.util;from pathlib import Path;r=Path('C:/ProgramData/DiskEd/qualification');s=importlib.util.spec_from_file_location('owned_cleanup',r/'tools/workspace.py');m=importlib.util.module_from_spec(s);s.loader.exec_module(m);m.remove_owned_work(r,r.parent,'qualification')"
        & $python -B -c $code
        if($LASTEXITCODE-ne0-or(Test-Path -LiteralPath $r)){throw 'Owned metadata cleanup incomplete.'}
        [pscustomobject]@{status='pass';nonce=$nonce;image_uuid=$state.image_uuid;source_removed=$true;image_removed=$true;actor_removed=$true;actor_profile_absent=$true;owned_coordinator_profiles_retired=$true;qualification_root_absent=$true;credential_absent=$true;tasks_absent=$true;unrelated_processes_killed=$false;guest_free_bytes=([IO.DriveInfo]::new('C:\')).AvailableFreeSpace;runner=$runner}
    }
    $record.status='pass';$record.cleanup=$result|Select-Object * -ExcludeProperty PSComputerName,RunspaceId,PSShowComputerName
    $vm=Get-VM -Id '3ebbe558-91b9-435b-96e4-0c8199bd38ad'
    $backing=@(Get-VMHardDiskDrive -VM $vm)
    if($backing.Count-ne1){throw 'Changed backing topology.'}
    $record.host_backing_end_bytes=(Get-Item -LiteralPath $backing[0].Path).Length
    $record.host_free_bytes=([IO.DriveInfo]::new('D:\')).AvailableFreeSpace
}catch{$record.status='fail';$record.error=$_.Exception.Message;throw}
finally{
    $record.finished_at=[DateTime]::UtcNow.ToString('o')
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'eighty-fifth-cleanup-recovery.json'),($record|ConvertTo-Json -Depth 8).Replace("`r`n","`n")+"`n",[Text.UTF8Encoding]::new($false))
    Remove-PSSession -Session $s
    $record|ConvertTo-Json -Depth 8
}
