from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator


class TimeWindow(BaseModel):
    model_config = ConfigDict(extra="forbid")
    start_time: AwareDatetime
    end_time: AwareDatetime

    @model_validator(mode="after")
    def valid_window(self):
        self.start_time = self.start_time.astimezone(UTC)
        self.end_time = self.end_time.astimezone(UTC)
        if self.end_time <= self.start_time:
            raise ValueError("end_time must be after start_time")
        if self.end_time - self.start_time > timedelta(hours=8):
            raise ValueError("A booking or availability window must be at most 8 hours")
        return self


class BookingCreate(TimeWindow):
    room_id: int = Field(gt=0)

    @model_validator(mode="after")
    def future_booking(self):
        now = datetime.now(UTC)
        if self.start_time <= now:
            raise ValueError("start_time must be in the future")
        if self.end_time > now + timedelta(days=365):
            raise ValueError("Bookings must end within 365 days")
        return self


class BookingOut(BaseModel):
    id: UUID
    room_id: int
    start_time: datetime
    end_time: datetime
    status: Literal["confirmed", "cancelled"]
    created_at: datetime
    cancelled_at: datetime | None = None


class RoomOut(BaseModel):
    id: int
    name: str
    capacity: int


class AvailabilityOut(TimeWindow):
    room_id: int
    available: bool
