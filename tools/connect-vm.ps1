#Requires -Version 7.0
<#!
One-time guest credential setup, a read-only connection check, or an open session.
No host elevation, network/remoting configuration, VM creation or test execution.
#>
[CmdletBinding(DefaultParameterSetName='Check')]
param(
    [Parameter(Mandatory,ParameterSetName='Setup')][switch]$SetupCredential,
    [Parameter(Mandatory,ParameterSetName='Session')][switch]$OpenSession,
    [Parameter(ParameterSetName='Setup')][Management.Automation.PSCredential]$GuestCredential
)
$ErrorActionPreference = 'Stop'
if (-not $IsWindows -or [Security.Principal.WindowsIdentity]::GetCurrent().Name -ne 'BLACKGLASS-WIN1\Jules') {
    throw 'Use the authorized Jules Windows session on BLACKGLASS-WIN1.'
}
$vmId = [guid]'3ebbe558-91b9-435b-96e4-0c8199bd38ad'
$credentialPath = Join-Path $env:LOCALAPPDATA "DiskEd\credentials\vm-$vmId.xml"

function Assert-GuestCredential {
    param([Management.Automation.PSCredential]$Value)
    if ($null -eq $Value -or $Value.Password.Length -eq 0) {
        throw 'Invalid guest credential: this unattended route requires a nonempty password; do not retry blank-password setup.'
    }
    if ($Value.UserName -notmatch '^(?:(?:\.|BLACKGLASS-HYPE|BLACKGLASS-HYPERV)\\)?Agents$') {
        throw 'Only the guest Agents account is authorized for automation; Codex is an emergency spare and Jules is excluded.'
    }
}

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
    if ($null -ne $GuestCredential) { Assert-GuestCredential $GuestCredential }
} else {
    if (-not (Test-Path -LiteralPath $credentialPath -PathType Leaf)) {
        throw 'Guest credential not configured. Run tools/connect-vm.ps1 -SetupCredential in an interactive PowerShell 7 window once.'
    }
    if ((Get-Item -LiteralPath $credentialPath).Length -gt 65536) {
        throw 'Oversized guest credential file; no connection attempted.'
    }
    $credential = Import-Clixml -LiteralPath $credentialPath
    if ($credential -isnot [Management.Automation.PSCredential]) {
        throw 'Invalid guest credential file; no connection attempted.'
    }
    Assert-GuestCredential $credential
}
$vm = Get-VM -Id $vmId
if ($vm.Name -ne 'Windows 10' -or $vm.State -ne 'Running') {
    throw 'Expected Windows 10 VM must be running. No VM state was changed.'
}
if ($SetupCredential) {
    if ($null -ne $GuestCredential) {
        $credential = $GuestCredential
    } else {
        Write-Host 'Enter Agents INSIDE the Windows 10 VM.'
        Write-Host 'A nonempty guest password is required for this route. Nothing is saved until verification succeeds.'
        $credential = Get-Credential -Message 'DiskEd: Agents guest account for unattended PowerShell Direct'
    }
    Assert-GuestCredential $credential
}
$session = $null
$keepSession = $false
try {
    $session = New-PSSession -VMId $vmId -Credential $credential
    $guest = Invoke-Command -Session $session -ScriptBlock {
        # Essential connection verification needs no WMI/provider discovery.
        $computer = Get-ItemProperty -LiteralPath 'HKLM:\HARDWARE\DESCRIPTION\System\BIOS'
        [pscustomobject]@{
            computer = $env:COMPUTERNAME
            dns_name = [Net.Dns]::GetHostName()
            model = $computer.SystemProductName
            identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
            elevated = ([Security.Principal.WindowsPrincipal][Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
            os_version = [Environment]::OSVersion.Version.ToString()
        }
    }
    if ($guest.dns_name -ne 'BlackGlass-HyperV' -or $guest.model -ne 'Virtual Machine' -or
        $guest.identity -notmatch '^BLACKGLASS-HYPE\\Agents$') {
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
