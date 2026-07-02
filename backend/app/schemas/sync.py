"""Envelope schemas for the offline sync pull endpoints (docs/spec/sync-protocol.md)."""

import uuid

from pydantic import BaseModel

from app.schemas.member import MemberRead


class SyncMembersPage(BaseModel):
    """One page of the members change stream, tombstones included.

    ``next_since_seq`` / ``next_since_id`` are the ``(sync_seq, id)`` keyset cursor of
    the last row returned — the client echoes them back verbatim on the next call.
    When ``items`` is empty they echo the request's own cursor.
    """

    items: list[MemberRead]
    next_since_seq: int
    next_since_id: uuid.UUID | None
    has_more: bool
