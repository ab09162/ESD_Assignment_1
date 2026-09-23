"""Run inside app: verify live services, scrape, searchable log fields and ILM attachment."""

import json
import time
from datetime import UTC, datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from uuid import uuid4


def api(base, path, method="GET", body=None, headers=None):
    request = Request(
        base + path,
        method=method,
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json", **(headers or {})},
    )
    with urlopen(request, timeout=10) as response:
        return json.load(response)


def main():
    app, prom, elastic = "http://app:8000", "http://prometheus:9090", "http://elasticsearch:9200"
    assert api(app, "/health")["status"] == "ok"
    assert api(app, "/ready")["status"] == "ready"
    assert api("http://grafana:3000", "/api/health")["database"] == "ok"
    api("http://kibana:5601", "/api/status")
    targets = api(prom, "/api/v1/targets")["data"]["activeTargets"]
    for job in ("campus-app", "node-exporter", "prometheus"):
        assert any(t["labels"]["job"] == job and t["health"] == "up" for t in targets), job
    request_id = "verify-" + str(uuid4())
    start = datetime.now(UTC) + timedelta(days=1)
    booking = api(
        app,
        "/bookings",
        "POST",
        {
            "room_id": 2,
            "start_time": start.isoformat(),
            "end_time": (start + timedelta(minutes=5)).isoformat(),
        },
        {"X-Request-ID": request_id},
    )
    api(app, "/bookings/" + booking["id"], "DELETE")
    hit = None
    for _ in range(30):
        time.sleep(2)
        result = api(
            elastic,
            "/campus-logs-*/_search",
            "POST",
            {
                "query": {
                    "bool": {
                        "filter": [
                            {"term": {"request_id": request_id}},
                            {"term": {"message": "request_completed"}},
                        ]
                    }
                },
                "size": 1,
            },
        )
        if result["hits"]["hits"]:
            hit = result["hits"]["hits"][0]
            break
    assert hit, "Filebeat did not deliver the correlated booking log within 60s"
    fields = hit["_source"]
    for key in (
        "@timestamp",
        "service",
        "severity",
        "request_id",
        "method",
        "route",
        "status_code",
        "duration_ms",
        "message",
    ):
        assert key in fields, key
    assert fields["status_code"] == 201
    assert isinstance(fields["duration_ms"], int | float)
    lifecycle = api(elastic, "/campus-logs-*/_ilm/explain")["indices"]
    assert lifecycle and all(
        v["managed"] and v["policy"] == "campus-logs-7d" for v in lifecycle.values()
    )
    # Filebeat may index the request before the next Prometheus scrape.
    for _attempt in range(15):
        metric = api(
            prom,
            "/api/v1/query?"
            + urlencode(
                {
                    "query": "http_request_duration_seconds_count"
                    '{route="/bookings",method="POST",status="201"}'
                }
            ),
        )
        if metric["data"]["result"]:
            break
        time.sleep(2)
    assert metric["data"]["result"], "Histogram observations not scraped within 30s"
    print(
        json.dumps(
            {
                "verified_utc": datetime.now(UTC).isoformat(),
                "request_id": request_id,
                "stored_log": hit,
                "metric": metric["data"],
                "ilm": lifecycle,
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
