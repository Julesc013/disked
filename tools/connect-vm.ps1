#Requires -Version 7.0
<#!
One-time guest credential setup, a read-only connection check, or an open session.
No host elevation, network/remoting configuration, VM creation or test execution.
#>
[CmdletBinding(DefaultParameterSetName='Check')]
param(
    [Parameter(Mandatory,ParameterSetName='Setup')][switch]$SetupCredential,
    [Parameter(Mandatory,ParameterSetName='Session')][switch]$OpenSession
)
$ErrorActionPreference = 'Stop'
if (-not $IsWindows -or [Security.Principal.WindowsIdentity]::GetCurrent().Name -ne 'BLACKGLASS-WIN1\Jules') {
    throw 'Use the authorized Jules Windows session on BLACKGLASS-WIN1.'
}
$vmId = [guid]'3ebbe558-91b9-435b-96e4-0c8199bd38ad'
$credentialPath = Join-Path $env:LOCALAPPDATA "DiskEd\credentials\vm-$vmId.xml"

# Do not read or write a redirected credential path. Passwords use Windows DPAPI
# through Export/Import-Clixml; never convert the SecureString into plain text.
$itemPath = [IO.Path]::GetFullPath($credentialPath)
while ($itemPath) {
    if (Test-Path -LiteralPath $itemPath) {
        if ((Get-Item -LiteralPath $itemPath -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
            throw 'Linked guest credential path; no connection attempted.'
        }
    }
    $parent = Split-Path -Parent $itemPath
    if ($parent -eq $itemPath) { break }
    $itemPath = $parent
}
if ($SetupCredential) {
    if (Test-Path -LiteralPath $credentialPath) {
        throw 'A guest credential already exists. Run without -SetupCredential to check it; no replacement was made.'
    }
} else {
    if (-not (Test-Path -LiteralPath $credentialPath -PathType Leaf)) {
        throw 'Guest credential not configured. Run tools/connect-vm.ps1 -SetupCredential in an interactive PowerShell 7 window once.'
    }
    if ((Get-Item -LiteralPath $credentialPath).Length -gt 65536) {
        throw 'Oversized guest credential file; no connection attempted.'
    }
    $credential = Import-Clixml -LiteralPath $credentialPath
    if ($credential -isnot [Management.Automation.PSCredential] -or $credential.Password.Length -eq 0) {
        throw 'Invalid guest credential file; no connection attempted.'
    }
}
$vm = Get-VM -Id $vmId
if ($vm.Name -ne 'Windows 10' -or $vm.State -ne 'Running') {
    throw 'Expected Windows 10 VM must be running. No VM state was changed.'
}
if ($SetupCredential) {
    Write-Host 'Enter an account INSIDE the Windows 10 VM, for example BlackGlass-HyperV\Codex.'
    Write-Host 'Use its password, not a host password or Windows Hello PIN. Nothing is saved until the connection succeeds.'
    $credential = Get-Credential -Message 'DiskEd: Windows 10 guest account for unattended PowerShell Direct'
    if ($null -eq $credential -or $credential.Password.Length -eq 0) { throw 'Guest credential setup cancelled.' }
}
$session = $null
$keepSession = $false
try {
    $session = New-PSSession -VMId $vmId -Credential $credential
    $guest = Invoke-Command -Session $session -ScriptBlock {
        $computer = Get-CimInstance Win32_ComputerSystem
        [pscustomobject]@{
            computer = $env:COMPUTERNAME
            model = $computer.Model
            identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
            elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
            os_version = [Environment]::OSVersion.Version.ToString()
        }
    }
    if ($guest.computer -ne 'BlackGlass-HyperV' -or $guest.model -ne 'Virtual Machine') {
        throw 'Unexpected guest identity; credential was not saved.'
    }
    if ($SetupCredential) {
        New-Item -ItemType Directory -Path (Split-Path -Parent $credentialPath) -Force | Out-Null
        $credential | Export-Clixml -LiteralPath $credentialPath -NoClobber
        Write-Host 'Verified guest credential saved with Windows encryption for this host user. No test has run.'
    }
    if ($OpenSession) {
        $keepSession = $true
        $session
    } else {
        [pscustomobject]@{status='connected';vm_id=$vmId.ToString();vm_name=$vm.Name;guest=$guest.computer;guest_identity=$guest.identity;guest_elevated=$guest.elevated;guest_os=$guest.os_version;tests_run=$false}
    }
} finally {
    if ($null -ne $session -and -not $keepSession) { Remove-PSSession -Session $session }
    $credential = $null
}
