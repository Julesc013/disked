# Exercise the actual pure guard without creating, attaching or detaching media.
$ErrorActionPreference='Stop'
$source=Join-Path $PSScriptRoot 'guest-proof.ps1'
$tokens=$null;$errors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$errors)
if($errors.Count){throw 'Guest script parse failure.'}
$guard=$ast.Find({param($node)$node-is[Management.Automation.Language.FunctionDefinitionAst]-and$node.Name-eq'Assert-WorkersStopped'},$true)
if(-not$guard){throw 'Missing actual retirement guard.'}
. ([scriptblock]::Create($guard.Extent.Text))
$cases=@()
foreach($case in @(@($false,$false),@($false,$true),@($true,$true),@($true,$false))){
    $refused=$false
    try{Assert-WorkersStopped $case[0] $case[1]}catch{if($_.Exception.Message-ne'Worker/profile cleanup not established; preserve the small image.'){throw};$refused=$true}
    if($refused-ne($case[0]-and-not$case[1])){throw 'Retirement guard outcome mismatch.'}
    $cases+=@{started=$case[0];stopped=$case[1];refused=$refused}
}
$record=@{status='pass';scope='Pure retirement guard only; no disk operations';cases=$cases;source_sha256=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash;full_remote_interruption_test='not_run'}
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'retirement-guard.json'),(($record|ConvertTo-Json -Depth 5)-replace"`r`n","`n")+"`n",[Text.UTF8Encoding]::new($false))
$record|ConvertTo-Json -Depth 5
