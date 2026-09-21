$ErrorActionPreference = 'Stop'

function Invoke-Compose {
    & docker compose @args
    if ($LASTEXITCODE -ne 0) { throw "docker compose failed (exit $LASTEXITCODE): $args" }
}

function Wait-Endpoint([string]$Url) {
    for ($attempt = 0; $attempt -lt 60; $attempt++) {
        try {
            $response = Invoke-WebRequest -UseBasicParsing -Uri $Url -TimeoutSec 3
            if ($response.StatusCode -eq 200) { return }
        } catch { }
        Start-Sleep -Seconds 2
    }
    throw "Endpoint did not become ready: $Url"
}

function Get-AppUrl {
    $port = $env:APP_PORT
    if (-not $port -and (Test-Path .env)) {
        $line = Get-Content .env | Where-Object { $_ -match '^APP_PORT=(\d+)$' } | Select-Object -Last 1
        if ($line) { $port = $line.Split('=')[1] }
    }
    if (-not $port) { $port = '8000' }
    return "http://localhost:$port"
}
