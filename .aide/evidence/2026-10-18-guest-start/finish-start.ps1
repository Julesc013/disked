# One finite continuation of the owner's pending guest shutdown. No reset or UAC.
# Run under tools/workspace.py; output and probe files have fixed small bounds.
$ErrorActionPreference='Stop'
if ([Security.Principal.WindowsIdentity]::GetCurrent().Name -ne 'BLACKGLASS-WIN1\Jules' -or
    -not $env:DISKED_WORK_ROOT) {throw 'Expected managed workspace and host user'}
$vmId=[guid]'3ebbe558-91b9-435b-96e4-0c8199bd38ad'
$deadline=[DateTime]::UtcNow.AddMinutes(15)
$record=[ordered]@{
 schema='org.disked.guest-start-continuation/1'
 started_at=[DateTime]::UtcNow.ToString('o')
 deadline_utc=$deadline.ToString('o')
 controller_pid=$PID
 vm_id=$vmId.ToString()
 phase='waiting_pending_shutdown'
 starts_issued=0
 authentication_attempts=0
 product_tests_run=$false
 controller_sha256=(Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash.ToLowerInvariant()
}
function Save-Result {
 $record['observed_at']=[DateTime]::UtcNow.ToString('o')
 $text=($record | ConvertTo-Json -Depth 6).Replace("`r`n","`n")+"`n"
 $bytes=[Text.UTF8Encoding]::new($false).GetBytes($text)
 if ($bytes.Length -gt 16384) {throw 'Oversized continuation record'}
 [IO.File]::WriteAllBytes((Join-Path $PSScriptRoot 'startup-result.json'),$bytes)
}
Save-Result
try {
 while ([DateTime]::UtcNow -lt $deadline) {
  $vm=Get-VM -Id $vmId
  if ($vm.Name -ne 'Windows 10') {throw 'VM identity changed'}
  if ($vm.State -eq 'Off') {break}
  if ($vm.State -notin @('Running','Stopping')) {throw 'Unexpected VM state; inspect without resetting it'}
  Start-Sleep -Seconds 10
 }
 if ($vm.State -ne 'Off') {
  $record.phase='shutdown_wait_deadline_reached'
  Save-Result
  exit 3
 }
 $memory=Get-VMMemory -VM $vm
 if ($memory.Startup -gt 2GB -or $memory.Maximum -gt 3GB -or $vm.ProcessorCount -gt 2) {throw 'Shared VM configuration changed; review before startup'}
 if ((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory*1KB -lt 6GB -or
     (Get-PSDrive C).Free -lt 20GB -or (Get-PSDrive D).Free -lt 20GB) {throw 'Host resource reserve too low'}
 Start-VM -VM $vm
 $record.starts_issued=1
 $record.phase='started_waiting_heartbeat'
 Save-Result
 $readyDeadline=[DateTime]::UtcNow.AddMinutes(3)
 do {
  if ((Get-VMIntegrationService -VM $vm -Name Heartbeat).PrimaryStatusDescription -eq 'OK') {break}
  Start-Sleep -Seconds 5
 } while ([DateTime]::UtcNow -lt $readyDeadline)
 if ((Get-VMIntegrationService -VM $vm -Name Heartbeat).PrimaryStatusDescription -ne 'OK') {throw 'Guest heartbeat did not become ready'}
 $out=Join-Path $env:DISKED_WORK_ROOT 'guest-probe.out'
 $err=Join-Path $env:DISKED_WORK_ROOT 'guest-probe.err'
 $script=Join-Path $PSScriptRoot 'inspect-guest.ps1'
 $probe=Start-Process -FilePath (Get-Command pwsh.exe).Source -ArgumentList @('-NoProfile','-File',('"'+$script+'"'),'-PasswordlessCodex') -RedirectStandardOutput $out -RedirectStandardError $err -WindowStyle Hidden -PassThru
 $record.authentication_attempts=1
 if (-not $probe.WaitForExit(60000)) {
  $probe.Kill()
  $probe.WaitForExit()
  throw 'Read-only connection probe timed out; guest connection cleanup is unverified'
 }
 $probe.WaitForExit()
 if ((Get-Item -LiteralPath $out).Length -gt 8192 -or (Get-Item -LiteralPath $err).Length -gt 4096) {throw 'Probe result exceeded retention bound'}
 $record['probe_exit_code']=$probe.ExitCode
 $record['probe_stdout']=[IO.File]::ReadAllText($out)
 $record['probe_stderr']=[IO.File]::ReadAllText($err)
 $record.phase=if ($probe.ExitCode -eq 0) {'guest_inspected'} else {'guest_probe_failed'}
 Save-Result
 exit $probe.ExitCode
} catch {
 $record.phase='requires_inspection'
 $record['error']=$_.Exception.Message
 Save-Result
 exit 1
}
