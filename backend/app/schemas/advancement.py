"""Pydantic schemas for the advancement API (GH-92 Phase 2)."""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models.enums import CompletionStatus, MemberStatus, RankCode, RecordedVia
from app.schemas.base import PlatformRead, TrackedRead
from app.schemas.types import UtcDateTime

# ---------------------------------------------------------------------------
# Catalog (read-only reference data)
# ---------------------------------------------------------------------------


class RankRead(PlatformRead):
    code: RankCode
    name: str
    sort_order: int


class RequirementSetRead(PlatformRead):
    rank_id: uuid.UUID
    version: str
    effective_date: date | None


class RequirementRead(PlatformRead):
    requirement_set_id: uuid.UUID
    number: str
    letter: str
    label: str
    parent_id: uuid.UUID | None
    sort_order: int
    text: str
    stable_key: str | None
    metrics: list[dict[str, Any]] | None
    auto_credit: bool


class RequirementSetDetail(RequirementSetRead):
    requirements: list[RequirementRead]


class RankWithSets(RankRead):
    requirement_sets: list[RequirementSetRead]


class MeritBadgeRead(PlatformRead):
    name: str
    eagle_required: bool
    is_discontinued: bool


# ---------------------------------------------------------------------------
# Requirement completions (report → approve workflow)
# ---------------------------------------------------------------------------


def _not_in_future(value: date | None) -> date | None:
    """Completion dates record history — a future sign-off is always a typo (#256 D2)."""
    if value is not None and value > date.today():
        raise ValueError("date_completed cannot be in the future")
    return value


class CompletionCreate(BaseModel):
    requirement_id: uuid.UUID
    # Optional: omitted means "today" (the server stamps it), editable otherwise.
    date_completed: date | None = None
    note: str | None = Field(default=None, max_length=2000)

    _no_future = field_validator("date_completed")(_not_in_future)


class CompletionUpdate(BaseModel):
    """Chair edits. ``status`` transitions need ``advancement:approve``;
    date/note edits need ``advancement:record``."""

    status: CompletionStatus | None = None
    date_completed: date | None = None
    note: str | None = Field(default=None, max_length=2000)

    _no_future = field_validator("date_completed")(_not_in_future)


class CompletionRead(TrackedRead):
    member_id: uuid.UUID
    requirement_id: uuid.UUID
    date_completed: date
    status: CompletionStatus
    reported_by_id: uuid.UUID | None
    approved_by_id: uuid.UUID | None
    approved_at: UtcDateTime | None
    recorded_via: RecordedVia
    note: str | None


# ---------------------------------------------------------------------------
# Merit badge records
# ---------------------------------------------------------------------------


class MemberMeritBadgeCreate(BaseModel):
    merit_badge_id: uuid.UUID
    date_started: date | None = None
    date_completed: date | None = None
    counselor_name: str | None = Field(default=None, max_length=255)


class MemberMeritBadgeUpdate(BaseModel):
    status: CompletionStatus | None = None
    date_started: date | None = None
    date_completed: date | None = None
    counselor_name: str | None = Field(default=None, max_length=255)


class MemberMeritBadgeRead(TrackedRead):
    member_id: uuid.UUID
    merit_badge_id: uuid.UUID
    date_started: date | None
    date_completed: date | None
    counselor_name: str | None
    status: CompletionStatus
    reported_by_id: uuid.UUID | None
    approved_by_id: uuid.UUID | None
    approved_at: UtcDateTime | None


# ---------------------------------------------------------------------------
# Rank progress / elections
# ---------------------------------------------------------------------------


class RankProgressRead(TrackedRead):
    member_id: uuid.UUID
    rank_id: uuid.UUID
    requirement_set_id: uuid.UUID
    completed_date: date | None
    awarded_date: date | None


class RankProgressUpdate(BaseModel):
    """Board-of-review / Court-of-Honor dates (``advancement:approve``)."""

    completed_date: date | None = None
    awarded_date: date | None = None


class ElectionUpdate(BaseModel):
    requirement_set_id: uuid.UUID


class ElectionResult(BaseModel):
    progress: RankProgressRead
    remapped: int
    skipped_existing: int
    unmatched: list[str]


# ---------------------------------------------------------------------------
# Member progress view
# ---------------------------------------------------------------------------


class MetricProgress(BaseModel):
    """One evaluated metric condition — the UI progress meter datum.

    ``value`` is None when the window anchor is unavailable (e.g. a since_rank
    condition before the previous rank's board of review is recorded).
    """

    kind: str
    window: str
    threshold: float
    value: float | None
    met: bool


class RequirementProgress(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    requirement: RequirementRead
    completion: CompletionRead | None
    # Derived completeness: approved leaves; containers when all children complete.
    is_complete: bool
    # Live meters for metric-bearing requirements (GH-92) — always computed fresh.
    metrics_progress: list[MetricProgress] = []


class MemberRankView(BaseModel):
    rank: RankRead
    requirement_set: RequirementSetRead
    progress: RankProgressRead | None
    requirements: list[RequirementProgress]
    # All top-level requirements complete ⇒ ready for board of review. Computed.
    is_complete: bool


class MemberAdvancementRead(BaseModel):
    member_id: uuid.UUID
    ranks: list[MemberRankView]
    merit_badges: list[MemberMeritBadgeRead]


class AdvancementQueueRead(BaseModel):
    """Pending approvals (mode ``scout_reported``)."""

    completions: list[CompletionRead]
    merit_badges: list[MemberMeritBadgeRead]


class AdvancementScoutRead(BaseModel):
    """A scout the caller may view advancement for — the viewer-page picker row.

    Deliberately self-contained (name, patrol, current rank) so parents and
    scouts without ``member:read`` never need the members API to render the
    picker. See GH-191.
    """

    member_id: uuid.UUID
    first_name: str
    last_name: str
    nickname: str | None
    membership_status: MemberStatus
    patrol_name: str | None
    # Current rank = highest sort_order with a recorded board-of-review date;
    # null for scouts with no completed rank yet.
    current_rank_code: RankCode | None
    current_rank_name: str | None
