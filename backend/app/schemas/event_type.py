from pydantic import BaseModel

from app.schemas.base import TrackedRead


class EventTypeBase(BaseModel):
    name: str
    color: str | None = None
    is_active: bool = True
    tracks_service_hours: bool = False
    tracks_camping_nights: bool = False
    tracks_mileage: bool = False
    allow_signups: bool = True
    require_permission_slip: bool = False
    allow_guests: bool = False
    is_online: bool = False


class EventTypeUpdate(BaseModel):
    name: str | None = None
    color: str | None = None
    is_active: bool | None = None
    tracks_service_hours: bool | None = None
    tracks_camping_nights: bool | None = None
    tracks_mileage: bool | None = None
    allow_signups: bool | None = None
    require_permission_slip: bool | None = None
    allow_guests: bool | None = None
    is_online: bool | None = None


class EventTypeRead(EventTypeBase, TrackedRead):
    is_system: bool
