#Requires -Version 7.0
param([Parameter(Mandatory)][string]$Archive, [Parameter(Mandatory)][string]$Manifest)
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$work = [IO.Path]::GetFullPath($env:DISKED_WORK_ROOT)
if ((Split-Path -Parent ([IO.Path]::GetFullPath($Archive))) -ne $work -or
    (Split-Path -Parent ([IO.Path]::GetFullPath($Manifest))) -ne $work) { throw 'Transfer must belong to the managed workspace.' }
if ((Get-Item -LiteralPath $Archive).Length -gt 64MB -or (Get-Item -LiteralPath $Manifest).Length -gt 262144) { throw 'Transfer exceeds bound.' }
$session = $null
$createdTransfer = $false
$nonce = [guid]::NewGuid().ToString('N')
$report = [ordered]@{schema='org.disked.guest-runtime-copy/1';started_at=[DateTime]::UtcNow.ToString('o');status='not_run';global_installation=$false;product_tests_run=$false}
try {
    $session = & (Join-Path $root 'tools\connect-vm.ps1') -OpenSession
    Invoke-Command -Session $session -ArgumentList $nonce -ScriptBlock {
        param($Nonce)
        if ([Security.Principal.WindowsIdentity]::GetCurrent().Name -ne 'BLACKGLASS-HYPE\Agents') { throw 'Wrong guest account.' }
        $base = 'C:\ProgramData\DiskEd'
        foreach ($path in @('C:\ProgramData', $base)) {
            if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked guest root.' }
        }
        if (Test-Path -LiteralPath "$base\python314") { throw 'Existing runtime; no overwrite.' }
        if (Test-Path -LiteralPath "$base\runtime-transfer") { throw 'Existing transfer; inspect before reuse.' }
        if (([IO.DriveInfo]::new('C:\')).AvailableFreeSpace -lt 20GB) { throw 'Guest OS reserve missing.' }
        New-Item -ItemType Directory -Path "$base\runtime-transfer" | Out-Null
        [IO.File]::WriteAllText("$base\runtime-transfer\owner.json", ('{"nonce":"'+$Nonce+'"}'))
    }
    $createdTransfer = $true
    $vm = Get-VM -Id '3ebbe558-91b9-435b-96e4-0c8199bd38ad'
    Copy-VMFile -VM $vm -FileSource Host -SourcePath $Archive -DestinationPath 'C:\ProgramData\DiskEd\runtime-transfer\python314.zip'
    Copy-VMFile -VM $vm -FileSource Host -SourcePath $Manifest -DestinationPath 'C:\ProgramData\DiskEd\runtime-transfer\python314.json'
    $report.guest = Invoke-Command -Session $session -ScriptBlock {
        $ErrorActionPreference = 'Stop'
        $transfer = 'C:\ProgramData\DiskEd\runtime-transfer'
        $destination = 'C:\ProgramData\DiskEd\python314'
        $created = $false
        $archive = $null
        try {
            $manifest = Get-Content -LiteralPath "$transfer\python314.json" -Raw | ConvertFrom-Json
            if ($manifest.schema -ne 'org.disked.python-runtime/1' -or $manifest.files.Count -gt 1000 -or
                $manifest.content_bytes -gt 64MB -or (Get-FileHash "$transfer\python314.zip" -Algorithm SHA256).Hash -ne $manifest.archive_sha256) { throw 'Invalid transfer manifest.' }
            Add-Type -AssemblyName System.IO.Compression.FileSystem
            $archive = [IO.Compression.ZipFile]::OpenRead("$transfer\python314.zip")
            if ($archive.Entries.Count -ne $manifest.files.Count) { throw 'Entry count mismatch.' }
            New-Item -ItemType Directory -Path $destination | Out-Null
            $created = $true
            $total = 0L
            for ($index=0; $index -lt $archive.Entries.Count; $index++) {
                $entry = $archive.Entries[$index]
                $expected = $manifest.files[$index]
                if ($entry.FullName -ne $expected.path -or $entry.Length -ne $expected.bytes -or
                    $entry.FullName -match '(^/|\\|:|(^|/)\.\.(/|$))') { throw 'Invalid runtime entry.' }
                $target = [IO.Path]::GetFullPath((Join-Path $destination $entry.FullName))
                if (-not $target.StartsWith($destination+'\', [StringComparison]::OrdinalIgnoreCase)) { throw 'Runtime entry escaped destination.' }
                $total += $entry.Length
                if ($total -gt 64MB) { throw 'Runtime extraction exceeded bound.' }
                $parent = Split-Path -Parent $target
                if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
                [IO.Compression.ZipFileExtensions]::ExtractToFile($entry, $target, $false)
                if ((Get-FileHash -LiteralPath $target -Algorithm SHA256).Hash -ne $expected.sha256) { throw 'Runtime content hash mismatch.' }
            }
            $archive.Dispose(); $archive=$null
            # Windows PowerShell's legacy native quoting strips embedded quotes.
            # Keep this Python source free of quoted literals and retain all stderr.
            $nativePreference=$ErrorActionPreference
            try {
                $ErrorActionPreference='Continue'
                $probe = @(& "$destination\python.exe" -I -B -c 'import sys,ctypes,ssl,unittest,subprocess,tempfile,json,zipfile,lzma,sqlite3; print(json.dumps(dict(version=sys.version,prefix=sys.prefix,executable=sys.executable,imports=True)))' 2>&1)
                $probeExit=$LASTEXITCODE
            } finally { $ErrorActionPreference=$nativePreference }
            if ($probeExit -ne 0) { throw ('Guest runtime probe failed: '+(($probe | ForEach-Object ToString) -join "`n")) }
            $observed = $probe | ConvertFrom-Json
            if ($observed.version -ne $manifest.version -or $observed.prefix -ne $destination -or $observed.imports -ne $true) { throw 'Unexpected runtime identity.' }
            Copy-Item -LiteralPath "$transfer\python314.json" -Destination "$destination\.disked-runtime.json"
            [pscustomobject]@{identity=[Security.Principal.WindowsIdentity]::GetCurrent().Name;runtime=$observed;files_verified=$manifest.files.Count;content_bytes=$total;archive_bytes=$manifest.archive_bytes;archive_sha256=$manifest.archive_sha256;manifest_sha256=(Get-FileHash -LiteralPath "$destination\.disked-runtime.json" -Algorithm SHA256).Hash;global_path_changed=$false;registry_changed=$false}
            $created=$false # Verified persistent project-owned tool; retain it.
        } finally {
            if ($archive) { $archive.Dispose() }
            # Both directories were new, fixed project-owned destinations in this invocation.
            foreach ($path in @($(if($created){$destination}),$transfer)) {
                if (-not $path -or -not (Test-Path -LiteralPath $path)) { continue }
                $absolute=[IO.Path]::GetFullPath($path)
                if ($absolute -notin @('C:\ProgramData\DiskEd\python314','C:\ProgramData\DiskEd\runtime-transfer')) { throw 'Unexpected cleanup path.' }
                if ((Get-Item -LiteralPath $absolute -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked cleanup root; preserve for review.' }
                if (@(Get-ChildItem -LiteralPath $absolute -Recurse -Force | Where-Object {$_.Attributes -band [IO.FileAttributes]::ReparsePoint}).Count) { throw 'Linked cleanup descendant; preserve for review.' }
                Remove-Item -LiteralPath $absolute -Recurse -Force
            }
        }
    } | Select-Object * -ExcludeProperty PSComputerName,RunspaceId,PSShowComputerName
    $report.status='pass'
} catch {
    $report.status='fail';$report.error=$_.Exception.Message
    throw
} finally {
    if ($session -and $createdTransfer) {
        Invoke-Command -Session $session -ArgumentList $nonce -ScriptBlock {
            param($Nonce)
            $path='C:\ProgramData\DiskEd\runtime-transfer'
            if (-not (Test-Path -LiteralPath $path)) { return }
            if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked transfer cleanup root.' }
            if ((Get-Content -LiteralPath "$path\owner.json" -Raw | ConvertFrom-Json).nonce -ne $Nonce) { throw 'Transfer ownership changed.' }
            foreach ($entry in Get-ChildItem -LiteralPath $path -Force) {
                if ($entry.Name -notin @('owner.json','python314.zip','python314.json') -or $entry.PSIsContainer -or
                    ($entry.Attributes -band [IO.FileAttributes]::ReparsePoint)) { throw 'Unexpected transfer cleanup entry.' }
                Remove-Item -LiteralPath $entry.FullName
            }
            Remove-Item -LiteralPath $path
        }
    }
    if ($session) { Remove-PSSession -Session $session }
    $report.finished_at=[DateTime]::UtcNow.ToString('o')
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'python-runtime.json'),(($report|ConvertTo-Json -Depth 6)-replace "`r`n","`n")+"`n",[Text.UTF8Encoding]::new($false))
    $report|ConvertTo-Json -Depth 6
}
