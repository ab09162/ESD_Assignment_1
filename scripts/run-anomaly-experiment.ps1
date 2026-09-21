param([string]$Duration = '2m', [int]$CooldownSeconds = 310)
. "$PSScriptRoot/common.ps1"
Set-Location (Split-Path $PSScriptRoot -Parent)
$original = $env:FAULT_DELAY_ENABLED
$run = [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
New-Item -ItemType Directory -Force "results/$run" | Out-Null
$events = @()
$failed = $false
try {
    foreach ($phase in @('baseline', 'fault', 'recovery')) {
        $env:FAULT_DELAY_ENABLED = if ($phase -eq 'fault') { 'true' } else { 'false' }
        Invoke-Compose up -d --no-deps --force-recreate app
        Wait-Endpoint "$(Get-AppUrl)/ready"
        # Avoid mixing phases in Grafana's 5-minute rate/quantile window.
        if ($phase -ne 'baseline' -and $CooldownSeconds -gt 0) {
            Write-Host "Waiting $CooldownSeconds seconds for the previous 5-minute window to clear."
            Start-Sleep -Seconds $CooldownSeconds
        }
        $start = [DateTime]::UtcNow.ToString('o')
        Write-Host "$phase starts $start"
        & docker compose --profile load run --rm -e "PHASE=$phase" -e "DURATION=$Duration" -e "SUMMARY_FILE=/results/$run/$phase.json" k6 run -o experimental-prometheus-rw /scripts/baseline.js
        $code = $LASTEXITCODE
        $end = [DateTime]::UtcNow.ToString('o')
        $events += [pscustomobject]@{phase=$phase; start=$start; end=$end; exit_code=$code}
        $events | ConvertTo-Json | Set-Content -Encoding UTF8 "results/$run/times.json"
        if ($code -ne 0) { $failed = $true; Write-Warning "$phase had failed thresholds; preserving evidence and continuing to recovery." }
    }
} finally {
    # Always recreate a fault-free app, even on interruption or a failed load test.
    $env:FAULT_DELAY_ENABLED = 'false'
    try { Invoke-Compose up -d --no-deps --force-recreate app; Wait-Endpoint "$(Get-AppUrl)/ready" }
    finally { $env:FAULT_DELAY_ENABLED = $original }
}
Write-Host "Evidence: results/$run. Compare absolute UTC windows in Grafana."
if ($failed) { throw 'One or more k6 phases failed; inspect saved summaries.' }
