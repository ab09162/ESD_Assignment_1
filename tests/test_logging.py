import json
import logging
import queue

from app.observability.logging import JsonFormatter, NonBlockingHandler
from app.observability.metrics import Metrics


def test_json_record_is_searchable_and_escapes_newlines():
    record = logging.LogRecord("campus", logging.INFO, "", 0, "hello\nworld", (), None)
    record.fields = {"request_id": "test-1", "route": "/bookings", "status_code": 201}
    line = JsonFormatter().format(record)
    assert "\n" not in line
    data = json.loads(line)
    assert data["service"] == "campus-booking"
    assert data["severity"] == "INFO"
    assert data["status_code"] == 201
    assert data["timestamp"].endswith("+00:00")


def test_full_queue_drops_records_without_blocking():
    metrics = Metrics()
    records = queue.Queue(maxsize=1)
    handler = NonBlockingHandler(records, metrics)
    record = logging.LogRecord("campus", 20, "", 0, "request_completed", (), None)
    handler.emit(record)
    handler.emit(record)
    assert records.qsize() == 1
    assert metrics.registry.get_sample_value("logging_dropped_total") == 1
