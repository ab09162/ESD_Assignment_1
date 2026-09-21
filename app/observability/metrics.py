from contextlib import contextmanager
from time import perf_counter

from prometheus_client import (
    CollectorRegistry,
    Counter,
    Gauge,
    GCCollector,
    Histogram,
    PlatformCollector,
    ProcessCollector,
    Summary,
)


class Metrics:
    """One registry per app instance; never put identifiers in metric labels."""

    def __init__(self):
        self.registry = CollectorRegistry()
        GCCollector(registry=self.registry)
        PlatformCollector(registry=self.registry)
        ProcessCollector(registry=self.registry)
        self.requests = Counter(
            "http_requests_total",
            "Completed business HTTP requests",
            ["method", "route", "status"],
            registry=self.registry,
        )
        self.in_progress = Gauge(
            "http_requests_in_progress",
            "Business requests currently executing",
            ["method", "route"],
            registry=self.registry,
        )
        self.duration = Histogram(
            "http_request_duration_seconds",
            "Business request server duration",
            ["method", "route", "status"],
            buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10),
            registry=self.registry,
        )
        self.db_duration = Summary(
            "db_operation_duration_seconds",
            "Repository wall time including pool wait and commit",
            ["operation"],
            registry=self.registry,
        )
        self.created = Counter(
            "bookings_created_total", "Committed bookings", registry=self.registry
        )
        self.cancelled = Counter(
            "bookings_cancelled_total",
            "Committed cancellation transitions",
            registry=self.registry,
        )
        self.conflicts = Counter(
            "booking_conflicts_total",
            "Database-rejected overlaps",
            registry=self.registry,
        )
        self.active = Gauge(
            "active_bookings",
            "Confirmed bookings whose end is in the future (periodic DB count)",
            registry=self.registry,
        )
        self.refresh_ok = Gauge(
            "booking_metrics_refresh_success",
            "Whether the most recent DB gauge refresh succeeded",
            registry=self.registry,
        )
        self.refresh_timestamp = Gauge(
            "booking_metrics_last_refresh_timestamp_seconds",
            "Last successful gauge refresh UTC epoch",
            registry=self.registry,
        )
        self.lead_time = Histogram(
            "booking_lead_time_seconds",
            "Time from accepted booking creation to start",
            buckets=(60, 300, 900, 3600, 21600, 86400, 604800, 2592000, 31536000),
            registry=self.registry,
        )
        self.faults = Counter(
            "fault_injections_total",
            "Deliberate local latency injections",
            registry=self.registry,
        )
        self.logs_dropped = Counter(
            "logging_dropped_total",
            "Log records dropped because the bounded queue is full",
            registry=self.registry,
        )
        self.log_errors = Counter(
            "logging_sink_errors_total",
            "Failed local log writes",
            registry=self.registry,
        )

    @contextmanager
    def db_timer(self, operation: str):
        start = perf_counter()
        try:
            yield
        finally:
            self.db_duration.labels(operation).observe(perf_counter() - start)
