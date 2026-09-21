param([string]$BaseUrl = '')
. "$PSScriptRoot/common.ps1"
if (-not $BaseUrl) { $BaseUrl = Get-AppUrl }
Wait-Endpoint "$BaseUrl/ready"
Invoke-RestMethod "$BaseUrl/health"
Invoke-RestMethod "$BaseUrl/rooms"
$start = [DateTime]::UtcNow.AddDays(1)
$body = @{room_id=1; start_time=$start.ToString('o'); end_time=$start.AddHours(1).ToString('o')} | ConvertTo-Json
$created = Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$BaseUrl/bookings" -ContentType 'application/json' -Headers @{'X-Request-ID'='demo-booking-001'} -Body $body
if ($created.StatusCode -ne 201) { throw 'Booking creation failed' }
$booking = $created.Content | ConvertFrom-Json
try {
    Invoke-RestMethod "$BaseUrl/bookings/$($booking.id)"
    $conflict = $false
    try {
        Invoke-WebRequest -UseBasicParsing -Method Post -Uri "$BaseUrl/bookings" -ContentType 'application/json' -Body $body | Out-Null
    } catch {
        if ([int]$_.Exception.Response.StatusCode -eq 409) { $conflict = $true } else { throw }
    }
    if (-not $conflict) { throw 'Expected a 409 overlap conflict' }
} finally {
    Invoke-RestMethod -Method Delete "$BaseUrl/bookings/$($booking.id)"
}
(Invoke-WebRequest -UseBasicParsing "$BaseUrl/metrics").Content | Select-String 'bookings_created_total'
Write-Host 'Smoke passed; request ID for Kibana: demo-booking-001'
