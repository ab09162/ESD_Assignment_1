import asyncio
from datetime import datetime, timedelta

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

pytestmark = pytest.mark.integration


async def test_real_lifecycle_adjacency_and_cancel(real_client, payload):
    client, app = real_client
    assert (await client.get("/ready")).status_code == 200
    assert len((await client.get("/rooms")).json()) == 3
    created = await client.post("/bookings", json=payload)
    assert created.status_code == 201, created.text
    booking_id = created.json()["id"]
    assert (await client.get(f"/bookings/{booking_id}")).json()["room_id"] == 1
    query = {key: payload[key] for key in ("start_time", "end_time")}
    assert not (await client.get("/rooms/1/availability", params=query)).json()["available"]
    assert (await client.post("/bookings", json=payload)).status_code == 409
    adjacent = {
        **payload,
        "start_time": payload["end_time"],
        "end_time": (datetime.fromisoformat(payload["end_time"]) + timedelta(hours=1)).isoformat(),
    }
    assert (await client.post("/bookings", json=adjacent)).status_code == 201
    assert len((await client.get("/bookings", params={"room_id": 1})).json()) == 2
    assert (await client.delete(f"/bookings/{booking_id}")).status_code == 200
    assert (await client.delete(f"/bookings/{booking_id}")).status_code == 200
    assert app.state.metrics.registry.get_sample_value("bookings_cancelled_total") == 1
    assert (await client.post("/bookings", json=payload)).status_code == 201
    assert (await app.state.repo.active_count()) == 2


async def test_20_simultaneous_same_slot_exactly_one_winner(real_client, payload, database):
    client, app = real_client
    responses = await asyncio.gather(*[client.post("/bookings", json=payload) for _ in range(20)])
    statuses = [response.status_code for response in responses]
    assert statuses.count(201) == 1, statuses
    assert statuses.count(409) == 19, statuses
    async with database.connect() as conn:
        assert (
            await conn.scalar(text("SELECT count(*) FROM bookings WHERE status='confirmed'")) == 1
        )
    assert app.state.metrics.registry.get_sample_value("bookings_created_total") == 1
    assert app.state.metrics.registry.get_sample_value("booking_conflicts_total") == 19


async def test_database_constraint_protects_direct_writers(real_client, database, payload):
    client, _ = real_client
    assert (await client.post("/bookings", json=payload)).status_code == 201
    with pytest.raises(IntegrityError) as caught:
        async with database.begin() as conn:
            await conn.execute(
                text("""
                INSERT INTO bookings(id, room_id, start_time, end_time)
                SELECT '00000000-0000-0000-0000-000000000099'::uuid, room_id, start_time, end_time
                FROM bookings LIMIT 1
            """)
            )
    assert caught.value.orig.sqlstate == "23P01"


async def test_parallel_cancel_counts_once(real_client, payload):
    client, app = real_client
    result = await client.post("/bookings", json=payload)
    booking_id = result.json()["id"]
    responses = await asyncio.gather(*[client.delete(f"/bookings/{booking_id}") for _ in range(10)])
    assert all(response.status_code == 200 for response in responses)
    assert app.state.metrics.registry.get_sample_value("bookings_cancelled_total") == 1


async def test_real_missing_room(real_client, payload):
    client, _ = real_client
    assert (await client.post("/bookings", json={**payload, "room_id": 999})).status_code == 404


async def test_schema_initialization_is_repeatable(database):
    from app.db.engine import initialize_schema

    await initialize_schema(database)
    async with database.connect() as conn:
        assert await conn.scalar(text("SELECT count(*) FROM rooms")) == 3
