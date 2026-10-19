#Requires -Version 7.0
param([Parameter(Mandatory)][ValidatePattern('^[0-9a-f]{32}$')][string]$ExpectedNonce)
$ErrorActionPreference='Stop'
trap{
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'preimage-cleanup-error.txt'),($_|Out-String),[Text.UTF8Encoding]::new($false))
    exit 1
}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$receipt=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'result.json') -Raw|ConvertFrom-Json
if($receipt.status-ne'fail'-or$receipt.guest.setup.error-notlike'*Description*48*'-or$receipt.guest.proof){throw 'Not the known preimage parameter refusal.'}
$session=& (Join-Path $root 'tools\connect-vm.ps1') -OpenSession
try{
    $arguments=[object[]]::new(2)
    $arguments[0]=@($receipt.sources.files);$arguments[1]=$ExpectedNonce
    $observed=Invoke-Command -Session $session -ArgumentList $arguments -ScriptBlock {
        param($Expected,$Nonce)
        $root='C:\ProgramData\DiskEd\qualification'
        if([Security.Principal.WindowsIdentity]::GetCurrent().Name-ne'BLACKGLASS-HYPE\Agents'){throw 'Wrong guest coordinator.'}
        $current=Get-Item -LiteralPath $root -Force
        while($current){if($current.Attributes-band[IO.FileAttributes]::ReparsePoint){throw 'Linked root.'};$current=$current.Parent}
        $owner=Get-Content -LiteralPath "$root\scratch\owner.json" -Raw|ConvertFrom-Json
        $actor=Get-Content -LiteralPath "$root\scratch\ordinary-actor.json" -Raw|ConvertFrom-Json
        $name='DiskEdTest-'+$Nonce.Substring(0,8)
        if($owner.nonce-ne$Nonce-or$actor.nonce-ne$Nonce-or$actor.name-ne$name-or$actor.phase-ne'creating'-or$actor.sid){throw 'Unexpected actor state.'}
        if((Get-LocalUser -Name $name -ErrorAction SilentlyContinue)-or(Test-Path -LiteralPath ('C:\Users\'+$name))){throw 'Account/profile remains; preserve source and inspect.'}
        if(Test-Path -LiteralPath "$root\scratch\disked-proof.vhd"){throw 'Image exists; this helper cannot remove media.'}
        $paths=@($Expected|ForEach-Object{[IO.Path]::GetFullPath((Join-Path $root $_.path))})+@("$root\source-manifest.json","$root\setup-result.json","$root\scratch\owner.json","$root\scratch\ordinary-actor.json")
        foreach($path in $paths){if(-not$path.StartsWith($root+'\',[StringComparison]::OrdinalIgnoreCase)){throw 'Cleanup target escaped fixed root.'}}
        $dirs=@("$root\scratch","$root\tools")
        $items=@(Get-ChildItem -LiteralPath $root -Recurse -Force)
        if($items.Count-gt40){throw 'Unexpected entry count.'}
        $bytes=0L
        foreach($item in $items){
            if($item.Attributes-band[IO.FileAttributes]::ReparsePoint){throw 'Linked cleanup entry.'}
            if($item.PSIsContainer){if($item.FullName-notin$dirs){throw 'Unexpected directory.'}}
            else{if($item.FullName-notin$paths){throw 'Unexpected file.'};$bytes+=$item.Length}
        }
        if($bytes-gt256KB){throw 'Unexpected preimage size.'}
        foreach($entry in $Expected){if((Get-FileHash -LiteralPath (Join-Path $root $entry.path) -Algorithm SHA256).Hash-ne$entry.sha256){throw 'Source copy changed.'}}
        foreach($path in $paths){if(Test-Path -LiteralPath $path){Remove-Item -LiteralPath $path}}
        foreach($path in @("$root\tools","$root\scratch",$root)){Remove-Item -LiteralPath $path}
        [pscustomobject]@{qualification_removed=(-not(Test-Path -LiteralPath $root));source_bytes_removed=$bytes;actor_absent=$true;actor_profile_absent=$true;image_created=$false;unrelated_processes_killed=$false}
    }|Select-Object * -ExcludeProperty PSComputerName,RunspaceId,PSShowComputerName
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'preimage-cleanup.json'),(($observed|ConvertTo-Json)-replace"`r`n","`n")+"`n",[Text.UTF8Encoding]::new($false))
    $observed|ConvertTo-Json
}finally{Remove-PSSession -Session $session}
