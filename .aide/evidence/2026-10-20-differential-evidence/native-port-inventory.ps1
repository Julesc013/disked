#Requires -Version 7.0
# Read-only inventory through the already-authorized Agents connection.
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
if(-not$env:DISKED_WORK_ROOT){throw 'Managed workspace required.'}
$session=$null
$result=[ordered]@{status='not_run';scope='Read-only guest/tool availability;no worker admission or native test';guest_modified=$false;host_media_mounted=$false}
try{
    $result.host_identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
    $session=& (Join-Path $root 'tools\connect-vm.ps1') -OpenSession
    $result.guest=Invoke-Command -Session $session -ScriptBlock {
        if([Security.Principal.WindowsIdentity]::GetCurrent().Name-ne'BLACKGLASS-HYPE\Agents'){throw 'Unexpected guest account.'}
        $fixed=@{
            python='C:\ProgramData\DiskEd\python314\python.exe'
            compiler='C:\BuildTools\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\cl.exe'
            linker='C:\BuildTools\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\link.exe'
            dumpbin='C:\BuildTools\VC\Tools\MSVC\14.44.35207\bin\Hostx64\x64\dumpbin.exe'
        }
        $tools=@(foreach($name in $fixed.Keys|Sort-Object){
            $path=$fixed[$name];$exists=Test-Path -LiteralPath $path -PathType Leaf
            $row=[ordered]@{name=$name;path=$path;exists=$exists}
            if($exists){
                $file=Get-Item -LiteralPath $path
                if($file.Length-gt64MB-or($file.Attributes-band[IO.FileAttributes]::ReparsePoint)){throw 'Unexpected tool form/size.'}
                $row.bytes=$file.Length;$row.sha256=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
                $row.file_version=$file.VersionInfo.FileVersion
            }
            [pscustomobject]$row
        })
        $references=@(foreach($name in 'sfdisk.exe','sgdisk.exe','gdisk.exe','fdisk.exe','wsl.exe'){
            $command=Get-Command -Name $name -CommandType Application -ErrorAction SilentlyContinue|Select-Object -First 1
            [pscustomobject]@{name=$name;path=if($command){$command.Source}else{$null};available=[bool]$command}
        })
        [pscustomobject]@{
            identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name
            hostname=[Net.Dns]::GetHostName()
            os_build=[Environment]::OSVersion.Version.ToString()
            pointer_bits=[IntPtr]::Size*8
            guest_free_c_bytes=([IO.DriveInfo]::new('C:\')).AvailableFreeSpace
            qualification_absent=(-not(Test-Path -LiteralPath 'C:\ProgramData\DiskEd\qualification'))
            runtime_transfer_absent=(-not(Test-Path -LiteralPath 'C:\ProgramData\DiskEd\runtime-transfer'))
            tools=$tools;references=$references
        }
    }|Select-Object * -ExcludeProperty PSComputerName,RunspaceId,PSShowComputerName
    if($result.guest.hostname-ne'BlackGlass-HyperV'){throw 'Unexpected guest host.'}
    $vm=Get-VM -Id '3ebbe558-91b9-435b-96e4-0c8199bd38ad'
    $result.vm=[ordered]@{id=$vm.Id.ToString();state=$vm.State.ToString();processors=$vm.ProcessorCount;assigned_bytes=$vm.MemoryAssigned;
        backing=@(Get-VMHardDiskDrive -VM $vm|ForEach-Object{[pscustomobject]@{path=$_.Path;file_bytes=(Get-Item -LiteralPath $_.Path).Length}})}
    $result.host_free_c_bytes=([IO.DriveInfo]::new('C:\')).AvailableFreeSpace
    $result.host_free_d_bytes=([IO.DriveInfo]::new('D:\')).AvailableFreeSpace
    $result.status='pass'
}catch{$result.status='fail';$result.error=$_.Exception.Message;throw}
finally{
    if($session){Remove-PSSession -Session $session}
    $result.observed_at=[DateTime]::UtcNow.ToString('o')
    $body=(($result|ConvertTo-Json -Depth 9)-replace"`r`n","`n")+"`n"
    if([Text.Encoding]::UTF8.GetByteCount($body)-gt32768){throw 'Inventory output bound.'}
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'native-port-inventory.json'),$body,[Text.UTF8Encoding]::new($false))
}
