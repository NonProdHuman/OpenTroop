import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel

from app.models.enums import PermissionSlipStatus, RsvpStatus
from app.schemas.base import TrackedRead
from app.schemas.event_type import EventTypeRead
from app.schemas.location import LocationRead
from app.schemas.types import UtcDateTime


class EventBase(BaseModel):
    name: str
    event_type_id: uuid.UUID
    location_id: uuid.UUID | None = None
    location_notes: str | None = None
    departure_location: str | None = None
    return_location: str | None = None
    scheduled_start: UtcDateTime
    scheduled_end: UtcDateTime
    all_day: bool = False
    signup_start: date | None = None
    signup_deadline: date | None = None
    signup_limit_scouts: int | None = None
    signup_limit_adults: int | None = None
    cost_youth: Decimal | None = None
    cost_adult: Decimal | None = None
    video_conference_url: str | None = None
    description: str | None = None
    agenda: str | None = None
    tour_permit_submitted: bool | None = None
    linked_event_id: uuid.UUID | None = None
    community_service_hours: Decimal | None = None
    conservation_hours: Decimal | None = None
    hiking_miles: Decimal | None = None
    backpacking_miles: Decimal | None = None
    paddling_miles: Decimal | None = None
    cycling_miles: Decimal | None = None
    water_hours: Decimal | None = None
    camping_nights: int | None = None


class EventUpdate(BaseModel):
    name: str | None = None
    event_type_id: uuid.UUID | None = None
    location_id: uuid.UUID | None = None
    location_notes: str | None = None
    departure_location: str | None = None
    return_location: str | None = None
    scheduled_start: UtcDateTime | None = None
    scheduled_end: UtcDateTime | None = None
    all_day: bool | None = None
    signup_start: date | None = None
    signup_deadline: date | None = None
    signup_limit_scouts: int | None = None
    signup_limit_adults: int | None = None
    cost_youth: Decimal | None = None
    cost_adult: Decimal | None = None
    video_conference_url: str | None = None
    description: str | None = None
    agenda: str | None = None
    tour_permit_submitted: bool | None = None
    attendance_taken: bool | None = None
    linked_event_id: uuid.UUID | None = None
    community_service_hours: Decimal | None = None
    conservation_hours: Decimal | None = None
    hiking_miles: Decimal | None = None
    backpacking_miles: Decimal | None = None
    paddling_miles: Decimal | None = None
    cycling_miles: Decimal | None = None
    water_hours: Decimal | None = None
    camping_nights: int | None = None


class EventRead(EventBase, TrackedRead):
    attendance_taken: bool
    cancelled_at: UtcDateTime | None = None
    event_type: EventTypeRead
    location: LocationRead | None = None


class EventOrganizerBase(BaseModel):
    member_id: uuid.UUID


class EventOrganizerRead(EventOrganizerBase, TrackedRead):
    event_id: uuid.UUID


class EventParticipantBase(BaseModel):
    member_id: uuid.UUID
    signed_up: bool = True
    rsvp_status: RsvpStatus = RsvpStatus.NO_RESPONSE
    guest_count: int = 0
    driver: bool = False
    drives_to: bool = False
    drives_from: bool = False
    seat_count: int | None = None
    comment: str | None = None
    signed_up_at: UtcDateTime | None = None
    hiking_miles_override: Decimal | None = None
    backpacking_miles_override: Decimal | None = None
    paddling_miles_override: Decimal | None = None
    cycling_miles_override: Decimal | None = None
    community_service_hours_override: Decimal | None = None
    conservation_hours_override: Decimal | None = None
    water_hours_override: Decimal | None = None
    camping_nights_override: int | None = None
    # Paper-slip tracking flag (manager-editable). The *electronic* parental permission
    # is granted only via POST .../permission and is read-only here.
    permission_slip_submitted: bool = False


class EventParticipantUpdate(BaseModel):
    signed_up: bool | None = None
    rsvp_status: RsvpStatus | None = None
    attended: bool | None = None
    guest_count: int | None = None
    driver: bool | None = None
    drives_to: bool | None = None
    drives_from: bool | None = None
    seat_count: int | None = None
    comment: str | None = None
    hiking_miles_override: Decimal | None = None
    backpacking_miles_override: Decimal | None = None
    paddling_miles_override: Decimal | None = None
    cycling_miles_override: Decimal | None = None
    community_service_hours_override: Decimal | None = None
    conservation_hours_override: Decimal | None = None
    water_hours_override: Decimal | None = None
    camping_nights_override: int | None = None
    permission_slip_submitted: bool | None = None


class EventParticipantPermission(BaseModel):
    """Body for POST .../permission — a parent/guardian signing a scout's slip."""

    signature: str


class EventParticipantRead(EventParticipantBase, TrackedRead):
    event_id: uuid.UUID
    attended: bool | None = None
    # Electronic parental permission — read-only; set via the permission endpoint.
    electronic_permission: bool = False
    electronic_permission_at: UtcDateTime | None = None
    electronic_permission_by_id: uuid.UUID | None = None
    electronic_permission_signature: str | None = None
    permission_message_snapshot: str | None = None
    # Derived per-request (see app.core.permission_slip). Defaults to NOT_REQUIRED if
    # the router did not attach it (e.g. unknown event/member context).
    permission_status: PermissionSlipStatus = PermissionSlipStatus.NOT_REQUIRED


class EventParticipantCounts(BaseModel):
    """Headcount summary for an event (see docs/spec/event-rsvp-permission.md).

    scouts/adults count members with rsvp_status=going; drivers counts any driver=true
    regardless of attending (an attending adult driver appears in both adults and
    drivers); guests sums guest_count.
    """

    scouts: int
    adults: int
    drivers: int
    guests: int


class EventAudienceCreate(BaseModel):
    group_id: uuid.UUID


class EventAudienceRead(TrackedRead):
    event_id: uuid.UUID
    group_id: uuid.UUID


class EventNotifyResult(BaseModel):
    """How many notification emails a trigger endpoint actually sent."""

    emails_sent: int
