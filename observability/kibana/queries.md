# Campus Kibana searches

After Kibana is healthy, run `docker compose exec -T app python scripts/setup-kibana.py`.
Alternatively, Stack Management → Data Views → Create: name **Campus request logs**, pattern `campus-logs-*`, timestamp `@timestamp`.

Open Discover, choose that view, set **Last 15 minutes** (or an experiment's saved absolute UTC interval), and add columns: `timestamp`, `severity`, `request_id`, `method`, `route`, `status_code`, `duration_ms`, `message`.

```kql
request_id : "demo-booking-001"
severity : "ERROR"
status_code >= 500
route : "/bookings"
route : "/bookings" and method : "POST" and status_code : 201
status_code : 409
status_code : 422
message : "fault_delay_injected"
message : "request_completed" and duration_ms >= 500
request_id : "<paste returned X-Request-ID>" and (severity : "ERROR" or status_code >= 500)
message : "database_unavailable" or message : "business_metrics_refresh_failed"
```

`route` is a template, so use `/bookings/{booking_id}` when searching fetch/cancel requests. A conflict is a domain result, not an ERROR-level crash. Fault warning and completed-request records share the same request ID.

Verification from PowerShell:

```powershell
Invoke-RestMethod 'http://localhost:9200/campus-logs-*/_count'
Invoke-RestMethod 'http://localhost:9200/campus-logs-*/_mapping'
Invoke-RestMethod 'http://localhost:9200/_ilm/policy/campus-logs-7d'
Invoke-RestMethod 'http://localhost:9200/campus-logs-*/_ilm/explain'
docker compose exec -T app python scripts/verify-stack.py
```

The verifier prints a **real** stored document and checks numeric status/duration, correlation fields, scrape observations, and ILM attachment. Save its output with your report. No example screenshot or synthetic document counts as observed delivery.
