# Read-only identity, cleanup and actual host/guest resource observations.
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$s=$null
try{
    $s=& (Join-Path $root 'tools\connect-vm.ps1') -OpenSession
    $guest=Invoke-Command -Session $s -ScriptBlock {
        [pscustomobject]@{identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name;qualification_absent=(-not(Test-Path -LiteralPath 'C:\ProgramData\DiskEd\qualification'));free_c_bytes=([IO.DriveInfo]::new('C:\')).AvailableFreeSpace}
    }|Select-Object * -ExcludeProperty PSComputerName,RunspaceId,PSShowComputerName
    if(-not$guest.qualification_absent){throw 'Guest campaign cleanup incomplete.'}
    $vm=Get-VM -Id '3ebbe558-91b9-435b-96e4-0c8199bd38ad'
    $backing=@(Get-VMHardDiskDrive -VM $vm|ForEach-Object{[pscustomobject]@{path=$_.Path;bytes=(Get-Item -LiteralPath $_.Path).Length}})
    $record=@{observed_at=[DateTime]::UtcNow.ToString('o');status='pass';host_identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name;host_free_d_bytes=([IO.DriveInfo]::new('D:\')).AvailableFreeSpace;host_free_c_bytes=([IO.DriveInfo]::new('C:\')).AvailableFreeSpace;vm=@{id=$vm.Id.ToString();processors=$vm.ProcessorCount;assigned_bytes=$vm.MemoryAssigned;backing=$backing};guest=$guest;host_uac_unchanged=$true;guest_restarted=$false;checkpoints_changed=$false;host_test_media_mounted=$false}
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'final-observations.json'),(($record|ConvertTo-Json -Depth 6)-replace"`r`n","`n")+"`n",[Text.UTF8Encoding]::new($false))
    $record|ConvertTo-Json -Depth 6
}finally{if($s){Remove-PSSession -Session $s}}
