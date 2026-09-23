"""Verify provisioned Grafana queries and live Prometheus data from the host.

Reads local Grafana credentials from .env without printing or saving them.
Run after generating business traffic; use --at for a past load-test UTC timestamp.
"""

import argparse
import base64
import json
import os
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]


def get(base, path, headers=None):
    request = Request(base + path, headers=headers or {})
    with urlopen(request, timeout=20) as response:
        return json.load(response)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--at", help="Optional UTC timestamp within a live load-test interval")
    args = parser.parse_args()
    env = {**dotenv_values(ROOT / ".env"), **os.environ}
    prometheus = env.get("PROMETHEUS_URL", "http://127.0.0.1:9090")
    grafana = env.get("GRAFANA_URL", "http://127.0.0.1:3000")
    credentials = (
        env.get("GRAFANA_ADMIN_USER", "admin")
        + ":"
        + env.get("GRAFANA_ADMIN_PASSWORD", "local-coursework-change-me")
    )
    headers = {"Authorization": "Basic " + base64.b64encode(credentials.encode()).decode()}
    datasource = get(grafana, "/api/datasources/uid/prometheus", headers)
    assert datasource["type"] == "prometheus" and datasource["url"] == "http://prometheus:9090"
    assert datasource["isDefault"]
    health = get(grafana, "/api/datasources/uid/prometheus/health", headers)
    assert health["status"] == "OK", health.get("message")
    targets = get(prometheus, "/api/v1/targets")["data"]["activeTargets"]
    target_status = {item["labels"]["job"]: item["health"] for item in targets}
    assert all(
        target_status.get(job) == "up" for job in ("campus-app", "node-exporter", "prometheus")
    )
    panels = []
    for source in sorted((ROOT / "observability/grafana/dashboards").glob("*.json")):
        expected = json.loads(source.read_text(encoding="utf-8"))
        loaded = get(grafana, "/api/dashboards/uid/" + expected["uid"], headers)["dashboard"]
        assert loaded["title"] == expected["title"]
        assert len(loaded["panels"]) == len(expected["panels"])
        for panel in loaded["panels"]:
            assert panel["datasource"]["uid"] == "prometheus"
            for target in panel["targets"]:
                assert target["datasource"]["uid"] == "prometheus"
                query = {"query": target["expr"]}
                if args.at:
                    query["time"] = args.at
                result = get(prometheus, "/api/v1/query?" + urlencode(query))
                assert result["status"] == "success"
                panels.append(
                    {
                        "dashboard": expected["uid"],
                        "panel": panel["title"],
                        "expression": target["expr"],
                        "series_count": len(result["data"]["result"]),
                        "sample": result["data"]["result"][:2],
                    }
                )
    required = [
        "http_requests_total",
        "http_requests_in_progress",
        "http_request_duration_seconds_bucket",
        "db_operation_duration_seconds_sum",
        "db_operation_duration_seconds_count",
        "bookings_created_total",
        "bookings_cancelled_total",
        "booking_conflicts_total",
        "active_bookings",
        "node_cpu_seconds_total",
        "node_memory_MemAvailable_bytes",
        "node_filesystem_size_bytes",
        "node_disk_read_bytes_total",
        "node_network_receive_bytes_total",
    ]
    counts = {}
    for name in required:
        query = {"query": f"count({name})"}
        if args.at:
            query["time"] = args.at
        result = get(prometheus, "/api/v1/query?" + urlencode(query))
        vector = result["data"]["result"]
        assert vector, f"Required metric absent: {name}"
        counts[name] = int(vector[0]["value"][1])
    output = {
        "verified_utc": datetime.now(UTC).isoformat(),
        "query_time": args.at,
        "target_status": target_status,
        "datasource_health": health,
        "dashboard_count": 3,
        "panel_count": len({(p["dashboard"], p["panel"]) for p in panels}),
        "query_count": len(panels),
        "required_metric_series": counts,
        "queries": panels,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(output, indent=2) + "\n", encoding="utf-8")
    print(f"Verified 3 dashboards, {output['panel_count']} panels, {len(panels)} queries.")
    print("Targets:", target_status)
    print(
        "Empty query results (may be expected outside an active load test):",
        [p["panel"] for p in panels if not p["series_count"]],
    )
    print("Evidence:", args.output)


if __name__ == "__main__":
    main()
