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

# Standard BSA activity consent/release language. Troops may override via
# Tenant.permission_message; this is the default shown until they do.
DEFAULT_PERMISSION_MESSAGE = (
    "I understand that participation in Scouting activities involves the risk of personal "
    "injury, including death, due to the physical, mental, and emotional challenges in the "
    "activities offered. Information about those activities may be obtained from the venue, "
    "activity coordinators, or local council. I also understand that participation in these "
    "activities is entirely voluntary and requires participants to follow instructions and "
    "abide by all applicable rules and the standards of conduct.\n\n"
    "In case of an emergency involving my child, I understand that efforts will be made to "
    "contact me. In the event I cannot be reached, permission is hereby given to the medical "
    "provider to secure proper treatment, including hospitalization, anesthesia, surgery, or "
    "injections of medication for my child. Medical providers are authorized to disclose "
    "protected health information to the adult in charge and/or any physician or health care "
    "provider involved in providing medical care to the participant. Protected Health "
    "Information/Confidential Health Information (PHI/CHI) under the Standards for Privacy of "
    "Individually Identifiable Health Information, 45 C.F.R. §§160.103, 164.501, et "
    "seq., as amended from time to time, includes examination findings, test results, and "
    "treatment provided for purposes of medical evaluation of the participant, follow-up and "
    "communication with the participant’s parents or guardian, and/or determination of "
    "the participant’s ability to continue in the program activities.\n\n"
    "With appreciation of the dangers and risks associated with programs and activities "
    "including preparations for and transportation to and from the activity, on my own behalf "
    "and/or on behalf of my child, I hereby fully and completely release and waive any and all "
    "claims for personal injury, death, or loss that may arise against the Boy Scouts of "
    "America, the local council, the activity coordinators, and all employees, volunteers, "
    "related parties, or other organizations associated with any program or activity.\n\n"
    "NOTE: The Boy Scouts of America and local councils cannot continually monitor compliance "
    "of program participants or any limitations imposed upon them by parents or medical "
    "providers. List any restrictions imposed on a child participant in connection with "
    "programs or activities below and counsel your child to comply with those restrictions."
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
