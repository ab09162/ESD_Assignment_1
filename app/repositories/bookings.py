from uuid import UUID, uuid4

from sqlalchemy import text

from app.observability.metrics import Metrics
from app.schemas.booking import BookingCreate, TimeWindow


class BookingRepository:
    def __init__(self, engine, metrics: Metrics):
        self.engine, self.metrics = engine, metrics

    async def ready(self):
        with self.metrics.db_timer("readiness"):
            async with self.engine.connect() as conn:
                return (
                    await conn.scalar(text("SELECT version FROM schema_version WHERE version=1"))
                    == 1
                )

    async def rooms(self):
        with self.metrics.db_timer("list_rooms"):
            async with self.engine.connect() as conn:
                return (
                    (await conn.execute(text("SELECT * FROM rooms ORDER BY id"))).mappings().all()
                )

    async def room_exists(self, room_id: int):
        with self.metrics.db_timer("get_room"):
            async with self.engine.connect() as conn:
                return (
                    await conn.scalar(text("SELECT 1 FROM rooms WHERE id=:id"), {"id": room_id})
                    == 1
                )

    async def availability(self, room_id: int, window: TimeWindow):
        with self.metrics.db_timer("availability"):
            async with self.engine.connect() as conn:
                return not await conn.scalar(
                    text("""
                    SELECT EXISTS(SELECT 1 FROM bookings
                    WHERE room_id=:room_id AND status='confirmed'
                    AND tstzrange(start_time, end_time, '[)') &&
                        tstzrange(:start_time, :end_time, '[)'))
                """),
                    {"room_id": room_id, **window.model_dump()},
                )

    async def create(self, data: BookingCreate):
        with self.metrics.db_timer("create_booking"):
            async with self.engine.begin() as conn:
                result = await conn.execute(
                    text("""
                    INSERT INTO bookings(id, room_id, start_time, end_time)
                    VALUES (:id, :room_id, :start_time, :end_time) RETURNING *
                """),
                    {"id": uuid4(), **data.model_dump()},
                )
                booking = dict(result.mappings().one())
            # Returning only after commit prevents counting a rolled-back booking.
            return booking

    async def get(self, booking_id: UUID):
        with self.metrics.db_timer("get_booking"):
            async with self.engine.connect() as conn:
                row = (
                    (
                        await conn.execute(
                            text("SELECT * FROM bookings WHERE id=:id"), {"id": booking_id}
                        )
                    )
                    .mappings()
                    .first()
                )
                return dict(row) if row else None

    async def list(self, room_id: int | None, status: str | None, limit: int, offset: int):
        clauses, params = [], {"limit": limit, "offset": offset}
        if room_id is not None:
            clauses.append("room_id=:room_id")
            params["room_id"] = room_id
        if status is not None:
            clauses.append("status=:status")
            params["status"] = status
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        with self.metrics.db_timer("list_bookings"):
            async with self.engine.connect() as conn:
                return (
                    (
                        await conn.execute(
                            text(
                                "SELECT * FROM bookings"
                                + where
                                + " ORDER BY start_time, id LIMIT :limit OFFSET :offset"
                            ),
                            params,
                        )
                    )
                    .mappings()
                    .all()
                )

    async def cancel(self, booking_id: UUID):
        with self.metrics.db_timer("cancel_booking"):
            async with self.engine.begin() as conn:
                row = (
                    (
                        await conn.execute(
                            text("""
                    UPDATE bookings SET status='cancelled', cancelled_at=now()
                    WHERE id=:id AND status='confirmed' RETURNING *
                """),
                            {"id": booking_id},
                        )
                    )
                    .mappings()
                    .first()
                )
                if row:
                    result, changed = dict(row), True
                else:
                    row = (
                        (
                            await conn.execute(
                                text("SELECT * FROM bookings WHERE id=:id"), {"id": booking_id}
                            )
                        )
                        .mappings()
                        .first()
                    )
                    result, changed = dict(row) if row else None, False
            return result, changed

    async def active_count(self):
        with self.metrics.db_timer("active_count"):
            async with self.engine.connect() as conn:
                return await conn.scalar(
                    text(
                        "SELECT count(*) FROM bookings "
                        "WHERE status='confirmed' AND end_time > now()"
                    )
                )
