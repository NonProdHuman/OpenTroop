from __future__ import annotations

import uuid

from pydantic import BaseModel, model_validator

from app.models.enums import PositionScope
from app.schemas.base import TrackedRead
from app.schemas.types import UtcDateTime


class EventSlotBase(BaseModel):
    name: str
    description: str | None = None
    capacity: int | None = None
    applies_to: PositionScope = PositionScope.ANY
    starts_at: UtcDateTime | None = None
    ends_at: UtcDateTime | None = None
    sort_order: int = 0

    @model_validator(mode="after")
    def _validate(self) -> EventSlotBase:
        if self.capacity is not None and self.capacity < 1:
            raise ValueError("capacity must be a positive integer or null (unlimited)")
        if (
            self.starts_at is not None
            and self.ends_at is not None
            and self.ends_at < self.starts_at
        ):
            raise ValueError("ends_at must be on or after starts_at")
        return self


class EventSlotCreate(EventSlotBase):
    pass


class EventSlotUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    capacity: int | None = None
    applies_to: PositionScope | None = None
    starts_at: UtcDateTime | None = None
    ends_at: UtcDateTime | None = None
    sort_order: int | None = None

    @model_validator(mode="after")
    def _validate(self) -> EventSlotUpdate:
        if self.capacity is not None and self.capacity < 1:
            raise ValueError("capacity must be a positive integer or null (unlimited)")
        return self


class EventSlotSignupCreate(BaseModel):
    member_id: uuid.UUID
    comment: str | None = None


class EventSlotSignupRead(TrackedRead):
    slot_id: uuid.UUID
    member_id: uuid.UUID
    member_name: str
    comment: str | None
    signed_up_by_id: uuid.UUID | None
    signed_up_at: UtcDateTime


class EventSlotRead(EventSlotBase, TrackedRead):
    event_id: uuid.UUID
    signups: list[EventSlotSignupRead]
    # null when the slot is uncapped; otherwise clamps at 0 (never negative).
    remaining: int | None
