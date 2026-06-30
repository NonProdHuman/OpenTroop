"""Parental permission-slip state — derived, never stored.

The permission slip's status is computed from three inputs: the event type
(`require_permission_slip` + `allow_signups`), the scout's RSVP (`rsvp_status`),
and whether a parent has signed under the *current* tenant language.

Key rules (see ``docs/spec/event-rsvp-permission.md``):

- Only **scouts** need a slip, and only on event types that require one.
- A signed slip is honored only while the scout is ``going`` — declining hides it.
- ``going → declined → going`` **revives** the original signature *without re-signing*,
  as long as the snapshotted language still matches the current tenant message.
- If the troop edits ``Tenant.permission_message`` after signing, the snapshot no
  longer matches → the slip reverts to PENDING and must be re-signed under the new text.
"""

from __future__ import annotations

from app.models.enums import MemberType, PermissionSlipStatus, RsvpStatus
from app.models.event import EventParticipant
from app.models.event_type import EventType
from app.models.member import Member
from app.models.tenant import Tenant

# Placeholder default until the troop sets its own. The real BSA permission language
# will replace this constant; it is intentionally generic for now.
DEFAULT_PERMISSION_MESSAGE = (
    "I give permission for my scout to participate in this event. In the event of an "
    "emergency and if I cannot be reached, I authorize the adult leaders present to "
    "obtain and consent to medical treatment for my scout."
)


def effective_permission_message(tenant: Tenant) -> str:
    """The permission language shown to a parent — the troop's text or the default."""
    return tenant.permission_message or DEFAULT_PERMISSION_MESSAGE


def permission_required(event_type: EventType, member: Member) -> bool:
    """Whether this member needs a parental permission slip for this event type.

    Only scouts, and only when the type both collects RSVPs and requires a slip.
    """
    return (
        event_type.allow_signups
        and event_type.require_permission_slip
        and member.member_type == MemberType.SCOUT
    )


def permission_status(
    participant: EventParticipant,
    event_type: EventType,
    member: Member,
    effective_message: str,
) -> PermissionSlipStatus:
    """Derive the slip status for a participant."""
    if not permission_required(event_type, member):
        return PermissionSlipStatus.NOT_REQUIRED
    if participant.rsvp_status != RsvpStatus.GOING:
        # Required for this type, but the scout isn't going — nothing to collect.
        return PermissionSlipStatus.NOT_REQUIRED
    # Going and required: a signature counts only if it matches the current language.
    if (
        participant.electronic_permission
        and participant.permission_message_snapshot == effective_message
    ):
        return PermissionSlipStatus.GRANTED
    return PermissionSlipStatus.PENDING
