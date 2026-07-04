"""Advancement catalog — platform-global BSA reference data (Pillar 4, GH-92).

Rank requirements are BSA facts, identical for every troop, so the catalog lives
on ``PlatformBase`` (no ``tenant_id``): read-only to tenants, exempt from RLS like
the other platform tables, and seeded from curated data files by
``uv run seed-advancement`` (see ``app/core/advancement_catalog.py``).

Versioning model (the load-bearing decision from GH-92):

- A :class:`RequirementSet` is **one complete copy** of a rank's requirements for
  one BSA version year — no delta/patch modeling. "What does scout X need" is a
  single-set query; renumbering across years can't corrupt anything.
- A scout's per-rank *version election* (Phase 2, ``MemberRankProgress``) points at
  exactly one set. :attr:`Requirement.stable_key` is the curated cross-version
  identity that lets completions remap when a scout switches sets.

Tenant-scoped tracking tables (``MemberRankProgress`` et al.) arrive in Phase 2 —
this module is deliberately catalog-only.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import PlatformBase, SourceTracked, TrackedBase
from app.models.enums import CompletionStatus, RankCode, RecordedVia
from app.models.types import JsonObjectList


class Rank(PlatformBase):
    """One of the seven Scouts BSA ranks. Global reference data."""

    __tablename__ = "ranks"

    code: Mapped[RankCode] = mapped_column(
        SAEnum(RankCode, values_callable=lambda x: [e.value for e in x]),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Earn-in-sequence ordering (Scout=1 … Eagle=7).
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    requirement_sets: Mapped[list[RequirementSet]] = relationship(
        "RequirementSet", back_populates="rank"
    )


class RequirementSet(PlatformBase):
    """A rank's complete requirement list for one BSA version year.

    Each set is a full copy — sharing/deltas are deliberately avoided so version
    switches and renumbering stay mechanically simple (GH-92).
    """

    __tablename__ = "requirement_sets"
    __table_args__ = (
        UniqueConstraint("rank_id", "version", name="uq_requirement_sets_rank_version"),
    )

    rank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ranks.id"), nullable=False, index=True)
    # BSA version year, e.g. "2025". String — BSA occasionally issues mid-year errata.
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    rank: Mapped[Rank] = relationship("Rank", back_populates="requirement_sets")
    requirements: Mapped[list[Requirement]] = relationship(
        "Requirement", back_populates="requirement_set"
    )


class Requirement(PlatformBase):
    """One requirement line within a set — numbered item or lettered sub-item.

    ``letter`` is ``""`` (never NULL) for numbered items so the uniqueness
    constraint is airtight on Postgres, where NULLs never collide. A numbered
    item that has lettered children is a *container* ("Do the following:") whose
    completion is derived from its children — only leaves get completion rows.
    """

    __tablename__ = "requirements"
    __table_args__ = (
        UniqueConstraint(
            "requirement_set_id", "number", "letter", name="uq_requirements_set_number_letter"
        ),
    )

    requirement_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirement_sets.id"), nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(8), nullable=False)
    letter: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    # Container linkage: a lettered item points at its numbered parent within the
    # same set. Assigned by the seed loader; NULL for top-level numbered items.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requirements.id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Full official requirement text, stored verbatim (GH-92 decision 4).
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Curated cross-version identity: the same slug on two sets' requirements means
    # "substantively the same requirement" even if BSA renumbered it — the remap key
    # for version switches. Best-effort curation; NULL when no counterpart exists.
    stable_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    # Metric conditions (JSON list, AND-ed): {"kind", "threshold", "window"} — see
    # MetricKind / MetricWindow. NULL = plain sign-off item with no progress meter.
    metrics: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonObjectList, nullable=True)
    # True only when the official condition is FULLY computable from the metrics —
    # the auto-credit engine (Phase 3) records completions for these; metric-bearing
    # requirements with auto_credit=False render as progress meters needing sign-off.
    auto_credit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    requirement_set: Mapped[RequirementSet] = relationship(
        "RequirementSet", back_populates="requirements"
    )
    parent: Mapped[Requirement | None] = relationship("Requirement", remote_side="Requirement.id")

    @property
    def label(self) -> str:
        """Display label, e.g. ``"1a"`` or ``"7"``."""
        return f"{self.number}{self.letter}"


class MeritBadge(PlatformBase):
    """A merit badge in the global catalog. Completions only in Phase 1/2 (GH-92).

    ``eagle_required`` drives the ``merit_badge_count_eagle_required`` metric.
    Discontinued badges stay in the catalog (historical completions reference
    them) with ``is_discontinued=True``.
    """

    __tablename__ = "merit_badges"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    eagle_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_discontinued: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class MemberRankProgress(SourceTracked, TrackedBase):
    """A member's progress on one rank — and their requirement-version election.

    One row per (member, rank), created lazily on first completion (or explicit
    start / election change). ``requirement_set_id`` is the **version election**:
    the set of requirements this scout is finishing the rank under (defaults to
    the latest set effective at creation; switchable by ``advancement:approve``,
    which remaps completions via ``stable_key`` — see
    ``app.core.advancement.switch_election``).

    ``completed_date`` is the board-of-review date — the official rank date and
    the tenure anchor for the next rank's ``since_rank`` metrics.
    ``awarded_date`` is the Court of Honor presentation. "All leaf requirements
    complete" is computed, never stored.
    """

    __tablename__ = "member_rank_progress"
    __table_args__ = (
        Index(
            "uix_member_rank_progress_member_rank",
            "tenant_id",
            "member_id",
            "rank_id",
            unique=True,
            postgresql_where=text("NOT is_deleted"),
            sqlite_where=text("is_deleted = 0"),
        ),
        Index("ix_member_rank_progress_tenant_member", "tenant_id", "member_id"),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False, index=True
    )
    rank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ranks.id"), nullable=False)
    requirement_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirement_sets.id"), nullable=False
    )
    completed_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    awarded_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    synced_to_scoutbook_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    rank: Mapped[Rank] = relationship("Rank")
    requirement_set: Mapped[RequirementSet] = relationship("RequirementSet")


class MemberRequirementCompletion(SourceTracked, TrackedBase):
    """One leaf requirement completed (or reported) by one member.

    Only **leaf** requirements get rows — container completion is derived from
    children. Soft delete is **revocation**: the auto-credit engine treats any
    existing row, deleted included, as "do not re-create", so a revoked
    auto-credit stays revoked.
    """

    __tablename__ = "member_requirement_completions"
    __table_args__ = (
        Index(
            "uix_member_req_completions_member_req",
            "tenant_id",
            "member_id",
            "requirement_id",
            unique=True,
            postgresql_where=text("NOT is_deleted"),
            sqlite_where=text("is_deleted = 0"),
        ),
        Index("ix_member_req_completions_tenant_member", "tenant_id", "member_id"),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False, index=True
    )
    requirement_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirements.id"), nullable=False, index=True
    )
    date_completed: Mapped[date] = mapped_column(Date, nullable=False)
    status: Mapped[CompletionStatus] = mapped_column(
        SAEnum(CompletionStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=CompletionStatus.REPORTED,
    )
    reported_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    recorded_via: Mapped[RecordedVia] = mapped_column(
        SAEnum(RecordedVia, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=RecordedVia.MANUAL,
    )
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    synced_to_scoutbook_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    requirement: Mapped[Requirement] = relationship("Requirement")


class MemberMeritBadge(SourceTracked, TrackedBase):
    """A member's merit badge record — completions (and in-progress partials).

    Phase 1/2 tracks the badge as a whole; per-requirement merit badge tracking
    is deferred (the counselor owns it). A row with a null ``date_completed`` is
    a partial in progress. Same report → approve workflow as requirement
    completions; soft delete is revocation.
    """

    __tablename__ = "member_merit_badges"
    __table_args__ = (
        Index(
            "uix_member_merit_badges_member_badge",
            "tenant_id",
            "member_id",
            "merit_badge_id",
            unique=True,
            postgresql_where=text("NOT is_deleted"),
            sqlite_where=text("is_deleted = 0"),
        ),
        Index("ix_member_merit_badges_tenant_member", "tenant_id", "member_id"),
    )

    member_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("members.id"), nullable=False, index=True
    )
    merit_badge_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("merit_badges.id"), nullable=False)
    date_started: Mapped[date | None] = mapped_column(Date, nullable=True)
    date_completed: Mapped[date | None] = mapped_column(Date, nullable=True)
    counselor_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    status: Mapped[CompletionStatus] = mapped_column(
        SAEnum(CompletionStatus, values_callable=lambda x: [e.value for e in x]),
        nullable=False,
        default=CompletionStatus.REPORTED,
    )
    reported_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )
    approved_by_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("members.id"), nullable=True
    )
    approved_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    synced_to_scoutbook_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    merit_badge: Mapped[MeritBadge] = relationship("MeritBadge")
