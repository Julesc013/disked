# Read-only inspection of the fixed guest; never starts a product test or changes policy.
[CmdletBinding()]
param([switch]$PasswordlessCodex)
$ErrorActionPreference='Stop'
if ([Security.Principal.WindowsIdentity]::GetCurrent().Name -ne 'BLACKGLASS-WIN1\Jules') {
    throw 'Use the authorized host user context.'
}
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..'))
$session=$null
try {
    if ($PasswordlessCodex) {
        $credential=[Management.Automation.PSCredential]::new('BlackGlass-HyperV\Codex',[Security.SecureString]::new())
        $session=New-PSSession -VMId '3ebbe558-91b9-435b-96e4-0c8199bd38ad' -Credential $credential
    } else {
        $session=& (Join-Path $root 'tools\connect-vm.ps1') -OpenSession
    }
    Invoke-Command -Session $session -ScriptBlock {
        $ErrorActionPreference='Stop'
        $computer=Get-CimInstance Win32_ComputerSystem
        if ($computer.DNSHostName -ne 'BlackGlass-HyperV' -or $computer.Model -ne 'Virtual Machine') {throw 'Unexpected guest'}
        $identity=[Security.Principal.WindowsIdentity]::GetCurrent()
        $systemPolicy=Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System'
        $blankPolicy=Get-ItemProperty -LiteralPath 'HKLM:\SYSTEM\CurrentControlSet\Control\Lsa' -Name LimitBlankPasswordUse
        $codex=Get-LocalUser -Name Codex
        $admins=Get-LocalGroup -SID 'S-1-5-32-544'
        $os=Get-CimInstance Win32_OperatingSystem
        [pscustomobject]@{
            schema='org.disked.guest-inspection/1'
            observed_at=[DateTime]::UtcNow.ToString('o')
            computer=$computer.Name
            dns_name=$computer.DNSHostName
            model=$computer.Model
            identity=$identity.Name
            connection_administrator=([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
            codex_administrator=(@(Get-LocalGroupMember -Group $admins | Where-Object {$_.SID -eq $codex.SID}).Count -gt 0)
            enable_lua=$systemPolicy.EnableLUA
            limit_blank_password_use=$blankPolicy.LimitBlankPasswordUse
            last_boot_utc=$os.LastBootUpTime.ToUniversalTime().ToString('o')
            os_version=$os.Version
            powershell_version=$PSVersionTable.PSVersion.ToString()
            free_c_bytes=(Get-CimInstance Win32_LogicalDisk -Filter "DeviceID='C:'").FreeSpace
            commands=@(Get-Command python.exe,git.exe,cmake.exe,pwsh.exe,cl.exe,New-VHD,Mount-VHD,diskpart.exe -ErrorAction SilentlyContinue | Select-Object Name,Source)
            sdk_versions=@(Get-ChildItem -LiteralPath 'C:\Program Files (x86)\Windows Kits\10\Lib' -Directory -ErrorAction SilentlyContinue | Select-Object -First 16 | ForEach-Object {$_.Name})
            vs_editions=@(Get-ChildItem -LiteralPath 'C:\Program Files\Microsoft Visual Studio\2022' -Directory -ErrorAction SilentlyContinue | Select-Object -First 16 | ForEach-Object {$_.Name})
            product_tests_run=$false
        }
    } | Select-Object * -ExcludeProperty PSComputerName,RunspaceId,PSShowComputerName | ConvertTo-Json -Depth 5
} finally {
    if ($session) {Remove-PSSession -Session $session}
    $credential=$null
}
