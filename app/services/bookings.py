from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError


class DomainError(Exception):
    def __init__(self, status: int, detail: str):
        self.status, self.detail = status, detail


class BookingService:
    def __init__(self, repository, metrics):
        self.repo, self.metrics = repository, metrics

    async def create(self, data):
        try:
            booking = await self.repo.create(data)
        except IntegrityError as exc:
            code = getattr(exc.orig, "sqlstate", None)
            if code == "23P01":
                self.metrics.conflicts.inc()
                raise DomainError(409, "Room already reserved for an overlapping time") from None
            if code == "23503":
                raise DomainError(404, "Room not found") from None
            raise
        self.metrics.created.inc()
        self.metrics.lead_time.observe(
            max(0, (data.start_time - datetime.now(UTC)).total_seconds())
        )
        return booking

    async def get(self, booking_id):
        booking = await self.repo.get(booking_id)
        if booking is None:
            raise DomainError(404, "Booking not found")
        return booking

    async def cancel(self, booking_id):
        booking, changed = await self.repo.cancel(booking_id)
        if booking is None:
            raise DomainError(404, "Booking not found")
        if changed:
            self.metrics.cancelled.inc()
        return booking

    async def availability(self, room_id, window):
        if not await self.repo.room_exists(room_id):
            raise DomainError(404, "Room not found")
        available = await self.repo.availability(room_id, window)
        return {"room_id": room_id, **window.model_dump(), "available": available}
