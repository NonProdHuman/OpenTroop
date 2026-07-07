"""Advancement domain logic (GH-92): version elections, remap, progress derivation.

Phase 2 scope — the workflow around the catalog:

- **Election defaulting**: a member's ``MemberRankProgress`` row is created lazily
  on first completion (or explicit election), pointing at the latest requirement
  set effective at creation time.
- **Version switch + remap** (:func:`switch_election`): completions keep pointing
  at their original set's rows (history is never rewritten); completions whose
  requirement ``stable_key`` exists in the new set are copied over as new rows
  (same dates/approver, ``recorded_via=remap``); unmatched ones are surfaced for
  manual re-entry.
- **Leaf/container derivation**: only leaf requirements carry completion rows;
  a container ("Do the following:") is complete when all its children are.

Phase 3 adds ``compute_member_metrics`` and the auto-credit engine here.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenant_context import include_deleted
from app.models.advancement import (
    MemberRankProgress,
    MemberRequirementCompletion,
    Rank,
    Requirement,
    RequirementSet,
)
from app.models.enums import CompletionStatus, MetricKind


def active_requirement_sets(rank_id: uuid.UUID, session: Session) -> list[RequirementSet]:
    """Non-deleted requirement sets for a rank, newest election candidate first."""
    sets = list(
        session.scalars(
            select(RequirementSet).where(
                RequirementSet.rank_id == rank_id, RequirementSet.is_deleted.is_(False)
            )
        )
    )
    sets.sort(key=lambda s: (s.effective_date or date.min, s.version), reverse=True)
    return sets


def latest_requirement_set(rank_id: uuid.UUID, session: Session) -> RequirementSet | None:
    sets = active_requirement_sets(rank_id, session)
    return sets[0] if sets else None


def set_requirements(requirement_set_id: uuid.UUID, session: Session) -> list[Requirement]:
    """Non-deleted requirements of a set in display order."""
    return list(
        session.scalars(
            select(Requirement)
            .where(
                Requirement.requirement_set_id == requirement_set_id,
                Requirement.is_deleted.is_(False),
            )
            .order_by(Requirement.sort_order)
        )
    )


def leaf_requirement_ids(requirement_set_id: uuid.UUID, session: Session) -> frozenset[uuid.UUID]:
    """Requirements that carry completion rows — everything that isn't a container."""
    requirements = set_requirements(requirement_set_id, session)
    parent_ids = {r.parent_id for r in requirements if r.parent_id is not None}
    return frozenset(r.id for r in requirements if r.id not in parent_ids)


def get_progress(
    member_id: uuid.UUID, rank_id: uuid.UUID, session: Session
) -> MemberRankProgress | None:
    return session.scalar(
        select(MemberRankProgress).where(
            MemberRankProgress.member_id == member_id,
            MemberRankProgress.rank_id == rank_id,
        )
    )


def get_or_create_progress(
    member_id: uuid.UUID, rank_id: uuid.UUID, session: Session
) -> MemberRankProgress:
    """Fetch the member's progress row for a rank, creating it lazily.

    The election defaults to the **latest** set effective now (GH-92); callers
    recording a completion against an older set should pass through
    :func:`switch_election` semantics instead of bypassing this default.
    """
    progress = get_progress(member_id, rank_id, session)
    if progress is not None:
        return progress
    latest = latest_requirement_set(rank_id, session)
    if latest is None:
        raise ValueError("No requirement set exists for this rank — seed the catalog first")
    progress = MemberRankProgress(
        member_id=member_id, rank_id=rank_id, requirement_set_id=latest.id
    )
    session.add(progress)
    session.flush()
    return progress


def member_completions(
    member_id: uuid.UUID,
    session: Session,
    *,
    requirement_ids: frozenset[uuid.UUID] | None = None,
) -> list[MemberRequirementCompletion]:
    """The member's non-deleted completions, optionally restricted to a set's requirements."""
    stmt = select(MemberRequirementCompletion).where(
        MemberRequirementCompletion.member_id == member_id
    )
    if requirement_ids is not None:
        stmt = stmt.where(MemberRequirementCompletion.requirement_id.in_(requirement_ids))
    return list(session.scalars(stmt))


@dataclass
class RemapResult:
    """Outcome of a version-election switch."""

    remapped: int = 0
    skipped_existing: int = 0
    unmatched: list[str] = field(default_factory=list)  # labels needing manual re-entry


def switch_election(
    progress: MemberRankProgress,
    new_set: RequirementSet,
    session: Session,
) -> RemapResult:
    """Move a member's rank election to *new_set*, remapping completions by stable_key.

    Original completion rows are never rewritten or deleted — they remain as
    history against the old set. For each completion whose requirement carries a
    ``stable_key`` present in the new set, a copy is created against the new
    set's requirement (same dates/status/approver, ``recorded_via=remap``) unless
    any row — including a revoked one — already exists there. Completions with
    no counterpart are reported back for manual re-entry.
    """
    from app.models.enums import RecordedVia

    result = RemapResult()
    if new_set.id == progress.requirement_set_id:
        return result

    old_requirements = {r.id: r for r in set_requirements(progress.requirement_set_id, session)}
    new_by_stable_key = {
        r.stable_key: r for r in set_requirements(new_set.id, session) if r.stable_key
    }

    completions = member_completions(
        progress.member_id, session, requirement_ids=frozenset(old_requirements)
    )
    # "Do not re-create" honors revoked rows too: lift the soft-delete filter for
    # this one lookup so a revoked completion on the new set blocks the copy.
    new_req_ids = frozenset(r.id for r in new_by_stable_key.values())
    with include_deleted():
        existing_new = {
            c.requirement_id
            for c in session.scalars(
                select(MemberRequirementCompletion).where(
                    MemberRequirementCompletion.member_id == progress.member_id,
                    MemberRequirementCompletion.requirement_id.in_(new_req_ids),
                )
            )
        }

    for completion in completions:
        old_req = old_requirements[completion.requirement_id]
        target = new_by_stable_key.get(old_req.stable_key) if old_req.stable_key else None
        if target is None:
            result.unmatched.append(old_req.label)
            continue
        if target.id in existing_new:
            result.skipped_existing += 1
            continue
        session.add(
            MemberRequirementCompletion(
                member_id=progress.member_id,
                requirement_id=target.id,
                date_completed=completion.date_completed,
                status=completion.status,
                reported_by_id=completion.reported_by_id,
                approved_by_id=completion.approved_by_id,
                approved_at=completion.approved_at,
                recorded_via=RecordedVia.REMAP,
                note=completion.note,
            )
        )
        existing_new = existing_new | {target.id}
        result.remapped += 1

    progress.requirement_set_id = new_set.id
    session.flush()
    return result


def derive_completion_map(
    requirements: list[Requirement],
    completions: list[MemberRequirementCompletion],
) -> dict[uuid.UUID, bool]:
    """Per-requirement completeness: approved leaves, containers from their children."""
    approved = {c.requirement_id for c in completions if c.status.value == "approved"}
    children: dict[uuid.UUID, list[Requirement]] = {}
    for req in requirements:
        if req.parent_id is not None:
            children.setdefault(req.parent_id, []).append(req)

    complete: dict[uuid.UUID, bool] = {}
    for req in requirements:
        kids = children.get(req.id)
        if kids:
            complete[req.id] = all(k.id in approved for k in kids)
        else:
            complete[req.id] = req.id in approved
    return complete


def rank_is_complete(
    requirements: list[Requirement],
    completion_map: dict[uuid.UUID, bool],
) -> bool:
    """All top-level requirements complete ⇒ ready for board of review (computed, never stored)."""
    top_level = [r for r in requirements if r.parent_id is None]
    return bool(top_level) and all(completion_map.get(r.id, False) for r in top_level)


def derive_earned_date(progress: MemberRankProgress, session: Session) -> bool:
    """Derive the rank's earned (board-of-review) date from its completions (#256 D3).

    The BoR is an ordinary sign-off leaf in the catalog (``…-bor`` stable keys),
    so "earned" falls out of the workflow: once every top-level requirement is
    complete, ``completed_date`` = the **latest** approved leaf date — in
    practice the BoR date. Sets/updates only, never auto-clears: imported and
    pre-derivation ranks legitimately carry an earned date without full leaf
    rows, and un-earning stays an explicit chair action. Returns whether the
    date changed (callers re-run auto-credit on change — the earned date is the
    next rank's tenure anchor).
    """
    requirements = set_requirements(progress.requirement_set_id, session)
    leaf_ids = leaf_requirement_ids(progress.requirement_set_id, session)
    completions = member_completions(progress.member_id, session, requirement_ids=leaf_ids)
    if not rank_is_complete(requirements, derive_completion_map(requirements, completions)):
        return False
    earned = max(c.date_completed for c in completions if c.status == CompletionStatus.APPROVED)
    if progress.completed_date == earned:
        return False
    progress.completed_date = earned
    return True


def ordered_ranks(session: Session) -> list[Rank]:
    return list(
        session.scalars(select(Rank).where(Rank.is_deleted.is_(False)).order_by(Rank.sort_order))
    )


# ---------------------------------------------------------------------------
# Phase 3 — metric computation + auto-credit engine (GH-92)
# ---------------------------------------------------------------------------

_AVG_DAYS_PER_MONTH = 30.4375  # calendar-average month; tenure/POR are ~month-grained

# Event-derived metric kinds (everything computed per attended participation).
_EVENT_KINDS = frozenset(
    {
        MetricKind.CAMPING_NIGHTS,
        MetricKind.SERVICE_HOURS,
        MetricKind.CONSERVATION_HOURS,
        MetricKind.HIKING_MILES,
        MetricKind.ACTIVITY_COUNT,
    }
)


def _months_between(start: date, end: date) -> float:
    return max(0.0, (end - start).days / _AVG_DAYS_PER_MONTH)


def _merged_interval_months(intervals: list[tuple[date, date]], cutoff: date, today: date) -> float:
    """Months covered by the union of intervals, clipped to [cutoff, today].

    Concurrent positions of responsibility must not double-count time — "serve
    in one or more positions for N months" measures elapsed service, not a sum
    over positions.
    """
    clipped = sorted(
        (max(s, cutoff), min(e, today)) for s, e in intervals if max(s, cutoff) <= min(e, today)
    )
    total_days = 0
    current_start: date | None = None
    current_end: date | None = None
    for start, end in clipped:
        if current_end is None or start > current_end:
            if current_start is not None and current_end is not None:
                total_days += (current_end - current_start).days
            current_start, current_end = start, end
        elif end > current_end:
            current_end = end
    if current_start is not None and current_end is not None:
        total_days += (current_end - current_start).days
    return total_days / _AVG_DAYS_PER_MONTH


@dataclass
class MemberMetrics:
    """A member's countable advancement inputs, ready for windowed evaluation.

    ``events`` holds one entry per *attended* participation: the event date and
    the effective per-kind values (participant override ?? event value — the
    same rule the event UI applies). Badge counts include only approved,
    completed records. ``por_intervals`` are the member's terms in
    ``counts_for_por`` positions (open terms run to *today*).
    """

    today: date
    events: list[tuple[date, dict[MetricKind, float]]] = field(default_factory=list)
    badge_count: int = 0
    badge_count_eagle_required: int = 0
    por_intervals: list[tuple[date, date]] = field(default_factory=list)

    def value(self, kind: MetricKind, anchor: date | None) -> float:
        """Accumulated value for *kind* since *anchor* (None ⇒ all history)."""
        cutoff = anchor or date.min
        if kind in _EVENT_KINDS:
            return sum(values.get(kind, 0.0) for d, values in self.events if d >= cutoff)
        if kind == MetricKind.MERIT_BADGE_COUNT:
            return float(self.badge_count)
        if kind == MetricKind.MERIT_BADGE_COUNT_EAGLE_REQUIRED:
            return float(self.badge_count_eagle_required)
        if kind == MetricKind.TENURE_MONTHS:
            return _months_between(anchor, self.today) if anchor else 0.0
        if kind == MetricKind.POR_MONTHS:
            return _merged_interval_months(self.por_intervals, cutoff, self.today)
        return 0.0  # pragma: no cover — enum is exhaustive today


def _effective(override: float | Decimal | int | None, base: float | Decimal | int | None) -> float:
    value = override if override is not None else base
    return float(value) if value is not None else 0.0


def compute_member_metrics(
    member_id: uuid.UUID, session: Session, *, today: date | None = None
) -> MemberMetrics:
    """Aggregate a member's advancement inputs from attendance, badges, and terms."""
    from app.models.advancement import MemberMeritBadge, MeritBadge
    from app.models.enums import CompletionStatus
    from app.models.event import Event, EventParticipant
    from app.models.rbac import MemberPositionAssignment, Position

    metrics = MemberMetrics(today=today or date.today())

    rows = session.execute(
        select(EventParticipant, Event)
        .join(Event, EventParticipant.event_id == Event.id)
        .where(
            EventParticipant.member_id == member_id,
            EventParticipant.attended.is_(True),
        )
    ).all()
    for participant, event in rows:
        event_date = event.scheduled_start.date()
        values: dict[MetricKind, float] = {
            MetricKind.SERVICE_HOURS: _effective(
                participant.community_service_hours_override, event.community_service_hours
            ),
            MetricKind.CONSERVATION_HOURS: _effective(
                participant.conservation_hours_override, event.conservation_hours
            ),
            MetricKind.HIKING_MILES: _effective(
                participant.hiking_miles_override, event.hiking_miles
            ),
            MetricKind.CAMPING_NIGHTS: _effective(
                participant.camping_nights_override, event.camping_nights
            ),
            MetricKind.ACTIVITY_COUNT: (
                1.0 if event.event_type is not None and event.event_type.counts_as_activity else 0.0
            ),
        }
        metrics.events.append((event_date, values))

    badge_rows = session.execute(
        select(MemberMeritBadge, MeritBadge)
        .join(MeritBadge, MemberMeritBadge.merit_badge_id == MeritBadge.id)
        .where(
            MemberMeritBadge.member_id == member_id,
            MemberMeritBadge.status == CompletionStatus.APPROVED,
            MemberMeritBadge.date_completed.is_not(None),
        )
    ).all()
    metrics.badge_count = len(badge_rows)
    metrics.badge_count_eagle_required = sum(1 for _, badge in badge_rows if badge.eagle_required)

    term_rows = session.execute(
        select(MemberPositionAssignment, Position)
        .join(Position, MemberPositionAssignment.position_id == Position.id)
        .where(
            MemberPositionAssignment.member_id == member_id,
            Position.counts_for_por.is_(True),
        )
    ).all()
    for term, _position in term_rows:
        start = term.start_date
        if start is None:
            continue  # an undated term can't accrue measurable months
        end = term.end_date or metrics.today
        metrics.por_intervals.append((start, end))

    return metrics


def _joining_anchor(member_id: uuid.UUID, session: Session, metrics: MemberMetrics) -> date | None:
    """SINCE_JOINING anchor: membership start date, falling back to earliest attendance.

    With neither recorded, ``None`` — callers treat that as "count everything",
    since a scout's tracked history effectively starts at joining anyway.
    """
    from app.models.member import Member

    member = session.get(Member, member_id)
    if member is not None and member.troop_membership_start_date is not None:
        return member.troop_membership_start_date
    if metrics.events:
        return min(d for d, _ in metrics.events)
    return None


def _previous_rank_anchor(
    member_id: uuid.UUID, rank: Rank, session: Session
) -> tuple[date | None, bool]:
    """SINCE_RANK anchor: the previous rank's board-of-review date.

    Returns ``(anchor, available)`` — ``available=False`` when the previous rank
    has no recorded completion, in which case a SINCE_RANK condition cannot be
    satisfied (strict: "while a First Class Scout" requires being one).
    """
    ranks = ordered_ranks(session)
    previous: Rank | None = None
    for candidate in ranks:
        if candidate.sort_order < rank.sort_order and (
            previous is None or candidate.sort_order > previous.sort_order
        ):
            previous = candidate
    if previous is None:
        return None, True  # first rank: SINCE_RANK degrades to all history
    progress = get_progress(member_id, previous.id, session)
    if progress is None or progress.completed_date is None:
        return None, False
    return progress.completed_date, True


@dataclass
class ConditionProgress:
    """One evaluated metric condition — feeds both auto-credit and the UI meters."""

    kind: str
    window: str
    threshold: float
    value: float | None  # None ⇒ the window anchor is unavailable (e.g. no prior BOR)
    met: bool


def evaluate_requirement_metrics(
    requirement: Requirement,
    member_id: uuid.UUID,
    rank: Rank,
    metrics: MemberMetrics,
    session: Session,
) -> list[ConditionProgress]:
    """Evaluate a requirement's metric conditions (AND-ed) for one member."""
    from app.models.enums import MetricKind, MetricWindow

    results: list[ConditionProgress] = []
    for condition in requirement.metrics or []:
        kind = MetricKind(condition["kind"])
        window = MetricWindow(condition.get("window", "any"))
        threshold = float(condition["threshold"])
        anchor: date | None = None
        available = True
        if window == MetricWindow.SINCE_JOINING:
            anchor = _joining_anchor(member_id, session, metrics)
        elif window == MetricWindow.SINCE_RANK:
            anchor, available = _previous_rank_anchor(member_id, rank, session)
        if not available:
            results.append(ConditionProgress(kind.value, window.value, threshold, None, False))
            continue
        value = metrics.value(kind, anchor)
        results.append(
            ConditionProgress(kind.value, window.value, threshold, value, value >= threshold)
        )
    return results


def apply_auto_credits(
    member_id: uuid.UUID, session: Session, *, today: date | None = None
) -> list[MemberRequirementCompletion]:
    """Record completions for auto-credit requirements whose thresholds are met.

    The core payoff of event-integrated advancement (GH-92): crossing a
    computable threshold records the completion — born ``approved`` (attendance
    is already chair-controlled data), ``recorded_via=auto``. Invariants:

    - **Never re-create.** Any existing row — approved, reported, rejected, or
      revoked (soft-deleted) — blocks the credit permanently.
    - **Never auto-revoke.** Later metric changes leave completions standing
      (the UI flags them for human review instead).
    - Only ranks not yet completed accrue, each under its elected (or latest)
      set; Scout–First Class accrue simultaneously per BSA rules.

    Flushes but does not commit. Callers own the transaction and are expected
    to skip tenants whose ``advancement_mode`` is ``disabled``.
    """
    from app.models.enums import CompletionStatus, RecordedVia
    from app.models.member import Member

    member = session.get(Member, member_id)
    if member is None:
        return []
    # Stamp tenant_id explicitly: the engine also runs from the CLI and direct
    # sessions where no request tenant context is active.
    tenant_id = member.tenant_id

    metrics = compute_member_metrics(member_id, session, today=today)
    effective_today = metrics.today

    with include_deleted():
        blocked_requirement_ids = {
            c.requirement_id
            for c in session.scalars(
                select(MemberRequirementCompletion).where(
                    MemberRequirementCompletion.member_id == member_id
                )
            )
        }

    created: list[MemberRequirementCompletion] = []
    for rank in ordered_ranks(session):
        progress = get_progress(member_id, rank.id, session)
        if progress is not None and progress.completed_date is not None:
            continue  # rank earned; nothing left to credit
        req_set = (
            session.get(RequirementSet, progress.requirement_set_id)
            if progress is not None
            else latest_requirement_set(rank.id, session)
        )
        if req_set is None:
            continue
        leaves = leaf_requirement_ids(req_set.id, session)
        for requirement in set_requirements(req_set.id, session):
            if (
                not requirement.auto_credit
                or not requirement.metrics
                or requirement.id not in leaves
                or requirement.id in blocked_requirement_ids
            ):
                continue
            conditions = evaluate_requirement_metrics(
                requirement, member_id, rank, metrics, session
            )
            if not conditions or not all(c.met for c in conditions):
                continue
            if progress is None:
                progress = MemberRankProgress(
                    tenant_id=tenant_id,
                    member_id=member_id,
                    rank_id=rank.id,
                    requirement_set_id=req_set.id,
                )
                session.add(progress)
                session.flush()
            completion = MemberRequirementCompletion(
                tenant_id=tenant_id,
                member_id=member_id,
                requirement_id=requirement.id,
                date_completed=effective_today,
                status=CompletionStatus.APPROVED,
                recorded_via=RecordedVia.AUTO,
            )
            session.add(completion)
            blocked_requirement_ids.add(requirement.id)
            created.append(completion)
    session.flush()
    return created


def auto_credit_enabled(tenant_id: uuid.UUID, session: Session) -> bool:
    """The engine is inert for tenants with advancement disabled (GH-92)."""
    from app.models.enums import AdvancementMode
    from app.models.tenant import Tenant

    tenant = session.get(Tenant, tenant_id)
    mode = tenant.advancement_mode if tenant is not None else AdvancementMode.CHAIR_ENTRY
    return mode != AdvancementMode.DISABLED


def recompute_member_advancement(
    member_id: uuid.UUID, tenant_id: uuid.UUID, session: Session
) -> None:
    """Synchronous post-write recompute trigger (attendance, badges, rank dates).

    Bounded by troop size, so in-request is acceptable (GH-92); the
    ``recompute-advancement`` CLI covers pure time-passage thresholds
    (tenure/POR) on a schedule. Commits the credits it creates.
    """
    if not auto_credit_enabled(tenant_id, session):
        return
    if apply_auto_credits(member_id, session):
        session.commit()
