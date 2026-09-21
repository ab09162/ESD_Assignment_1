import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, OperationalError

from app.core.config import Settings
from app.main import create_app


def test_health_readiness_rooms_and_openapi(client):
    assert client.get("/health").json() == {"status": "ok"}
    assert client.get("/ready").status_code == 200
    assert client.get("/rooms").json()[0]["capacity"] == 4
    assert "/bookings" in client.get("/openapi.json").json()["paths"]


def test_booking_lifecycle_and_committed_metrics(client, payload, fake_repo):
    response = client.post("/bookings", json=payload)
    assert response.status_code == 201
    booking_id = response.json()["id"]
    assert client.get(f"/bookings/{booking_id}").status_code == 200
    assert client.get("/bookings").status_code == 200
    assert client.delete(f"/bookings/{booking_id}").json()["status"] == "cancelled"
    fake_repo.cancel.return_value = (fake_repo.cancel.return_value[0], False)
    assert client.delete(f"/bookings/{booking_id}").status_code == 200
    metrics = client.get("/metrics").text
    assert "bookings_created_total 1.0" in metrics
    assert "bookings_cancelled_total 1.0" in metrics


@pytest.mark.parametrize(
    "change",
    [
        {"room_id": 0},
        {"start_time": "2020-01-01T00:00:00Z"},
        {"start_time": "2030-01-01T00:00:00"},
        {"unexpected": "secret"},
        {"end_time": "2020-01-01T00:00:00Z"},
        {"start_time": "not-a-date"},
    ],
)
def test_validation(client, payload, change):
    result = client.post("/bookings", json={**payload, **change})
    assert result.status_code == 422
    assert "secret" not in result.text


def test_availability_validation(client, payload):
    query = {key: payload[key] for key in ("start_time", "end_time")}
    assert client.get("/rooms/1/availability", params=query).json()["available"] is True
    query["end_time"] = "2020-01-01T00:00:00Z"
    assert client.get("/rooms/1/availability", params=query).status_code == 422


def test_database_overlap_returns_clean_conflict(client, fake_repo, payload):
    fake_repo.create.side_effect = IntegrityError(
        "INSERT secret", {}, SimpleNamespace(sqlstate="23P01")
    )
    response = client.post("/bookings", json=payload)
    assert response.status_code == 409
    assert "secret" not in response.text
    metrics = client.get("/metrics").text
    assert "booking_conflicts_total 1.0" in metrics
    assert "bookings_created_total 0.0" in metrics


def test_missing_room_and_booking(client, fake_repo, payload):
    fake_repo.create.side_effect = IntegrityError("", {}, SimpleNamespace(sqlstate="23503"))
    assert client.post("/bookings", json=payload).status_code == 404
    fake_repo.get.return_value = None
    assert client.get("/bookings/00000000-0000-0000-0000-000000000001").status_code == 404


def test_request_id_and_bounded_metric_labels(client):
    assert (
        client.get("/rooms", headers={"X-Request-ID": "demo-safe-123"}).headers["X-Request-ID"]
        == "demo-safe-123"
    )
    bad = "a" * 100
    assert client.get("/rooms", headers={"X-Request-ID": bad}).headers["X-Request-ID"] != bad
    for number in range(10):
        assert client.get(f"/random/{number}").status_code == 404
        assert client.get(f"/bookings/00000000-0000-0000-0000-{number:012d}").status_code == 200
    for verb in ["ARBITRARY", "CUSTOM"]:
        assert client.request(verb, "/rooms").status_code == 405
    body = client.get("/metrics").text
    assert 'route="unmatched"' in body
    assert 'route="/bookings/{booking_id}"' in body
    assert 'method="OTHER"' in body
    assert "/random/1" not in body
    assert "request_id=" not in body
    assert 'route="/metrics"' not in body
    assert 'route="/health"' not in body


def test_errors_keep_correlation_and_release_gauge(client, fake_repo):
    fake_repo.rooms.side_effect = RuntimeError("private data must not escape")
    response = client.get("/rooms", headers={"X-Request-ID": "failure-demo"})
    assert response.status_code == 500
    assert response.headers["X-Request-ID"] == "failure-demo"
    assert "private data" not in response.text
    assert (
        'http_requests_in_progress{method="GET",route="/rooms"} 0.0' in client.get("/metrics").text
    )


def test_database_down_is_503_but_liveness_survives(client, fake_repo):
    fake_repo.ready.side_effect = OperationalError("secret SQL", {}, Exception("secret password"))
    response = client.get("/ready")
    assert response.status_code == 503
    assert response.headers["Retry-After"] == "2"
    assert "secret" not in response.text
    assert client.get("/health").status_code == 200
    assert client.get("/metrics").status_code == 200


def test_fault_every_fifth_request(fake_repo, tmp_path):
    log = tmp_path / "fault.jsonl"
    settings = Settings(
        _env_file=None, log_file=str(log), fault_delay_enabled=True, fault_delay_ms=0
    )
    app = create_app(settings, fake_repo)
    with TestClient(app) as client:
        for _ in range(10):
            assert client.get("/rooms").status_code == 200
            client.get("/health")
        assert "fault_injections_total 2.0" in client.get("/metrics").text
    records = [json.loads(line) for line in log.read_text().splitlines()]
    assert len([r for r in records if r["message"] == "fault_delay_injected"]) == 2


def test_timeout_releases_gauge(fake_repo, tmp_path):
    import asyncio

    async def never_returns():
        await asyncio.Event().wait()

    fake_repo.rooms.side_effect = never_returns
    app = create_app(
        Settings(
            _env_file=None, log_file=str(tmp_path / "timeout.jsonl"), request_timeout_seconds=0.02
        ),
        fake_repo,
    )
    with TestClient(app) as client:
        result = client.get("/rooms", headers={"X-Request-ID": "timeout-demo"})
        assert result.status_code == 504
        assert result.headers["X-Request-ID"] == "timeout-demo"
        assert (
            'http_requests_in_progress{method="GET",route="/rooms"} 0.0'
            in client.get("/metrics").text
        )


def test_fault_rejected_outside_local_environment():
    with pytest.raises(ValueError, match="only in the local"):
        Settings(_env_file=None, environment="production", fault_delay_enabled=True)
