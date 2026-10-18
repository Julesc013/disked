# One-time guest-console setup. No host changes, password resets or network service.
[CmdletBinding()]
param([switch]$CreateAgents)
$ErrorActionPreference='Stop'
$computer=Get-CimInstance Win32_ComputerSystem
$identity=[Security.Principal.WindowsIdentity]::GetCurrent()
if($computer.Model -ne 'Virtual Machine' -or $computer.DNSHostName -ne 'BlackGlass-HyperV' -or
   ($identity.Name -split '\\')[-1] -ne 'Codex') {
 throw 'Use the Codex console in the authorized BlackGlass-HyperV guest only.'
}
$administrator=([Security.Principal.WindowsPrincipal]$identity).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
[pscustomobject]@{
 computer=$env:COMPUTERNAME
 dns_name=$computer.DNSHostName
 identity=$identity.Name
 administrator=$administrator
 enable_lua=(Get-ItemProperty -LiteralPath 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System').EnableLUA
} | Format-List
if($CreateAgents){
 if(-not $administrator){throw 'Codex console lacks the authorized guest administrator token.'}
 if(Get-LocalUser -Name Agents -ErrorAction SilentlyContinue){throw 'Agents already exists; no password or membership changed.'}
 $password=Read-Host 'Agents password (guest only)' -AsSecureString
 if($password.Length -eq 0){throw 'Unattended access requires a nonempty guest credential.'}
 try {
  $user=New-LocalUser -Name Agents -Password $password -Description 'Owner-authorized shared guest automation' -PasswordNeverExpires
  Add-LocalGroupMember -Group (Get-LocalGroup -SID 'S-1-5-32-544') -Member $user
  Write-Host 'Agents created and added to guest Administrators. Verify the unattended connection before retaining its credential.'
 } finally {$password=$null}
}
