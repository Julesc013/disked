# Retire the eighth attempt's verified inputs after source recovery; no raw archive survived.
# Does not remove source trees, images, ACLs, profiles or running processes.
$ErrorActionPreference = 'Stop'
$repo = 'D:\Projects\DiskEd\disked'
$receipt = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'result.json') -Raw | ConvertFrom-Json
$session = & (Join-Path $repo 'tools\connect-vm.ps1') -OpenSession
try {
    $result = Invoke-Command -Session $session -ArgumentList ($receipt | ConvertTo-Json -Depth 16 -Compress) -ScriptBlock {
        param($ReceiptJson)
        $ErrorActionPreference = 'Stop'
        $receipt = $ReceiptJson | ConvertFrom-Json
        $root = 'C:\ProgramData\DiskEd\qualification'
        if ([Security.Principal.WindowsIdentity]::GetCurrent().Name -ne 'BLACKGLASS-HYPE\Agents') { throw 'Unexpected guest.' }
        $ancestor = Get-Item -LiteralPath $root -Force
        while ($ancestor) {
            if ($ancestor.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked root.' }
            $ancestor = $ancestor.Parent
        }
        $setup = Get-Content -LiteralPath "$root\setup-result.json" -Raw | ConvertFrom-Json
        $source = Get-Content -LiteralPath "$root\source-retired.json" -Raw | ConvertFrom-Json
        if (-not $setup.image_removed -or -not (($setup.runner_output | ConvertFrom-Json).workspace_removed) -or
            -not $source.source_removed -or (Test-Path -LiteralPath "$root\source") -or
            (Test-Path -LiteralPath "$root\scratch\disked-proof.vhd") -or
            (Test-Path -LiteralPath "$root\scoped-directory-access.json")) { throw 'Retirement incomplete.' }
        $paths = @($receipt.sources.files | ForEach-Object { Join-Path $root $_.path })
        $extra = @('source-manifest.json', 'setup-result.json', 'proof-result.json', 'source-owner.json',
            'source-prepared.json', 'source-retired.json', 'retained.tar.xz', 'scratch\create.txt',
            'scratch\owner.json', 'scratch\state.json', 'scratch\attach-config.json',
            'scratch\attach-result.json', 'scratch\outside\sentinel')
        $paths += @($extra | ForEach-Object { Join-Path $root $_ })
        $paths = @($paths | ForEach-Object { [IO.Path]::GetFullPath($_) })
        $dirs = @("$root\tools", "$root\scratch", "$root\scratch\outside")
        $items = @(Get-ChildItem -LiteralPath $root -Recurse -Force)
        if ($items.Count -gt 40) { throw 'Unexpected entry count.' }
        foreach ($item in $items) {
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) { throw 'Linked entry.' }
            $name = [IO.Path]::GetFullPath($item.FullName)
            if ($item.PSIsContainer) {
                if ($name -notin $dirs) { throw "Unexpected directory: $name" }
            } elseif ($name -notin $paths) { throw "Unexpected file: $name" }
        }
        foreach ($entry in $receipt.sources.files) {
            if ((Get-FileHash -LiteralPath (Join-Path $root $entry.path) -Algorithm SHA256).Hash -ne $entry.sha256) {
                throw 'Transferred input changed.'
            }
        }
        if ($receipt.guest.proof.archive_sha256 -and (Get-FileHash -LiteralPath "$root\retained.tar.xz" -Algorithm SHA256).Hash -ne $receipt.guest.proof.archive_sha256) {
            throw 'Retained archive changed.'
        }
        $bytes = 0L
        foreach ($path in $paths) {
            if (Test-Path -LiteralPath $path) {
                $bytes += (Get-Item -LiteralPath $path).Length
                Remove-Item -LiteralPath $path
            }
        }
        foreach ($path in @("$root\scratch\outside", "$root\scratch", "$root\tools", $root)) {
            if (Test-Path -LiteralPath $path) { Remove-Item -LiteralPath $path }
        }
        [pscustomobject]@{status='pass'; qualification_removed=(-not (Test-Path -LiteralPath $root));
            removed_content_bytes=$bytes; image_already_removed=$true; unrelated_processes_killed=$false;
            observed_at=[DateTime]::UtcNow.ToString('o')}
    }
    $result = $result | Select-Object * -ExcludeProperty PSComputerName, RunspaceId, PSShowComputerName
    $json = ($result | ConvertTo-Json -Depth 5) -replace "`r`n", "`n"
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'eighth-cleanup.json'), $json+"`n", [Text.UTF8Encoding]::new($false))
    $json
} finally { Remove-PSSession $session }
