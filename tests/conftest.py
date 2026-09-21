import os
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr
from sqlalchemy import text

from app.core.config import Settings
from app.db.engine import initialize_schema, make_engine
from app.main import create_app
from app.observability.metrics import Metrics
from app.repositories.bookings import BookingRepository


@pytest.fixture
def payload():
    start = datetime.now(UTC) + timedelta(days=1)
    return {
        "room_id": 1,
        "start_time": start.isoformat(),
        "end_time": (start + timedelta(hours=1)).isoformat(),
    }


@pytest.fixture
def fake_repo(payload):
    booking = {
        **payload,
        "id": str(uuid4()),
        "status": "confirmed",
        "created_at": datetime.now(UTC).isoformat(),
        "cancelled_at": None,
    }
    return SimpleNamespace(
        ready=AsyncMock(return_value=True),
        active_count=AsyncMock(return_value=0),
        rooms=AsyncMock(return_value=[{"id": 1, "name": "Study Room", "capacity": 4}]),
        room_exists=AsyncMock(return_value=True),
        availability=AsyncMock(return_value=True),
        create=AsyncMock(return_value=booking),
        get=AsyncMock(return_value=booking),
        list=AsyncMock(return_value=[booking]),
        cancel=AsyncMock(return_value=({**booking, "status": "cancelled"}, True)),
    )


@pytest.fixture
def client(fake_repo, tmp_path):
    settings = Settings(_env_file=None, log_file=str(tmp_path / "app.jsonl"))
    app = create_app(settings, fake_repo)
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
async def database():
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("Set TEST_DATABASE_URL to a disposable PostgreSQL database ending in _test")
    # Integration cleanup is destructive; refuse application databases.
    from sqlalchemy.engine import make_url

    if not (make_url(url).database or "").endswith("_test"):
        pytest.fail("TEST_DATABASE_URL database name must end in _test")
    engine = make_engine(Settings(_env_file=None, database_url=SecretStr(url)))
    await initialize_schema(engine)
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE bookings"))
    yield engine
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE bookings"))
    await engine.dispose()


@pytest.fixture
async def real_client(database, tmp_path):
    repo = BookingRepository(database, Metrics())
    app = create_app(Settings(_env_file=None, log_file=str(tmp_path / "real.jsonl")), repo)
    repo.metrics = app.state.metrics
    async with app.router.lifespan_context(app):
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            yield client, app
