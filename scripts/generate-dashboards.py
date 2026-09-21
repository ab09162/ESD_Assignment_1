"""Regenerate committed Grafana JSON with Python's standard library."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTTP = 'http_requests_total{job="campus-app"}'
RATE = f"sum(rate({HTTP}[1m]))"
SUCCESS = 'sum(rate(http_requests_total{job="campus-app",status=~"2.."}[1m]))'
ERROR = 'sum(rate(http_requests_total{job="campus-app",status=~"5.."}[1m]))'
DENOM = f"clamp_min({RATE}, 0.000001)"


def latency(q):
    return (
        f"histogram_quantile({q}, sum by (le) "
        '(rate(http_request_duration_seconds_bucket{job="campus-app"}[5m])))'
    )


def panel(title, expr, unit, description, legend=None):
    expressions = expr if isinstance(expr, list) else [(expr, legend or title)]
    return {
        "title": title,
        "type": "timeseries",
        "description": description,
        "datasource": {"type": "prometheus", "uid": "prometheus"},
        "fieldConfig": {"defaults": {"unit": unit, "min": 0}, "overrides": []},
        "options": {
            "legend": {"displayMode": "list", "placement": "bottom", "calcs": ["lastNotNull"]},
            "tooltip": {"mode": "multi", "sort": "desc"},
        },
        "targets": [
            {
                "expr": query,
                "legendFormat": label,
                "refId": chr(65 + i),
                "range": True,
                "datasource": {"type": "prometheus", "uid": "prometheus"},
            }
            for i, (query, label) in enumerate(expressions)
        ],
    }


def save(name, title, panels):
    for i, item in enumerate(panels):
        item.update(id=i + 1, gridPos={"x": (i % 2) * 12, "y": (i // 2) * 8, "w": 12, "h": 8})
    result = {
        "uid": name,
        "title": title,
        "schemaVersion": 40,
        "version": 1,
        "tags": ["campus", "assignment"],
        "timezone": "utc",
        "editable": False,
        "refresh": "5s",
        "time": {"from": "now-30m", "to": "now"},
        "panels": panels,
        "annotations": {"list": []},
    }
    path = ROOT / "observability" / "grafana" / "dashboards" / f"{name}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def main():
    average = (
        'sum(rate(http_request_duration_seconds_sum{job="campus-app"}[5m])) / '
        'clamp_min(sum(rate(http_request_duration_seconds_count{job="campus-app"}[5m])), 0.000001)'
    )
    db = (
        'sum by (operation) (rate(db_operation_duration_seconds_sum{job="campus-app"}[5m])) / '
        "clamp_min(sum by (operation) "
        '(rate(db_operation_duration_seconds_count{job="campus-app"}[5m])), 0.000001)'
    )
    cpu = '100 * (1 - avg by (machine) (rate(node_cpu_seconds_total{mode="idle"}[1m])))'
    memory = "100 * (1 - node_memory_MemAvailable_bytes / node_memory_MemTotal_bytes)"
    save(
        "campus-app",
        "Campus | Application & business",
        [
            panel(
                "Requests per second",
                RATE,
                "reqps",
                "Business traffic only; 1 minute rolling rate.",
            ),
            panel(
                "Successful requests per second", SUCCESS + " or vector(0)", "reqps", "HTTP 2xx."
            ),
            panel(
                "Server errors per second (5xx)",
                ERROR + " or vector(0)",
                "reqps",
                "True server failures; excludes 409 conflicts.",
            ),
            panel(
                "Server error percentage",
                f"100 * ({ERROR} or vector(0)) / {DENOM}",
                "percent",
                "5xx / all business requests.",
            ),
            panel(
                "p95 request latency",
                latency(0.95),
                "s",
                "Histogram estimate over 5m; aggregate buckets by le.",
            ),
            panel(
                "p99 request latency",
                latency(0.99),
                "s",
                "Tail latency; estimate limited by bucket resolution and sample count.",
            ),
            panel(
                "Average HTTP latency", average, "s", "Sum of durations divided by count over 5m."
            ),
            panel(
                "In-flight requests",
                'sum(http_requests_in_progress{job="campus-app"})',
                "short",
                "Instantaneous concurrency; 5s scrapes can miss short spikes.",
            ),
            panel(
                "Requests by route",
                f"sum by (route) (rate({HTTP}[1m]))",
                "reqps",
                "Normalized templates, never raw IDs.",
                "{{route}}",
            ),
            panel(
                "Requests by status",
                f"sum by (status) (rate({HTTP}[1m]))",
                "reqps",
                "409 is an expected domain conflict; 422 validation; 5xx server failures.",
                "{{status}}",
            ),
            panel(
                "Booking creation rate",
                'sum(rate(bookings_created_total{job="campus-app"}[1m]))',
                "ops",
                "Only committed inserts.",
            ),
            panel(
                "Booking cancellation rate",
                'sum(rate(bookings_cancelled_total{job="campus-app"}[1m]))',
                "ops",
                "Only first cancellation transition; retries do not inflate counts.",
            ),
            panel(
                "Booking conflict rate",
                'sum(rate(booking_conflicts_total{job="campus-app"}[1m]))',
                "ops",
                "Database exclusion violations (409).",
            ),
            panel(
                "Active bookings",
                'active_bookings{job="campus-app"}',
                "short",
                "Confirmed bookings ending in the future; "
                "5s DB refresh, includes future reservations.",
            ),
            panel(
                "DB operation average latency",
                db,
                "s",
                "Summary sum/count; includes pool wait and commit. No Summary percentiles.",
                "{{operation}}",
            ),
            panel(
                "Booking conflict percentage (own exploration)",
                "100 * sum(rate(booking_conflicts_total[5m])) / "
                "clamp_min(sum(rate(booking_conflicts_total[5m])) + "
                "sum(rate(bookings_created_total[5m])), 0.000001)",
                "percent",
                "Conflicts / (created + conflicts). Rising contention can indicate "
                "demand for rooms even when 5xx is zero; invalid payloads excluded.",
            ),
            panel(
                "Route p95 latency",
                "histogram_quantile(0.95, sum by (le, route) "
                "(rate(http_request_duration_seconds_bucket[5m])))",
                "s",
                "Identify the slow endpoint.",
                "{{route}}",
            ),
            panel(
                "Mean booking lead time",
                "sum(rate(booking_lead_time_seconds_sum[5m])) / "
                "clamp_min(sum(rate(booking_lead_time_seconds_count[5m])), 0.000001)",
                "s",
                "How far ahead accepted bookings are made; "
                "load-test synthetic dates influence this.",
            ),
            panel(
                "Business gauge refresh health",
                [
                    ("booking_metrics_refresh_success", "success (1=yes)"),
                    ("time() - booking_metrics_last_refresh_timestamp_seconds", "age seconds"),
                ],
                "short",
                "Treat active-booking value as stale if success=0 or age exceeds 10s.",
            ),
            panel(
                "Log pipeline local loss",
                [
                    ("sum(rate(logging_dropped_total[1m]))", "queue drops/s"),
                    ("sum(rate(logging_sink_errors_total[1m]))", "sink errors/s"),
                ],
                "ops",
                "Logging is best effort and cannot block API requests on remote backends.",
            ),
        ],
    )
    save(
        "campus-load",
        "Campus | Load & saturation",
        [
            panel(
                "k6 virtual users",
                "k6_vus",
                "short",
                "Remote-written by k6 every 5s. Run one load generator at a time.",
                "{{profile}} {{phase}}",
            ),
            panel(
                "Server throughput",
                RATE,
                "reqps",
                "Compare against VUs: a plateau can indicate saturation.",
            ),
            panel(
                "Server p95 / p99",
                [(latency(0.95), "p95"), (latency(0.99), "p99")],
                "s",
                "5m rolling estimates retain preceding phases; use absolute time ranges.",
            ),
            panel(
                "Client p95 / p99",
                [
                    ("k6_http_req_duration_p95", "p95 {{name}} {{phase}}"),
                    ("k6_http_req_duration_p99", "p99 {{name}} {{phase}}"),
                ],
                "s",
                "k6 remote-write converts HTTP durations to seconds; "
                "never average percentiles across series.",
            ),
            panel(
                "Server error percentage",
                f"100 * ({ERROR} or vector(0)) / {DENOM}",
                "percent",
                "5xx only.",
            ),
            panel(
                "k6 unexpected response fraction",
                "k6_unexpected_responses_rate",
                "percentunit",
                "Every business response checked; deliberate 409 handled separately.",
                "{{profile}} {{phase}}",
            ),
            panel(
                "In-flight requests",
                'sum(http_requests_in_progress{job="campus-app"})',
                "short",
                "Requests including injected delay and DB wait.",
            ),
            panel(
                "VM CPU usage",
                cpu,
                "percent",
                "Docker Desktop Linux VM, not the physical Windows host.",
                "{{machine}}",
            ),
            panel(
                "VM memory usage",
                memory,
                "percent",
                "Linux MemAvailable based; shared VM resources.",
                "{{machine}}",
            ),
            panel(
                "DB average latency",
                db,
                "s",
                "Pool wait and SQL/transaction time combined.",
                "{{operation}}",
            ),
            panel(
                "App resident memory",
                'process_resident_memory_bytes{job="campus-app"}',
                "bytes",
                "Python process RSS, separate from whole-VM memory.",
            ),
            panel(
                "App CPU cores used",
                'rate(process_cpu_seconds_total{job="campus-app"}[1m])',
                "short",
                "1 means one full CPU core.",
            ),
            panel(
                "VM network receive / transmit",
                [
                    ('sum(rate(node_network_receive_bytes_total{device!="lo"}[1m]))', "receive"),
                    ('sum(rate(node_network_transmit_bytes_total{device!="lo"}[1m]))', "transmit"),
                ],
                "Bps",
                "Exporter network namespace scope may differ from root filesystem; see README.",
            ),
            panel(
                "Injected delays per second",
                "sum(rate(fault_injections_total[1m]))",
                "ops",
                "Every fifth business request when the local fault is enabled.",
            ),
        ],
    )
    save(
        "campus-node",
        "Campus | Docker Desktop Linux VM",
        [
            panel(
                "VM CPU usage",
                cpu,
                "percent",
                "CPU exported by the Linux VM, not Windows.",
                "{{machine}}",
            ),
            panel(
                "VM memory usage",
                memory,
                "percent",
                "Linux memory usage based on available bytes.",
                "{{machine}}",
            ),
            panel(
                "Disk usage",
                '100 * (1 - node_filesystem_avail_bytes{fstype!~"tmpfs|overlay|squashfs"} / '
                'node_filesystem_size_bytes{fstype!~"tmpfs|overlay|squashfs"})',
                "percent",
                "Mounted Linux filesystems; never claim this is Windows C:.",
                "{{mountpoint}}",
            ),
            panel(
                "Disk I/O",
                [
                    ("rate(node_disk_read_bytes_total[1m])", "read {{device}}"),
                    ("rate(node_disk_written_bytes_total[1m])", "write {{device}}"),
                ],
                "Bps",
                "VM block devices, if available.",
            ),
            panel(
                "Network receive",
                'rate(node_network_receive_bytes_total{device!="lo"}[1m])',
                "Bps",
                "Network namespace exposed by Docker; inspect device labels.",
                "{{device}}",
            ),
            panel(
                "Network transmit",
                'rate(node_network_transmit_bytes_total{device!="lo"}[1m])',
                "Bps",
                "May reflect exporter container namespace on Docker Desktop.",
                "{{device}}",
            ),
        ],
    )


if __name__ == "__main__":
    main()
