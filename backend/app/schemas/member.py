import uuid
from datetime import date, datetime

from pydantic import BaseModel, EmailStr

from app.models.enums import (
    AnnouncementEmailMode,
    MemberStatus,
    MemberType,
    SwimClassification,
)
from app.schemas.base import TrackedRead


class MemberBase(BaseModel):
    bsa_id: str | None = None
    first_name: str
    middle_name: str | None = None
    last_name: str
    name_suffix: str | None = None
    nickname: str | None = None
    date_of_birth: date | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = "US"
    member_type: MemberType
    membership_status: MemberStatus = MemberStatus.ACTIVE
    swim_classification: SwimClassification = SwimClassification.NONSWIMMER
    troop_membership_start_date: date | None = None
    troop_membership_end_date: date | None = None
    swim_date: date | None = None
    medical_form_ab_date: date | None = None
    medical_form_c_date: date | None = None
    allergies: str | None = None
    dietary_restrictions: str | None = None
    emergency_contact_1_name: str | None = None
    emergency_contact_1_phone: str | None = None
    emergency_contact_2_name: str | None = None
    emergency_contact_2_phone: str | None = None
    email_opt_out: bool = False
    email_bounced: bool = False
    sms_opt_in: bool = False
    announcement_email_mode: AnnouncementEmailMode = AnnouncementEmailMode.EVERY
    notes: str | None = None
    oa_member: bool = False
    oa_active: bool = False
    oa_election_date: date | None = None
    oa_call_out_date: date | None = None
    oa_ordeal_date: date | None = None
    oa_brotherhood_date: date | None = None
    oa_vigil_date: date | None = None
    oa_vigil_name: str | None = None
    oa_notes: str | None = None


class MemberUpdate(BaseModel):
    bsa_id: str | None = None
    first_name: str | None = None
    middle_name: str | None = None
    last_name: str | None = None
    name_suffix: str | None = None
    nickname: str | None = None
    date_of_birth: date | None = None
    email: EmailStr | None = None
    phone: str | None = None
    address_line1: str | None = None
    address_line2: str | None = None
    city: str | None = None
    state: str | None = None
    postal_code: str | None = None
    country: str | None = None
    member_type: MemberType | None = None
    membership_status: MemberStatus | None = None
    swim_classification: SwimClassification | None = None
    troop_membership_start_date: date | None = None
    troop_membership_end_date: date | None = None
    swim_date: date | None = None
    medical_form_ab_date: date | None = None
    medical_form_c_date: date | None = None
    allergies: str | None = None
    dietary_restrictions: str | None = None
    emergency_contact_1_name: str | None = None
    emergency_contact_1_phone: str | None = None
    emergency_contact_2_name: str | None = None
    emergency_contact_2_phone: str | None = None
    email_opt_out: bool | None = None
    email_bounced: bool | None = None
    sms_opt_in: bool | None = None
    announcement_email_mode: AnnouncementEmailMode | None = None
    notes: str | None = None
    oa_member: bool | None = None
    oa_active: bool | None = None
    oa_election_date: date | None = None
    oa_call_out_date: date | None = None
    oa_ordeal_date: date | None = None
    oa_brotherhood_date: date | None = None
    oa_vigil_date: date | None = None
    oa_vigil_name: str | None = None
    oa_notes: str | None = None


class MemberRead(MemberBase, TrackedRead):
    user_id: uuid.UUID | None = None
    # Override to str so rows with non-RFC-5321 values already in the DB
    # (e.g. "[email]" placeholder from aggressive PII scrubbing) don't cause
    # a 500 on the list endpoint.
    email: str | None = None


class MemberPurgeRequest(BaseModel):
    """Body for POST /members/{id}/purge — the type-to-confirm phrase (GH-222).

    Must match the member's "first_name last_name" (case-insensitive,
    whitespace-normalized). Enforced server-side so no client can offer a
    one-click irreversible delete.
    """

    confirm_name: str


class NotificationPreferencesRead(BaseModel):
    """A member's self-service notification preferences (GH-218).

    ``announcement_email_mode`` is the editable knob; ``email_opt_out`` and
    ``email_bounced`` are surfaced read-only so the member understands why mail
    may not be arriving (opted out globally, or their address bounced).
    """

    announcement_email_mode: AnnouncementEmailMode
    email_opt_out: bool
    email_bounced: bool


class NotificationPreferencesUpdate(BaseModel):
    announcement_email_mode: AnnouncementEmailMode


class MemberInviteRead(BaseModel):
    """Returned by POST /members/{id}/invite — the token the member uses to claim their account."""

    token: str
    expires_at: datetime
    # True if an invite email was sent automatically. False if the member has no
    # usable email address (missing, opted out, or previously bounced) or the
    # send failed — the token/link is still valid and can be shared manually.
    email_sent: bool
