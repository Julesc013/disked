#Requires -Version 7.0
# Apply the owner's final policy: Agents primary; Codex retained as emergency spare.
$ErrorActionPreference = 'Stop'
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$session = $null
$saved = $null
$record = [ordered]@{
    schema = 'org.disked.guest-account-configuration/1'
    started_at = [DateTime]::UtcNow.ToString('o')
    status = 'not_run'
    authority = 'Owner: use Agents; keep Codex as an emergency spare with the same supplied password. Do not delete or routinely use Codex.'
    product_tests_run = $false
    codex_login_performed = $false
    account_or_profile_deleted = $false
}
try {
    $session = & (Join-Path $root 'tools\connect-vm.ps1') -OpenSession
    $saved = Import-Clixml -LiteralPath (Join-Path $env:LOCALAPPDATA 'DiskEd\credentials\vm-3ebbe558-91b9-435b-96e4-0c8199bd38ad.xml')
    if ($saved.UserName -ne 'BLACKGLASS-HYPE\Agents') { throw 'Unexpected saved account.' }
    $owned = @('bootstrap-access.ps1', 'prepare-agents.ps1') | ForEach-Object {
        $file = Join-Path $PSScriptRoot $_
        [pscustomobject]@{name=$_;sha256=(Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash}
    }
    $record.guest = Invoke-Command -Session $session -ArgumentList $saved.Password, $owned -ScriptBlock {
        param([Security.SecureString]$EmergencyPassword, $OwnedFiles)
        $ErrorActionPreference = 'Stop'
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $bios = Get-ItemProperty 'HKLM:\HARDWARE\DESCRIPTION\System\BIOS'
        if ($identity.Name -ne 'BLACKGLASS-HYPE\Agents' -or [Net.Dns]::GetHostName() -ne 'BlackGlass-HyperV' -or
            $bios.SystemProductName -ne 'Virtual Machine') { throw 'Wrong guest account or computer.' }
        if (-not ([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
            throw 'Agents lacks the authorized guest administrator token.'
        }
        if ($EmergencyPassword.Length -eq 0) { throw 'Missing owner-supplied emergency credential.' }
        $agentsBefore = Get-LocalUser -Name Agents
        $codexBefore = Get-LocalUser -Name Codex
        Set-LocalUser -Name Agents -PasswordNeverExpires $true -Description 'Primary shared guest automation account'
        Set-LocalUser -Name Codex -Password $EmergencyPassword -PasswordNeverExpires $true -Description 'Emergency spare; daily work uses Agents'
        $logonPath = 'HKLM:\SOFTWARE\Microsoft\Windows NT\CurrentVersion\Winlogon'
        $logon = Get-ItemProperty -LiteralPath $logonPath
        $oldCodexAutologonDisabled = $false
        if ($logon.DefaultUserName -match '^(?:[^\\]+\\)?Codex$' -and $logon.AutoAdminLogon -eq '1') {
            Set-ItemProperty -LiteralPath $logonPath -Name AutoAdminLogon -Value '0'
            Set-ItemProperty -LiteralPath $logonPath -Name DefaultUserName -Value 'Agents'
            $oldCodexAutologonDisabled = $true
        }
        $cleanup = @()
        foreach ($entry in $OwnedFiles) {
            if ($entry.name -notin @('bootstrap-access.ps1', 'prepare-agents.ps1')) { throw 'Unexpected cleanup entry.' }
            $file = Join-Path 'C:\ProgramData\DiskEd' $entry.name
            if (-not (Test-Path -LiteralPath $file)) { continue }
            $item = Get-Item -LiteralPath $file -Force
            if ($item.Attributes -band [IO.FileAttributes]::ReparsePoint -or
                (Get-FileHash -LiteralPath $file -Algorithm SHA256).Hash -ne $entry.sha256) {
                $cleanup += [pscustomobject]@{path=$file;removed=$false;reason='Changed or linked; preserved.'}
                continue
            }
            $matching = @(Get-CimInstance Win32_Process -Filter "Name='powershell.exe'" | Where-Object {
                $_.CommandLine -and $_.CommandLine.Contains($file)
            })
            if ($matching.Count) {
                $cleanup += [pscustomobject]@{path=$file;removed=$false;reason='Potential console process still running; preserved.'}
                continue
            }
            Remove-Item -LiteralPath $file
            $cleanup += [pscustomobject]@{path=$file;removed=$true;bytes=$item.Length}
        }
        $agents = Get-LocalUser -Name Agents
        $codex = Get-LocalUser -Name Codex
        $admins = Get-LocalGroup -SID 'S-1-5-32-544'
        $members = @(Get-LocalGroupMember -Group $admins)
        if ($agents.SID -ne $agentsBefore.SID -or $codex.SID -ne $codexBefore.SID) { throw 'Unexpected account identity change.' }
        if (-not $agents.Enabled -or -not $codex.Enabled -or $agents.PasswordExpires -or $codex.PasswordExpires) {
            throw 'Final account enabled/expiration checks failed.'
        }
        [pscustomobject]@{
            identity=$identity.Name
            enable_lua=(Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System').EnableLUA
            agents=($agents | Select-Object Name,Enabled,PasswordLastSet,PasswordExpires,Description)
            codex=($codex | Select-Object Name,Enabled,PasswordLastSet,PasswordExpires,Description)
            agents_administrator=(@($members | Where-Object SID -eq $agents.SID).Count -eq 1)
            codex_administrator=(@($members | Where-Object SID -eq $codex.SID).Count -eq 1)
            account_sids_preserved=$true
            codex_profile_preserved=(Test-Path -LiteralPath 'C:\Users\Codex')
            active_profile=$env:USERPROFILE
            codex_autologon_disabled=$oldCodexAutologonDisabled
            owned_cleanup=$cleanup
            guest_c_free_bytes=([IO.DriveInfo]::new('C:\')).AvailableFreeSpace
        }
    } | Select-Object * -ExcludeProperty PSComputerName,RunspaceId,PSShowComputerName
    $record.status = 'pass'
} catch {
    $record.status = 'fail'
    $record.error = $_.Exception.Message
    throw
} finally {
    if ($session) { Remove-PSSession -Session $session }
    $saved = $null
    $record.finished_at = [DateTime]::UtcNow.ToString('o')
    [IO.File]::WriteAllText((Join-Path $PSScriptRoot 'account-configuration.json'), (($record | ConvertTo-Json -Depth 8) -replace "`r`n", "`n") + "`n", [Text.UTF8Encoding]::new($false))
    $record | ConvertTo-Json -Depth 8
}
