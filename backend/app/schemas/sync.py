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


# Sync stream items are the interactive *Read payloads plus the row's own
# ``sync_seq``: the offline mirror stores it as a NOT NULL column with every
# row (GH-153 §C1), so it is part of the pull contract, not an internal.


class SyncMemberRead(MemberRead):
    sync_seq: int


class SyncMemberRelationshipRead(MemberRelationshipRead):
    sync_seq: int


class SyncEventTypeRead(EventTypeRead):
    sync_seq: int


class SyncLocationRead(LocationRead):
    sync_seq: int


class SyncEventRead(EventRead):
    sync_seq: int


class SyncEventParticipantRead(EventParticipantRead):
    sync_seq: int


class SyncMessageRead(MessageRead):
    sync_seq: int


class SyncMessageRecipientRead(MessageRecipientRead):
    sync_seq: int


class SyncMembersPage(_SyncPageBase):
    """One page of the members change stream, tombstones included."""

    items: list[SyncMemberRead]


class SyncMemberRelationshipsPage(_SyncPageBase):
    items: list[SyncMemberRelationshipRead]


class SyncEventTypesPage(_SyncPageBase):
    items: list[SyncEventTypeRead]


class SyncLocationsPage(_SyncPageBase):
    items: list[SyncLocationRead]


class SyncEventsPage(_SyncPageBase):
    items: list[SyncEventRead]


class SyncEventParticipantsPage(_SyncPageBase):
    items: list[SyncEventParticipantRead]


class SyncInboxMessagesPage(_SyncPageBase):
    items: list[SyncMessageRead]


class SyncInboxRecipientsPage(_SyncPageBase):
    items: list[SyncMessageRecipientRead]
