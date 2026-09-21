import json
import logging
import logging.handlers
import queue
import sys
import threading
from datetime import UTC, datetime
from pathlib import Path

from app.observability.metrics import Metrics


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        data = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(),
            "service": "campus-booking",
            "severity": record.levelname,
            "message": record.getMessage(),
        }
        data.update(getattr(record, "fields", {}))
        return json.dumps(data, ensure_ascii=True, separators=(",", ":"))


class SafeRotatingHandler(logging.handlers.RotatingFileHandler):
    def __init__(self, filename, metrics):
        self.metrics = metrics
        super().__init__(filename, maxBytes=10 * 1024 * 1024, backupCount=7, encoding="utf-8")

    def handleError(self, record):  # noqa: N802
        self.metrics.log_errors.inc()


class SafeStreamHandler(logging.StreamHandler):
    def __init__(self, metrics):
        self.metrics = metrics
        super().__init__(sys.stdout)

    def handleError(self, record):  # noqa: N802
        self.metrics.log_errors.inc()


class NonBlockingHandler(logging.Handler):
    def __init__(self, records, metrics):
        super().__init__()
        self.records = records
        self.metrics = metrics

    def emit(self, record):
        try:
            self.records.put_nowait(record)
        except queue.Full:
            self.metrics.logs_dropped.inc()


class LogRuntime:
    """A bounded queue separates API latency from file/stdout I/O; drain is time bounded."""

    def __init__(self, filename: str, capacity: int, metrics: Metrics):
        self.records = queue.Queue(maxsize=capacity)
        self.stop = threading.Event()
        self.logger = logging.Logger("campus", level=logging.INFO)
        self.logger.addHandler(NonBlockingHandler(self.records, metrics))
        self.sinks = [SafeStreamHandler(metrics)]
        try:
            Path(filename).parent.mkdir(parents=True, exist_ok=True)
            self.sinks.append(SafeRotatingHandler(filename, metrics))
        except OSError:
            metrics.log_errors.inc()
        for sink in self.sinks:
            sink.setFormatter(JsonFormatter())
        self.thread = threading.Thread(target=self._run, name="json-log-writer", daemon=True)
        self.thread.start()

    def _run(self):
        while not self.stop.is_set() or not self.records.empty():
            try:
                record = self.records.get(timeout=0.1)
            except queue.Empty:
                continue
            for sink in self.sinks:
                sink.handle(record)
            self.records.task_done()
        for sink in self.sinks:
            sink.close()

    def close(self):
        self.stop.set()
        self.thread.join(timeout=2)
