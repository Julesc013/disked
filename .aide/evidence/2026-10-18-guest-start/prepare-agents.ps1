# One-time owner-authorized guest account setup. No Codex deletion in this phase.
$ErrorActionPreference = 'Stop'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$bios = Get-ItemProperty 'HKLM:\HARDWARE\DESCRIPTION\System\BIOS'
if ([Net.Dns]::GetHostName() -ne 'BlackGlass-HyperV' -or $bios.SystemProductName -ne 'Virtual Machine' -or
    $identity.Name -notmatch '^BLACKGLASS-HYPE\\(?:Codex|Agents)$') { throw 'Wrong guest or account.' }
if (-not ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    throw 'Guest administrator token required.'
}
$record = [ordered]@{
    schema = 'org.disked.guest-agents-preparation/1'
    observed_at = [DateTime]::UtcNow.ToString('o')
    identity = $identity.Name
    enable_lua = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System').EnableLUA
    status = 'not_run'
    codex_deleted = $false
    profile_files_deleted = $false
}
$recordPath = 'C:\ProgramData\DiskEd\agents-preparation.json'
$guestPassword = $null
try {
    $agentUser = Get-LocalUser -Name Agents
    $oldUser = Get-LocalUser -Name Codex
    $record.agents_sid = $agentUser.SID.Value
    $record.codex_sid = $oldUser.SID.Value
    $profileKey = "HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\ProfileList\$($oldUser.SID.Value)"
    $profile = (Get-ItemProperty -LiteralPath $profileKey).ProfileImagePath
    if ($profile -ne 'C:\Users\Codex') { throw 'Unexpected Codex profile; inspect before migration.' }
    $record.codex_profile = $profile
    $record.codex_profile_top_level = @(Get-ChildItem -LiteralPath $profile -Force | Select-Object Name,Mode,Length)
    $logonKey = Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
    $record.autologon_user_before = $logonKey.DefaultUserName
    $record.autologon_enabled_before = $logonKey.AutoAdminLogon
    Write-Host "Guest: $($identity.Name); EnableLUA=$($record.enable_lua)"
    Write-Host 'Existing Codex profile remains in place. Preparing only Agents.'
    $guestPassword = Read-Host 'Enter the owner-supplied Agents password' -AsSecureString
    if ($guestPassword.Length -eq 0) { throw 'Unattended access requires the supplied nonempty credential.' }
    Set-LocalUser -Name Agents -Password $guestPassword -PasswordNeverExpires $true -Description 'Shared guest automation account'
    Enable-LocalUser -Name Agents
    $admins = Get-LocalGroup -SID 'S-1-5-32-544'
    if (-not @(Get-LocalGroupMember -Group $admins | Where-Object SID -eq $agentUser.SID).Count) {
        Add-LocalGroupMember -Group $admins -Member $agentUser
    }
    Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class DiskEdGuestLogon {
 [DllImport("advapi32.dll", CharSet=CharSet.Unicode, SetLastError=true)]
 public static extern bool LogonUser(string user, string domain, IntPtr password, int type, int provider, out IntPtr token);
 [DllImport("kernel32.dll")] public static extern bool CloseHandle(IntPtr handle);
}
'@
    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToGlobalAllocUnicode($guestPassword)
    $token = [IntPtr]::Zero
    try {
        $record.interactive_credential_verified = [DiskEdGuestLogon]::LogonUser('Agents', $env:COMPUTERNAME, $pointer, 2, 0, [ref]$token)
        if (-not $record.interactive_credential_verified) {
            throw "Guest credential verification failed: $([Runtime.InteropServices.Marshal]::GetLastWin32Error())"
        }
    } finally {
        if ($token -ne [IntPtr]::Zero) { [DiskEdGuestLogon]::CloseHandle($token) | Out-Null }
        [Runtime.InteropServices.Marshal]::ZeroFreeGlobalAllocUnicode($pointer)
    }
    $record.agents_enabled = (Get-LocalUser -Name Agents).Enabled
    $record.agents_administrator = (@(Get-LocalGroupMember -Group $admins | Where-Object SID -eq $agentUser.SID).Count -eq 1)
    $record.status = 'pass'
    Write-Host 'AGENTS PREPARED: enabled, administrator, password does not expire, interactive credential accepted.'
    Write-Host 'Codex account and profile have not yet been removed.'
} catch {
    $record.status = 'fail'
    $record.error = $_.Exception.Message
    Write-Host "PREPARATION FAILED: $($record.error)"
    throw
} finally {
    $guestPassword = $null
    [IO.File]::WriteAllText($recordPath, (($record | ConvertTo-Json -Depth 6) -replace "`r`n", "`n") + "`n", [Text.UTF8Encoding]::new($false))
}
