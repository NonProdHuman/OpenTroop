"""Hard-delete flows (GH-222): member purge, tombstone reaper, tenant export/purge.

Three layers, each with different timing and blast radius:

1. **Member purge** (``purge_member``) — immediate, tenant-scoped. Anonymizes the
   Member row *in place*: every PII-bearing field is nulled, credentials and the
   platform-account link are severed, and the row becomes a soft-deleted sync
   tombstone (``is_deleted=True``, ``purged_at`` stamped). Offline mirrors purge
   the member through the normal tombstone stream. Attendance, advancement, and
   position history are kept — attached to the now-faceless row — so troop
   aggregates stay truthful until the reaper runs.

2. **Tombstone reaper** (``reap_purged_members``) — deferred, cross-tenant. Once a
   purged member's tombstone has been visible for ``tombstone_retention_days``
   (≥180, sync-protocol Decision 5), the skeleton row and every row hanging off it
   are physically deleted and nullable back-references are cleared. Because the
   dependent rows (participants, advancement, …) were never tombstoned, their
   deletion is invisible to incremental sync — so the reaper records a fresh
   ``Tenant.purged_through_seq`` watermark dominating every issued cursor, and
   the pull endpoints answer 410 to any older cursor, forcing a full refetch.
   Reaps are rare (once per departed member, six months later), so the occasional
   tenant-wide refetch is a fair trade for never leaving dangling rows on devices.

3. **Tenant export + purge** (``export_tenant`` / ``purge_tenant``) — the platform
   control plane's offboarding pair. Export streams every tenant-scoped table into
   one JSON bundle and stamps ``Tenant.last_export_at`` — the precondition (and
   accidental-delete recovery path) for ``purge_tenant``, which hard-deletes every
   ``tenant_id`` row plus the Tenant itself in one transaction. Platform ``User``/
   ``Identity`` rows survive: they may span tenants.

None of these functions commit — the caller owns the transaction.
"""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Any, cast

from sqlalchemy import CursorResult, delete, func, select, text, update
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.tenant_context import include_deleted, unscoped
from app.models.advancement import (
    MemberMeritBadge,
    MemberRankProgress,
    MemberRequirementCompletion,
)
from app.models.base import Base
from app.models.event import Event, EventOrganizer, EventParticipant
from app.models.event_type import EventType
from app.models.group import GroupMember
from app.models.location import Location
from app.models.member import Member, MemberRelationship
from app.models.message import Message, MessageRecipient
from app.models.push import PushToken
from app.models.rbac import MemberPositionAssignment
from app.models.tenant import Tenant
from app.models.user import User

logger = logging.getLogger(__name__)

# Member columns anonymized by purge_member. Everything here is either direct PII
# or an external identifier that could re-identify the person (bsa_id, TWH
# provenance). Kept deliberately explicit — a new PII column must be added here
# (test_member_purge has a tripwire that flags unreviewed new Member columns).
MEMBER_PII_NULLED: tuple[str, ...] = (
    "middle_name",
    "nickname",
    "name_suffix",
    "date_of_birth",
    "email",
    "phone",
    "address_line1",
    "address_line2",
    "city",
    "state",
    "postal_code",
    "country",
    "swim_date",
    "medical_form_ab_date",
    "medical_form_c_date",
    "allergies",
    "dietary_restrictions",
    "emergency_contact_1_name",
    "emergency_contact_1_phone",
    "emergency_contact_2_name",
    "emergency_contact_2_phone",
    "notes",
    "oa_vigil_name",
    "oa_notes",
    "bsa_id",
    "source_system",
    "source_id",
    "source_updated_at",
    "user_id",
    "calendar_token_hash",
    "invite_token_jti",
)

# The Syncable, member-owned tables whose rows the reaper hard-deletes; their max
# sync_seq feeds the watermark. Non-syncable member-owned tables are deleted too
# (below) but never appeared in the sync stream, so they don't move the watermark.
_REAPED_BY_MEMBER_ID: tuple[type[Base], ...] = (
    EventParticipant,
    EventOrganizer,
    GroupMember,
    MemberPositionAssignment,
    MemberRankProgress,
    MemberRequirementCompletion,
    MemberMeritBadge,
    MessageRecipient,
    PushToken,
)

# Nullable back-references into members from rows that survive a reap.
_NULLED_ON_REAP: tuple[tuple[type[Base], str], ...] = (
    (MemberPositionAssignment, "assigned_by_id"),
    (GroupMember, "added_by_id"),
    (EventParticipant, "electronic_permission_by_id"),
    (MemberRequirementCompletion, "reported_by_id"),
    (MemberRequirementCompletion, "approved_by_id"),
    (MemberMeritBadge, "reported_by_id"),
    (MemberMeritBadge, "approved_by_id"),
    (Message, "sent_by_id"),
)

# Every Syncable table — the SQLite fallback for drawing a fresh watermark value
# scans their max sync_seq (Postgres just draws nextval from the shared sequence).
_SYNCABLE_MODELS: tuple[type[Base], ...] = (
    Member,
    MemberRelationship,
    EventType,
    Location,
    Event,
    EventParticipant,
    Message,
    MessageRecipient,
)


def purge_member(db: Session, member: Member, *, now: datetime | None = None) -> None:
    """Anonymize *member* in place (GH-222) — the immediate half of hard delete.

    Assumes the caller has already enforced RBAC, confirmation, and the
    last-admin/self guardrails. Runs entirely through the ORM so ``sync_seq``
    bumps and the tombstones re-enter the pull stream. Does not commit.
    """
    now = now or datetime.now(UTC)

    for field in MEMBER_PII_NULLED:
        setattr(member, field, None)
    member.first_name = "Deleted"
    member.last_name = "Member"
    member.email_opt_out = False
    member.email_bounced = False
    member.sms_opt_in = False
    member.is_deleted = True
    member.purged_at = now

    # Family edges and group/patrol membership become tombstones (both Syncable
    # or resolved through members anyway); push registrations are hard-pruned,
    # matching the model's own convention for dead tokens.
    relationships = db.scalars(
        select(MemberRelationship).where(
            (MemberRelationship.from_member_id == member.id)
            | (MemberRelationship.to_member_id == member.id)
        )
    ).all()
    for rel in relationships:
        rel.is_deleted = True

    group_rows = db.scalars(select(GroupMember).where(GroupMember.member_id == member.id)).all()
    for gm in group_rows:
        gm.is_deleted = True

    db.execute(delete(PushToken).where(PushToken.member_id == member.id))

    # Kept rows are scrubbed of free-text the person authored (or that embeds
    # their address): RSVP comments, permission-slip signatures they signed,
    # email-delivery error strings.
    db.execute(
        update(EventParticipant).where(EventParticipant.member_id == member.id).values(comment=None)
    )
    db.execute(
        update(EventParticipant)
        .where(EventParticipant.electronic_permission_by_id == member.id)
        .values(electronic_permission_signature=None)
    )
    db.execute(
        update(MessageRecipient)
        .where(MessageRecipient.member_id == member.id)
        .values(last_error=None)
    )

    logger.info("member.purge tenant=%s member=%s", member.tenant_id, member.id)


def _fresh_watermark(db: Session) -> int:
    """Draw a sync-cursor value strictly greater than any cursor a client holds.

    A reap silently hard-deletes rows that were never tombstoned (participants,
    advancement, …), which incremental sync cannot express — so *every* cursor
    issued before the reap must be pushed through a full refetch. On Postgres a
    ``nextval`` from the shared ``sync_seq`` sequence dominates every value ever
    issued; the SQLite fallback takes the global max across syncable tables + 1
    (duplicates with a future row are fine — the 410 check is strict-less-than).
    The pull endpoints clamp a completed walk's cursor up to the watermark so a
    post-refetch client converges instead of looping on 410.
    """
    if db.get_bind().dialect.name == "postgresql":
        return int(db.scalar(text("SELECT nextval('sync_seq')")))
    high = 0
    for model in _SYNCABLE_MODELS:
        value = db.scalar(select(func.max(model.sync_seq)))  # type: ignore[attr-defined]
        high = max(high, value or 0)
    return high + 1


def reap_purged_members(
    db: Session, *, retention_days: int | None = None, now: datetime | None = None
) -> int:
    """Physically delete members purged at least *retention_days* ago.

    Cross-tenant (run it from the reaper CLI / cron, not a request path). For each
    due member: hard-delete the member-owned rows, null surviving back-references,
    advance the tenant's ``purged_through_seq`` watermark to the tenant's current
    max ``sync_seq``, then delete the Member row. Returns the number of members
    reaped. Does not commit.
    """
    days = retention_days if retention_days is not None else settings.tombstone_retention_days
    if days < 180:  # sync-protocol Decision 5 floor; belt against a caller bypassing Settings
        raise ValueError("tombstone retention below the 180-day sync floor")
    cutoff = (now or datetime.now(UTC)) - timedelta(days=days)

    with unscoped(), include_deleted():
        due = db.scalars(
            select(Member).where(Member.purged_at.is_not(None), Member.purged_at <= cutoff)
        ).all()

        for member in due:
            for model, field in _NULLED_ON_REAP:
                db.execute(
                    update(model).where(getattr(model, field) == member.id).values({field: None})
                )
            for model in _REAPED_BY_MEMBER_ID:
                db.execute(delete(model).where(model.member_id == member.id))  # type: ignore[attr-defined]
            db.execute(
                delete(MemberRelationship).where(
                    (MemberRelationship.from_member_id == member.id)
                    | (MemberRelationship.to_member_id == member.id)
                )
            )

            tenant = db.get(Tenant, member.tenant_id)
            if tenant is not None:
                watermark = _fresh_watermark(db)
                tenant.purged_through_seq = max(tenant.purged_through_seq or 0, watermark)

            db.execute(delete(Member).where(Member.id == member.id))
            logger.info("member.reap tenant=%s member=%s", member.tenant_id, member.id)

    return len(due)


def _jsonable(value: Any) -> Any:
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, Enum):
        return value.value
    return value


def _tenant_scoped_tables() -> list[Any]:
    """Every mapped table carrying a ``tenant_id`` column, in FK-dependency order."""
    return [t for t in Base.metadata.sorted_tables if "tenant_id" in t.c]


def export_tenant(db: Session, tenant: Tenant, *, now: datetime | None = None) -> dict[str, Any]:
    """Build the full-tenant JSON bundle and stamp ``last_export_at``.

    Includes every tenant-scoped table (soft-deleted rows too — they are real
    data), the tenant row itself, and a minimal directory of the platform users
    linked from the roster so contactability survives offboarding. This is the
    delete gate and the recovery path; #121 owns any richer/streaming evolution.
    """
    now = now or datetime.now(UTC)
    tables: dict[str, list[dict[str, Any]]] = {}
    for table in _tenant_scoped_tables():
        rows = db.execute(select(table).where(table.c.tenant_id == tenant.id)).mappings().all()
        tables[table.name] = [{k: _jsonable(v) for k, v in row.items()} for row in rows]

    user_ids = {
        row["user_id"] for row in tables.get("members", ()) if row.get("user_id") is not None
    }
    users = []
    if user_ids:
        for user in db.scalars(
            select(User).where(User.id.in_([uuid.UUID(u) for u in user_ids]))
        ).all():
            users.append(
                {"id": str(user.id), "email": user.email, "display_name": user.display_name}
            )

    tenant.last_export_at = now
    return {
        "format": "opentroop-tenant-export",
        "version": 1,
        "exported_at": now.isoformat(),
        "tenant": {
            "id": str(tenant.id),
            "name": tenant.name,
            "slug": tenant.slug,
            "created_at": tenant.created_at.isoformat(),
            "suspended_at": tenant.suspended_at.isoformat() if tenant.suspended_at else None,
        },
        "users": users,
        "tables": tables,
    }


def purge_tenant(db: Session, tenant: Tenant) -> dict[str, int]:
    """Hard-delete every tenant-scoped row and the Tenant itself (GH-222).

    Walks the mapped tables in reverse FK-dependency order so children go first.
    Platform ``User``/``Identity`` rows are untouched. Returns per-table deleted
    row counts (for the audit line). Does not commit.
    """
    counts: dict[str, int] = {}
    for table in reversed(_tenant_scoped_tables()):
        result = cast(
            "CursorResult[Any]", db.execute(table.delete().where(table.c.tenant_id == tenant.id))
        )
        if result.rowcount:
            counts[table.name] = result.rowcount
    db.execute(delete(Tenant).where(Tenant.id == tenant.id))
    return counts
