from typing import Annotated, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Request
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.responses import JSONResponse, Response

from app.schemas.booking import AvailabilityOut, BookingCreate, BookingOut, RoomOut, TimeWindow

router = APIRouter()


@router.get("/health", tags=["operations"])
async def health():
    return {"status": "ok"}


@router.get("/ready", tags=["operations"], responses={503: {"description": "Database unavailable"}})
async def ready(request: Request):
    if await request.app.state.repo.ready():
        return {"status": "ready"}
    return JSONResponse({"detail": "Database schema unavailable"}, status_code=503)


@router.get("/metrics", include_in_schema=False)
async def metrics(request: Request):
    return Response(
        generate_latest(request.app.state.metrics.registry),
        headers={"Content-Type": CONTENT_TYPE_LATEST},
    )


@router.get("/rooms", response_model=list[RoomOut], tags=["rooms"])
async def rooms(request: Request):
    return await request.app.state.repo.rooms()


@router.get("/rooms/{room_id}/availability", response_model=AvailabilityOut, tags=["rooms"])
async def availability(request: Request, room_id: int, window: TimeWindow = Depends()):
    return await request.app.state.service.availability(room_id, window)


@router.post(
    "/bookings",
    response_model=BookingOut,
    status_code=201,
    tags=["bookings"],
    responses={409: {"description": "Room/time conflict"}, 404: {"description": "No room"}},
)
async def create_booking(request: Request, data: BookingCreate):
    return await request.app.state.service.create(data)


@router.get("/bookings", response_model=list[BookingOut], tags=["bookings"])
async def list_bookings(
    request: Request,
    room_id: Annotated[int | None, Query(gt=0)] = None,
    status: Literal["confirmed", "cancelled"] | None = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 25,
    offset: Annotated[int, Query(ge=0, le=10000)] = 0,
):
    return await request.app.state.repo.list(room_id, status, limit, offset)


@router.get("/bookings/{booking_id}", response_model=BookingOut, tags=["bookings"])
async def get_booking(request: Request, booking_id: UUID):
    return await request.app.state.service.get(booking_id)


@router.delete("/bookings/{booking_id}", response_model=BookingOut, tags=["bookings"])
async def cancel_booking(request: Request, booking_id: UUID):
    """Idempotent cancellation. Retains the row for inspection."""
    return await request.app.state.service.cancel(booking_id)
