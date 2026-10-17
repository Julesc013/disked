#Requires -Version 7.0
<#!
Temporary setup only: one NEW blank fixed VHDX, never a physical source.
The unelevated controller must own/retire its workers before writing release.json.
This helper accepts no commands, disk numbers, image paths or arbitrary sizes.
#>
[CmdletBinding()]
param([ValidateSet(32,512)][int]$SizeMiB = 32)
$ErrorActionPreference = 'Stop'
$scratchRoot = 'D:\Projects\DiskEd\scratch'
$imagePath = Join-Path $scratchRoot 'disked-work.vhdx'
$statePath = Join-Path $scratchRoot 'state.json'
$releasePath = Join-Path $scratchRoot 'release.json'
$ownerPath = Join-Path $scratchRoot 'owner.json'
$repoRoot = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$createdImage = $false
$attachedImage = $false
$createdOwner = $false
$failure = $null
$state = $null
$setupMutex = $null
$ownsSetupMutex = $false

function Write-State {
    param($Value)
    $text = $Value | ConvertTo-Json -Depth 8
    if ([Text.Encoding]::UTF8.GetByteCount($text) -gt 16384) { throw 'Oversized setup state' }
    [IO.File]::WriteAllText($statePath, $text + "`n", [Text.UTF8Encoding]::new($false))
}

function Assert-PlainPath {
    param([string]$Path)
    $item = Get-Item -LiteralPath $Path -Force
    while ($null -ne $item) {
        if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw "Linked path: $($item.FullName)" }
        $item = if ($item -is [IO.DirectoryInfo]) { $item.Parent } else { $item.Directory }
    }
}

try {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = [Security.Principal.WindowsPrincipal]::new($identity)
    if ($identity.Name -ne 'BLACKGLASS-WIN1\Jules') {
        throw 'This fixed local setup requires the authorized Jules Windows identity'
    }
    # Elevation can outlive its requester. Serialize helper lifetimes across
    # sessions before examining or changing the fixed scratch directory.
    $setupMutex = [Threading.Mutex]::new($false, 'Global\DiskEd.CappedScratch')
    try { $ownsSetupMutex = $setupMutex.WaitOne(0) } catch [Threading.AbandonedMutexException] {
        $ownsSetupMutex = $true
    }
    if (-not $ownsSetupMutex) { throw 'Another bounded scratch setup is active; no storage was changed' }
    if ($repoRoot -ne 'D:\Projects\DiskEd\disked' -or
        (Get-Content -LiteralPath (Join-Path $repoRoot 'spec\bundle.json') -Raw | ConvertFrom-Json).bundle_id -ne 'org.disked.spec') {
        throw 'Repository identity mismatch'
    }
    Assert-PlainPath $repoRoot
    foreach ($letter in 'C','D') {
        if ((Get-PSDrive -Name $letter).Free -lt 20GB) { throw "Host reserve missing on ${letter}:" }
    }
    if (-not (Test-Path -LiteralPath $scratchRoot)) {
        New-Item -ItemType Directory -Path $scratchRoot | Out-Null
    }
    Assert-PlainPath $scratchRoot
    if (@(Get-ChildItem -LiteralPath $scratchRoot -Force).Count -ne 0) {
        throw 'Scratch must be empty; inspect leftovers rather than adopting or overwriting them'
    }
    $nonce = [guid]::NewGuid().ToString('N')
    $owner = @{schema='org.disked.capped-scratch-owner/1'; root=$repoRoot; nonce=$nonce; image=$imagePath}
    [IO.File]::WriteAllText($ownerPath, ($owner | ConvertTo-Json) + "`n")
    $createdOwner = $true
    $state = @{schema='org.disked.capped-scratch/1'; phase='creating'; nonce=$nonce; root=$repoRoot;
        image=$imagePath; size_mib=$SizeMiB; pid=$PID; worker_elevated=$false;
        setup_elevated=$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator);
        helper_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()}
    Write-State $state
    # No SourceDisk, existing image, caller-selected path or disk-number parameter.
    $createdImage = $true
    $vhd = New-VHD -Path $imagePath -Fixed -SizeBytes ($SizeMiB * 1MB)
    if ($vhd.VhdType -ne 'Fixed' -or $vhd.VhdFormat -ne 'VHDX' -or
        $vhd.Size -ne $SizeMiB * 1MB -or $vhd.FileSize -gt 1GB) { throw 'Unexpected new image geometry' }
    $state.image_identifier = $vhd.DiskIdentifier.ToString()
    $state.backing_bytes = $vhd.FileSize
    Write-State $state
    Mount-VHD -Path $imagePath -NoDriveLetter | Out-Null
    $attachedImage = $true
    $vhd = Get-VHD -Path $imagePath
    $disk = Get-Disk -Number $vhd.DiskNumber
    if (-not $vhd.Attached -or $disk.IsBoot -or $disk.IsSystem -or
        $disk.PartitionStyle -ne 'RAW' -or $disk.Size -ne $SizeMiB * 1MB -or
        $disk.BusType -notin @('File Backed Virtual','Virtual')) { throw 'New-image binding check failed' }
    $state.disk_number_observed = $disk.Number
    if ($disk.IsOffline) { $disk | Set-Disk -IsOffline $false }
    $fresh = Get-VHD -Path $imagePath
    if ($fresh.DiskIdentifier.ToString() -ne $state.image_identifier -or $fresh.DiskNumber -ne $disk.Number) {
        throw 'Image changed before initialization'
    }
    $disk | Initialize-Disk -PartitionStyle MBR | Out-Null
    $disk = Get-Disk -Number $fresh.DiskNumber
    $state.disk_unique_id = $disk.UniqueId
    $partition = $disk | New-Partition -UseMaximumSize
    # Revalidate the exact image and new disk identity immediately before format.
    $fresh = Get-VHD -Path $imagePath
    if ($fresh.DiskIdentifier.ToString() -ne $state.image_identifier -or
        (Get-Disk -Number $fresh.DiskNumber).UniqueId -ne $state.disk_unique_id -or
        $partition.DiskNumber -ne $fresh.DiskNumber) { throw 'Image/partition binding changed before format' }
    Format-Volume -Partition $partition -FileSystem NTFS -AllocationUnitSize 4096 -NewFileSystemLabel 'DiskEdScratch' -Confirm:$false | Out-Null
    $used = @((Get-Volume).DriveLetter) + @((Get-PSDrive -PSProvider FileSystem).Name)
    $letter = @('R','S','T','U','V','W','X','Y','Z') | Where-Object { $_ -notin $used } | Select-Object -First 1
    if (-not $letter) { throw 'No unused temporary drive letter' }
    $partition | Add-PartitionAccessPath -AccessPath "${letter}:\"
    $volume = Get-Volume -DriveLetter $letter
    if ($volume.FileSystem -ne 'NTFS' -or $volume.Size -gt $SizeMiB * 1MB -or $volume.FileSystemLabel -ne 'DiskEdScratch') {
        throw 'Unexpected scratch filesystem'
    }
    $state.drive = "${letter}:\"
    $state.filesystem_bytes = $volume.Size
    $state.filesystem_free_bytes = $volume.SizeRemaining
    $state.volume_unique_id = $volume.UniqueId
    $state.work = Join-Path $state.drive 'work'
    New-Item -ItemType Directory -Path $state.work | Out-Null
    $acl = Get-Acl -LiteralPath $state.work
    $rule = [Security.AccessControl.FileSystemAccessRule]::new($identity.User,
        [Security.AccessControl.FileSystemRights]::FullControl,
        [Security.AccessControl.InheritanceFlags]'ContainerInherit,ObjectInherit',
        [Security.AccessControl.PropagationFlags]::None,
        [Security.AccessControl.AccessControlType]::Allow)
    $acl.SetAccessRule($rule)
    Set-Acl -LiteralPath $state.work -AclObject $acl
    $state.phase = 'ready'
    Write-State $state
    # A bounded lease, not a service. Accept only this run's release nonce.
    $deadline = [DateTime]::UtcNow.AddSeconds(120)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-Path -LiteralPath $releasePath) {
            if ((Get-Item -LiteralPath $releasePath).Length -gt 4096) { throw 'Oversized release marker' }
            $release = Get-Content -LiteralPath $releasePath -Raw | ConvertFrom-Json
            if ($release.nonce -ne $nonce -or $release.workers_stopped -ne $true) { throw 'Invalid release marker' }
            break
        }
        Start-Sleep -Milliseconds 200
    }
    $state.lease_expired = -not (Test-Path -LiteralPath $releasePath)
} catch {
    $failure = $_.Exception.Message
} finally {
    try {
        if ($attachedImage) {
            $fresh = Get-VHD -Path $imagePath
            if ($fresh.DiskIdentifier.ToString() -ne $state.image_identifier) { throw 'Refusing to detach a different image' }
            Dismount-VHD -Path $imagePath
            $attachedImage = $false
        }
        if ($createdImage -and (Test-Path -LiteralPath $imagePath)) {
            Assert-PlainPath $imagePath
            if ((Get-Content -LiteralPath $ownerPath -Raw | ConvertFrom-Json).nonce -ne $nonce) { throw 'Owner marker changed' }
            if ((Get-Item -LiteralPath $imagePath).Length -gt 1GB) { throw 'Unexpected image size' }
            $validVhd = $null
            try { $validVhd = Get-VHD -Path $imagePath } catch {
                if ($state.phase -ne 'creating' -or $attachedImage) { throw }
            }
            if ($null -ne $validVhd -and $validVhd.Attached) { throw 'Refusing to delete an attached image' }
            # Fixed literal file only; no recursive delete or other-volume cleanup.
            Remove-Item -LiteralPath $imagePath
        }
        if ($createdOwner) {
            if ((Get-Content -LiteralPath $ownerPath -Raw | ConvertFrom-Json).nonce -ne $nonce) { throw 'Owner marker changed' }
            Remove-Item -LiteralPath $ownerPath
            if (Test-Path -LiteralPath $releasePath) { Remove-Item -LiteralPath $releasePath }
        }
    } catch {
        $failure = "$failure; cleanup: $($_.Exception.Message)"
    }
    try {
        if ($null -ne $state) {
            $state.phase = if ($failure) { 'failed' } else { 'retired' }
            $state.error = $failure
            $state.image_removed = -not (Test-Path -LiteralPath $imagePath)
            Write-State $state
        }
    } finally {
        if ($null -ne $setupMutex) {
            try { if ($ownsSetupMutex) { $setupMutex.ReleaseMutex() } } finally { $setupMutex.Dispose() }
        }
    }
}
if ($failure) { Write-Error $failure -ErrorAction Continue; exit 1 }
