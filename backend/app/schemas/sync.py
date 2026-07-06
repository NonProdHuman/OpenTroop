"""Envelope schemas for the offline sync pull endpoints (docs/spec/sync-protocol.md).

Every entity's page shares the same keyset-cursor envelope: ``next_since_seq`` /
``next_since_id`` are the ``(sync_seq, id)`` of the last row returned — the client
echoes them back verbatim on the next call. When ``items`` is empty they echo the
request's own cursor.
"""

import uuid

from pydantic import BaseModel

from app.schemas.event import EventParticipantRead, EventRead
from app.schemas.event_type import EventTypeRead
from app.schemas.location import LocationRead
from app.schemas.member import MemberRead
from app.schemas.message import MessageRead, MessageRecipientRead
from app.schemas.relationship import MemberRelationshipRead


class _SyncPageBase(BaseModel):
    next_since_seq: int
    next_since_id: uuid.UUID | None
    has_more: bool


class SyncMembersPage(_SyncPageBase):
    """One page of the members change stream, tombstones included."""

    items: list[MemberRead]


class SyncMemberRelationshipsPage(_SyncPageBase):
    items: list[MemberRelationshipRead]


class SyncEventTypesPage(_SyncPageBase):
    items: list[EventTypeRead]


class SyncLocationsPage(_SyncPageBase):
    items: list[LocationRead]


class SyncEventsPage(_SyncPageBase):
    items: list[EventRead]


class SyncEventParticipantsPage(_SyncPageBase):
    items: list[EventParticipantRead]


class SyncInboxMessagesPage(_SyncPageBase):
    items: list[MessageRead]


class SyncInboxRecipientsPage(_SyncPageBase):
    items: list[MessageRecipientRead]
