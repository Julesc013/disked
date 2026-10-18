# Retire only this campaign's verified disposable guest source/report copy.
param([ValidateSet(32,512)][int]$SizeMiB=32)
$ErrorActionPreference='Stop'
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$campaign=Get-Content -LiteralPath (Join-Path $PSScriptRoot "proof-$SizeMiB.json") -Raw|ConvertFrom-Json
if(-not$campaign.guest.setup.image_removed -or -not(($campaign.guest.setup.runner_output|ConvertFrom-Json).workspace_removed)){throw 'Prior workers/image are not retired.'}
$session=$null
try{
    $session=& (Join-Path $root 'tools\connect-vm.ps1') -OpenSession
    $cleanup=Invoke-Command -Session $session -ArgumentList (,$campaign.sources.files) -ScriptBlock {
        param($Expected)
        $root='C:\ProgramData\DiskEd\qualification'
        if([Security.Principal.WindowsIdentity]::GetCurrent().Name-ne'BLACKGLASS-HYPE\Agents'){throw 'Wrong guest account.'}
        $ancestor=Get-Item -LiteralPath $root -Force
        while($ancestor){if($ancestor.Attributes-band[IO.FileAttributes]::ReparsePoint){throw 'Linked root.'};$ancestor=$ancestor.Parent}
        if(Test-Path -LiteralPath "$root\scratch\disked-proof.vhd"){throw 'Image remains; do not discard its metadata.'}
        $paths=@($Expected|ForEach-Object{Join-Path $root $_.path})+@("$root\source-manifest.json","$root\setup-result.json","$root\proof-result.json","$root\scratch\create.txt","$root\scratch\owner.json","$root\scratch\state.json","$root\scratch\attach-config.json","$root\scratch\attach-result.json","$root\scratch\outside\sentinel")
        $dirs=@("$root\tools","$root\scratch","$root\scratch\outside")
        $items=@();foreach($item in Get-ChildItem -LiteralPath $root -Recurse -Force){$items+=$item;if($items.Count-gt32){throw 'Unexpected entry count.'}}
        foreach($item in $items){
            if($item.Attributes-band[IO.FileAttributes]::ReparsePoint){throw 'Linked entry.'}
            if($item.PSIsContainer){if($item.FullName-notin$dirs){throw 'Unexpected directory.'}}elseif($item.FullName-notin$paths){throw 'Unexpected file.'}
        }
        foreach($entry in $Expected){if((Get-FileHash -LiteralPath (Join-Path $root $entry.path) -Algorithm SHA256).Hash-ne$entry.sha256){throw 'Source copy changed; preserve it.'}}
        $setup=Get-Content -LiteralPath "$root\setup-result.json" -Raw|ConvertFrom-Json
        if(-not$setup.image_removed){throw 'Image retirement unverified.'}
        $bytes=0L;foreach($path in $paths){if(Test-Path -LiteralPath $path){$bytes+=(Get-Item -LiteralPath $path).Length;Remove-Item -LiteralPath $path}}
        foreach($path in @("$root\scratch\outside","$root\scratch","$root\tools",$root)){if(Test-Path -LiteralPath $path){Remove-Item -LiteralPath $path}}
        [pscustomobject]@{source_and_report_bytes_removed=$bytes;image_already_removed=$true;qualification_removed=(-not(Test-Path -LiteralPath $root));unrelated_processes_killed=$false}
    }|Select-Object * -ExcludeProperty PSComputerName,RunspaceId,PSShowComputerName
    $path=Join-Path $PSScriptRoot 'cleanups.json'
    $records=@();if(Test-Path -LiteralPath $path){$records=@(Get-Content -LiteralPath $path -Raw|ConvertFrom-Json)}
    $records+=@{image_uuid=$campaign.guest.setup.image_uuid;cleanup=$cleanup;observed_at=[DateTime]::UtcNow.ToString('o')}
    [IO.File]::WriteAllText($path,((ConvertTo-Json -InputObject @($records) -Depth 6)-replace"`r`n","`n")+"`n",[Text.UTF8Encoding]::new($false))
    $cleanup|ConvertTo-Json
}finally{if($session){Remove-PSSession -Session $session}}
