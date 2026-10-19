$ErrorActionPreference='Stop'
$repository=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '../../..'))
$receipt=Get-Content -LiteralPath (Join-Path $PSScriptRoot 'result.json') -Raw|ConvertFrom-Json
if(-not$receipt.guest.proof.all_owned_processes_retired-or-not$receipt.guest.setup.image_removed-or-not$receipt.guest.setup.actor_removed-or-not$receipt.guest.setup.actor_profile_absent){throw 'Owned workers/image/actor retirement is not established.'}
if(-not$receipt.guest.proof.crypto_device_retired-or-not$receipt.guest.proof.null_device_retired){throw 'Temporary security grants are not retired.'}
$expected=@($receipt.sources.files|Where-Object path -eq 'guest-source.py')
if($expected.Count-ne1){throw 'Missing exact source-retirement helper identity.'}
$session=& (Join-Path $repository 'tools/connect-vm.ps1') -OpenSession
try {
    $result=Invoke-Command -Session $session -ArgumentList $expected[0].sha256 -ScriptBlock {
        param($ExpectedHash)
        $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
        if($identity.Name-notlike '*\Agents'){throw 'Routine Agents guest required.'}
        $root='C:\ProgramData\DiskEd\qualification'
        $helper=Join-Path $root 'guest-source.py'
        $item=Get-Item -LiteralPath $helper
        if(($item.Attributes-band[IO.FileAttributes]::ReparsePoint)-or(Get-FileHash -LiteralPath $helper -Algorithm SHA256).Hash-ne$ExpectedHash){throw 'Retirement helper differs from its actual campaign hash.'}
        $python='C:\ProgramData\DiskEd\python314\python.exe'
        if((Get-FileHash -LiteralPath $python -Algorithm SHA256).Hash-ne'4942b86a6597e5aee0128daa00050ed79bc21f6e709a78eb19cbfeb0c2f39ac9'){throw 'Guest Python identity changed.'}
        & $python -B $helper retire
        if($LASTEXITCODE-ne0){throw 'Guarded owned-source retirement failed.'}
        Get-Content -LiteralPath (Join-Path $root 'source-retired.json') -Raw|ConvertFrom-Json
    }
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'source-retirement-recovery.json'),($result|Select-Object status,source_removed,nonce|ConvertTo-Json).Replace("`r`n","`n"))
} finally {Remove-PSSession -Session $session}
