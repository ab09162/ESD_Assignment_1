. "$PSScriptRoot/common.ps1"
Set-Location (Split-Path $PSScriptRoot -Parent)
$original = $env:DEMO_HIGH_CARDINALITY
$run = 'cardinality-' + [DateTime]::UtcNow.ToString('yyyyMMddTHHmmssZ')
New-Item -ItemType Directory -Force "results/$run" | Out-Null
$results = @()
try {
    foreach ($mode in @('true', 'false')) {
        $env:DEMO_HIGH_CARDINALITY = $mode
        Invoke-Compose --profile cardinality up -d --build --force-recreate cardinality-demo
        # Compose publishes IPv4 loopback; avoid Windows localhost IPv6 fallback per request.
        Wait-Endpoint 'http://127.0.0.1:8010/health'
        1..100 | ForEach-Object { Invoke-RestMethod -Method Post 'http://127.0.0.1:8010/hit' | Out-Null }
        $query = [Uri]::EscapeDataString('count(demo_requests_total{job="cardinality-demo"})')
        $expected = if ($mode -eq 'true') { 100 } else { 1 }
        $count = 0
        # Wait for scrapes and stale markers instead of assuming a fixed scrape happened.
        for ($attempt = 0; $attempt -lt 30; $attempt++) {
            Start-Sleep -Seconds 2
            $response = Invoke-RestMethod "http://127.0.0.1:9090/api/v1/query?query=$query"
            if ($response.data.result.Count -gt 0) { $count = [int]$response.data.result[0].value[1] }
            if ($count -eq $expected) { break }
        }
        if ($count -ne $expected) { throw "Expected $expected current series; found $count" }
        $results += [pscustomobject]@{high_cardinality=$mode; accepted=100; series=$count; utc=[DateTime]::UtcNow.ToString('o')}
        $results | ConvertTo-Json | Set-Content -Encoding UTF8 "results/$run/counts.json"
        Write-Host "high_cardinality=$mode current series=$count"
    }
} finally { $env:DEMO_HIGH_CARDINALITY = $original }
Write-Host "Evidence: results/$run. The low-cardinality demo remains running for screenshots."
Write-Host 'Stop later: docker compose --profile cardinality stop cardinality-demo'
