#Requires -Version 7.0
# One owner-authorized normal shutdown/start of the existing shared guest.
$ErrorActionPreference = 'Stop'
$vmId = [guid]'3ebbe558-91b9-435b-96e4-0c8199bd38ad'
$resultPath = Join-Path $PSScriptRoot 'restart-result.json'
$result = [ordered]@{
    schema = 'org.disked.guest-restart-result/1'
    started_at = [DateTime]::UtcNow.ToString('o')
    authority = 'Owner answered the shared-guest coordination question: i dont know but reset it anyway.'
    vm_id = $vmId.ToString()
    method = 'Stop-VM normal guest shutdown, then Start-VM; no TurnOff, Force or reset.'
    status = 'not_started'
    product_tests_run = $false
}
try {
    if ([Security.Principal.WindowsIdentity]::GetCurrent().Name -ne 'BLACKGLASS-WIN1\Jules') {
        throw 'Unexpected host execution identity.'
    }
    $vm = Get-VM -Id $vmId
    if ($vm.Name -ne 'Windows 10' -or $vm.State -ne 'Running') {
        throw 'Expected existing guest must be running.'
    }
    $snapshotsBefore = @((Get-VMSnapshot -VM $vm).Id | ForEach-Object ToString | Sort-Object)
    $hostUacBefore = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System').EnableLUA
    $result.state_before = [string]$vm.State
    $result.checkpoints_before = $snapshotsBefore
    $result.host_enable_lua_before = $hostUacBefore
    $result.status = 'shutdown_requested'
    Write-Output 'Requesting a normal Windows guest shutdown.'
    Stop-VM -VM $vm -Confirm:$false
    $vm = Get-VM -Id $vmId
    if ($vm.State -ne 'Off') { throw "Normal shutdown did not reach Off: $($vm.State)" }
    $result.shutdown_completed_at = [DateTime]::UtcNow.ToString('o')
    $result.status = 'starting'
    Start-VM -VM $vm | Out-Null
    $result.start_requested_at = [DateTime]::UtcNow.ToString('o')
    $deadline = [DateTime]::UtcNow.AddSeconds(120)
    do {
        $vm = Get-VM -Id $vmId
        $heartbeat = Get-VMIntegrationService -VM $vm | Where-Object Name -eq 'Heartbeat'
        if ($vm.State -eq 'Running' -and $heartbeat.PrimaryStatusDescription -eq 'OK') { break }
        Start-Sleep -Seconds 2
    } while ([DateTime]::UtcNow -lt $deadline)
    $result.state_after = [string]$vm.State
    $result.heartbeat = [string]$heartbeat.PrimaryStatusDescription
    $result.checkpoints_after = @((Get-VMSnapshot -VM $vm).Id | ForEach-Object ToString | Sort-Object)
    $result.checkpoints_preserved = (@(Compare-Object $snapshotsBefore $result.checkpoints_after).Count -eq 0)
    $result.host_enable_lua_after = (Get-ItemProperty 'HKLM:\SOFTWARE\Microsoft\Windows\CurrentVersion\Policies\System').EnableLUA
    if (-not $result.checkpoints_preserved -or $result.host_enable_lua_after -ne $hostUacBefore) {
        throw 'Unexpected checkpoint or host UAC state; no corrective mutation attempted.'
    }
    if ($vm.State -ne 'Running' -or $heartbeat.PrimaryStatusDescription -ne 'OK') {
        throw 'Guest started, but heartbeat readiness was not confirmed within the observation window.'
    }
    $result.status = 'pass'
} catch {
    $result.status = 'fail'
    $result.error = $_.Exception.Message
    throw
} finally {
    $result.finished_at = [DateTime]::UtcNow.ToString('o')
    [IO.File]::WriteAllText($resultPath, (($result | ConvertTo-Json -Depth 8) -replace "`r`n", "`n") + "`n", [Text.UTF8Encoding]::new($false))
}
