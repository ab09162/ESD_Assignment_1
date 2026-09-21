"""Save actual Prometheus samples for a UTC experiment window; never synthesize data."""

import argparse
import json
import math
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import urlopen

QUERIES = {
    "vus": "sum(k6_vus)",
    "requests_per_second": 'sum(rate(http_requests_total{job="campus-app"}[1m]))',
    "server_errors_per_second": (
        'sum(rate(http_requests_total{job="campus-app",status=~"5.."}[1m])) or vector(0)'
    ),
    "http_p95_seconds_1m": (
        "histogram_quantile(0.95,sum by(le)(rate(http_request_duration_seconds_bucket[1m])))"
    ),
    "http_p99_seconds_1m": (
        "histogram_quantile(0.99,sum by(le)(rate(http_request_duration_seconds_bucket[1m])))"
    ),
    "in_flight": 'sum(http_requests_in_progress{job="campus-app"})',
    "vm_cpu_percent": '100*(1-avg(rate(node_cpu_seconds_total{mode="idle"}[1m])))',
    "vm_memory_used_bytes": "node_memory_MemTotal_bytes-node_memory_MemAvailable_bytes",
    "vm_memory_percent": "100*(1-node_memory_MemAvailable_bytes/node_memory_MemTotal_bytes)",
    "app_rss_bytes": 'process_resident_memory_bytes{job="campus-app"}',
    "app_cpu_cores": 'rate(process_cpu_seconds_total{job="campus-app"}[1m])',
    "db_average_seconds": "sum(rate(db_operation_duration_seconds_sum[1m])) / "
    "clamp_min(sum(rate(db_operation_duration_seconds_count[1m])),0.000001)",
    "faults_per_second": "sum(rate(fault_injections_total[1m]))",
    "booking_conflicts_per_second": "sum(rate(booking_conflicts_total[1m]))",
    "logs_dropped_per_second": "sum(rate(logging_dropped_total[1m]))",
    "log_sink_errors_per_second": "sum(rate(logging_sink_errors_total[1m]))",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--prometheus", default="http://127.0.0.1:9090")
    args = parser.parse_args()
    result = {
        "collected_utc": datetime.now(UTC).isoformat(),
        "start": args.start,
        "end": args.end,
        "step_seconds": 5,
        "queries": {},
    }
    for name, expression in QUERIES.items():
        query = urlencode({"query": expression, "start": args.start, "end": args.end, "step": 5})
        with urlopen(args.prometheus + "/api/v1/query_range?" + query, timeout=20) as response:
            data = json.load(response)
        assert data["status"] == "success", name
        values = [
            float(value)
            for series in data["data"]["result"]
            for _, value in series["values"]
            if math.isfinite(float(value))
        ]
        result["queries"][name] = {
            "expression": expression,
            "series": data["data"]["result"],
            "sample_count": len(values),
            "sample_mean": sum(values) / len(values) if values else None,
            "sample_max": max(values) if values else None,
        }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print("Recorded actual Prometheus samples:", args.output)


if __name__ == "__main__":
    main()
