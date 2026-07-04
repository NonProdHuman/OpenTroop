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


def ordered_ranks(session: Session) -> list[Rank]:
    return list(
        session.scalars(select(Rank).where(Rank.is_deleted.is_(False)).order_by(Rank.sort_order))
    )
