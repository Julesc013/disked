# Read-only final observations through the primary guest account.
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$session=$null
try{
    $session=& (Join-Path $root 'tools\connect-vm.ps1') -OpenSession
    $guest=Invoke-Command -Session $session -ScriptBlock {
        $members=@(Get-LocalGroupMember -SID 'S-1-5-32-544'|ForEach-Object {$_.SID.Value})
        $accounts=@(foreach($name in 'Agents','Codex'){
            $user=Get-LocalUser -Name $name
            [pscustomobject]@{name=$name;enabled=$user.Enabled;administrator=($user.SID.Value-in$members);password_required=$user.PasswordRequired;password_expires=$user.PasswordExpires;password_last_set=$user.PasswordLastSet.ToUniversalTime().ToString('o');profile_preserved=(Test-Path -LiteralPath "C:\Users\$name")}
        })
        $runtime=@(Get-ChildItem -LiteralPath 'C:\ProgramData\DiskEd\python314' -Recurse -File)
        if($runtime.Count-gt1024){throw 'Unexpected runtime growth.'}
        $temps=@(Get-ChildItem -LiteralPath ([IO.Path]::GetTempPath()) -Directory -Filter 'disked-work-*'|Select-Object -ExpandProperty Name)
        [pscustomobject]@{identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name;accounts=$accounts;guest_uac=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System').EnableLUA;qualification_absent=(-not(Test-Path -LiteralPath 'C:\ProgramData\DiskEd\qualification'));runtime_transfer_absent=(-not(Test-Path -LiteralPath 'C:\ProgramData\DiskEd\runtime-transfer'));guest_free_c_bytes=([IO.DriveInfo]::new('C:\')).AvailableFreeSpace;runtime_files=$runtime.Count;runtime_retained_bytes=($runtime|Measure-Object -Property Length -Sum).Sum;disked_temp_directory_names=$temps;codex_login_performed=$false;jules_guest_used=$false}
    }|Select-Object * -ExcludeProperty PSComputerName,RunspaceId,PSShowComputerName
    if(-not$guest.qualification_absent -or -not$guest.runtime_transfer_absent -or $guest.disked_temp_directory_names.Count){throw 'Guest disposable cleanup incomplete.'}
    $vm=Get-VM -Id '3ebbe558-91b9-435b-96e4-0c8199bd38ad'
    $backing=@(Get-VMHardDiskDrive -VM $vm|ForEach-Object{[pscustomobject]@{path=$_.Path;file_bytes=(Get-Item -LiteralPath $_.Path).Length}})
    $record=[ordered]@{observed_at=[DateTime]::UtcNow.ToString('o');status='pass';host_identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name;host_uac=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System').EnableLUA;host_free_c_bytes=([IO.DriveInfo]::new('C:\')).AvailableFreeSpace;host_free_d_bytes=([IO.DriveInfo]::new('D:\')).AvailableFreeSpace;vm=@{id=$vm.Id.ToString();state=$vm.State.ToString();processors=$vm.ProcessorCount;assigned_bytes=$vm.MemoryAssigned;minimum_bytes=$vm.MemoryMinimum;maximum_bytes=$vm.MemoryMaximum;checkpoints=@(Get-VMSnapshot -VM $vm|ForEach-Object {$_.Id.ToString()});backing=$backing};guest=$guest;native_product_tests_run=$false;host_test_media_mounted=$false}
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'final-observations.json'),(($record|ConvertTo-Json -Depth 7)-replace"`r`n","`n")+"`n",[Text.UTF8Encoding]::new($false))
    [pscustomobject]@{status=$record.status;guest_identity=$guest.identity;qualification_absent=$guest.qualification_absent;runtime_retained_bytes=$guest.runtime_retained_bytes;host_uac=$record.host_uac;host_free_d_bytes=$record.host_free_d_bytes}|ConvertTo-Json
}finally{if($session){Remove-PSSession -Session $session}}
