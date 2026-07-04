"""Advancement API (GH-92 Phase 2): catalog reads, workflow writes, progress view.

Authorization model (see the spec in GH-92):

- Catalog endpoints (ranks, requirement sets, merit badges) are reference data —
  any authenticated member of the tenant may read them.
- A member's progress view is visible to ``advancement:read`` holders and always
  to the member themselves and their parents/guardians (baseline-access pattern).
- Writes: ``advancement:record`` creates completions born ``approved``;
  scouts/parents may self-report (born ``reported``) only in mode
  ``scout_reported``. Status transitions, revocation, elections, and rank dates
  need ``advancement:approve``.
- The whole surface 404s when the tenant's ``advancement_mode`` is ``disabled``.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.advancement import (
    derive_completion_map,
    get_or_create_progress,
    get_progress,
    latest_requirement_set,
    leaf_requirement_ids,
    member_completions,
    ordered_ranks,
    rank_is_complete,
    set_requirements,
    switch_election,
)
from app.core.deps import DbDep, MemberContextDep, TenantDep, get_or_404
from app.core.relationships import is_guardian_of
from app.models.advancement import (
    MemberMeritBadge,
    MemberRankProgress,
    MemberRequirementCompletion,
    MeritBadge,
    Rank,
    Requirement,
    RequirementSet,
)
from app.models.enums import AdvancementMode, CompletionStatus, Permission, RecordedVia
from app.models.member import Member
from app.models.tenant import Tenant
from app.schemas.advancement import (
    AdvancementQueueRead,
    CompletionCreate,
    CompletionRead,
    CompletionUpdate,
    ElectionResult,
    ElectionUpdate,
    MemberAdvancementRead,
    MemberMeritBadgeCreate,
    MemberMeritBadgeRead,
    MemberMeritBadgeUpdate,
    MemberRankView,
    MeritBadgeRead,
    RankProgressRead,
    RankProgressUpdate,
    RankRead,
    RankWithSets,
    RequirementProgress,
    RequirementRead,
    RequirementSetDetail,
    RequirementSetRead,
)

router = APIRouter(tags=["advancement"])


def get_advancement_mode(tenant_id: TenantDep, db: DbDep) -> AdvancementMode:
    """Resolve the tenant's advancement mode; 404 the whole surface when disabled.

    A missing Tenant row (tests, fresh self-host bootstrap) falls back to the
    model default so the API behaves like a newly provisioned tenant.
    """
    tenant = db.get(Tenant, tenant_id)
    mode = tenant.advancement_mode if tenant is not None else AdvancementMode.CHAIR_ENTRY
    if mode is AdvancementMode.DISABLED:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    return mode


ModeDep = Annotated[AdvancementMode, Depends(get_advancement_mode)]


def _now() -> datetime:
    return datetime.now(UTC)


def _may_view(actor: Member, perms: frozenset[Permission], target_id: uuid.UUID, db: DbDep) -> bool:
    if Permission.ADVANCEMENT_READ in perms or actor.id == target_id:
        return True
    return is_guardian_of(actor.id, target_id, db)


def _may_self_report(actor: Member, mode: AdvancementMode, target_id: uuid.UUID, db: DbDep) -> bool:
    if mode is not AdvancementMode.SCOUT_REPORTED:
        return False
    return actor.id == target_id or is_guardian_of(actor.id, target_id, db)


def _requirement_read(req: Requirement) -> RequirementRead:
    return RequirementRead(
        id=req.id,
        created_at=req.created_at,
        updated_at=req.updated_at,
        is_deleted=req.is_deleted,
        requirement_set_id=req.requirement_set_id,
        number=req.number,
        letter=req.letter,
        label=req.label,
        parent_id=req.parent_id,
        sort_order=req.sort_order,
        text=req.text,
        stable_key=req.stable_key,
        metrics=req.metrics,
        auto_credit=req.auto_credit,
    )


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


@router.get("/advancement/ranks", response_model=list[RankWithSets])
def list_ranks(mode: ModeDep, ctx: MemberContextDep, db: DbDep) -> list[RankWithSets]:
    ranks = ordered_ranks(db)
    out: list[RankWithSets] = []
    for rank in ranks:
        sets = [
            RequirementSetRead.model_validate(s) for s in rank.requirement_sets if not s.is_deleted
        ]
        sets.sort(key=lambda s: s.version, reverse=True)
        base = RankRead.model_validate(rank)
        out.append(RankWithSets(**base.model_dump(), requirement_sets=sets))
    return out


@router.get("/advancement/requirement-sets/{set_id}", response_model=RequirementSetDetail)
def get_requirement_set(
    set_id: uuid.UUID, mode: ModeDep, ctx: MemberContextDep, db: DbDep
) -> RequirementSetDetail:
    req_set = db.get(RequirementSet, set_id)
    if req_set is None or req_set.is_deleted:
        raise HTTPException(status_code=404, detail="Requirement set not found")
    base = RequirementSetRead.model_validate(req_set)
    return RequirementSetDetail(
        **base.model_dump(),
        requirements=[_requirement_read(r) for r in set_requirements(req_set.id, db)],
    )


@router.get("/merit-badges", response_model=list[MeritBadgeRead])
def list_merit_badges(mode: ModeDep, ctx: MemberContextDep, db: DbDep) -> list[MeritBadgeRead]:
    badges = db.scalars(
        select(MeritBadge).where(MeritBadge.is_deleted.is_(False)).order_by(MeritBadge.name)
    )
    return [MeritBadgeRead.model_validate(b) for b in badges]


# ---------------------------------------------------------------------------
# Member progress view
# ---------------------------------------------------------------------------


@router.get("/members/{member_id}/advancement", response_model=MemberAdvancementRead)
def member_advancement(
    member_id: uuid.UUID, mode: ModeDep, ctx: MemberContextDep, db: DbDep
) -> MemberAdvancementRead:
    actor, perms = ctx
    get_or_404(db, Member, member_id, "Member not found")
    if not _may_view(actor, perms, member_id, db):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    rank_views: list[MemberRankView] = []
    for rank in ordered_ranks(db):
        progress = get_progress(member_id, rank.id, db)
        req_set = (
            progress.requirement_set
            if progress is not None
            else latest_requirement_set(rank.id, db)
        )
        if req_set is None:
            continue  # catalog not seeded for this rank
        requirements = set_requirements(req_set.id, db)
        completions = member_completions(
            member_id, db, requirement_ids=frozenset(r.id for r in requirements)
        )
        by_req = {c.requirement_id: c for c in completions}
        complete_map = derive_completion_map(requirements, completions)
        rank_views.append(
            MemberRankView(
                rank=RankRead.model_validate(rank),
                requirement_set=RequirementSetRead.model_validate(req_set),
                progress=RankProgressRead.model_validate(progress) if progress else None,
                requirements=[
                    RequirementProgress(
                        requirement=_requirement_read(r),
                        completion=(
                            CompletionRead.model_validate(by_req[r.id]) if r.id in by_req else None
                        ),
                        is_complete=complete_map.get(r.id, False),
                    )
                    for r in requirements
                ],
                is_complete=rank_is_complete(requirements, complete_map),
            )
        )

    badges = db.scalars(
        select(MemberMeritBadge).where(MemberMeritBadge.member_id == member_id)
    ).all()
    return MemberAdvancementRead(
        member_id=member_id,
        ranks=rank_views,
        merit_badges=[MemberMeritBadgeRead.model_validate(b) for b in badges],
    )


# ---------------------------------------------------------------------------
# Requirement completions
# ---------------------------------------------------------------------------


@router.post(
    "/members/{member_id}/advancement/completions",
    response_model=CompletionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_completion(
    member_id: uuid.UUID,
    body: CompletionCreate,
    mode: ModeDep,
    ctx: MemberContextDep,
    db: DbDep,
) -> CompletionRead:
    actor, perms = ctx
    get_or_404(db, Member, member_id, "Member not found")

    is_recorder = Permission.ADVANCEMENT_RECORD in perms
    if not is_recorder and not _may_self_report(actor, mode, member_id, db):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    requirement = db.get(Requirement, body.requirement_id)
    if requirement is None or requirement.is_deleted:
        raise HTTPException(status_code=422, detail="requirement_id not found")
    req_set = requirement.requirement_set
    if requirement.id not in leaf_requirement_ids(req_set.id, db):
        raise HTTPException(
            status_code=422,
            detail="Container requirements derive from their sub-items; complete those instead",
        )

    # Lazy election: first completion creates the progress row. If an election
    # already exists it must match the requirement's set — no cross-set entries.
    progress = get_progress(member_id, req_set.rank_id, db)
    if progress is None:
        progress = MemberRankProgress(
            member_id=member_id, rank_id=req_set.rank_id, requirement_set_id=req_set.id
        )
        db.add(progress)
        db.flush()
    elif progress.requirement_set_id != req_set.id:
        raise HTTPException(
            status_code=422,
            detail="Requirement belongs to a different version than this member's election",
        )

    existing = db.scalar(
        select(MemberRequirementCompletion).where(
            MemberRequirementCompletion.member_id == member_id,
            MemberRequirementCompletion.requirement_id == requirement.id,
        )
    )
    if existing is not None:
        if existing.status is not CompletionStatus.REJECTED:
            raise HTTPException(status_code=409, detail="Completion already recorded")
        # Re-report after rejection: reuse the row so history/audit stays intact.
        existing.date_completed = body.date_completed
        existing.note = body.note
        existing.reported_by_id = actor.id
        if is_recorder:
            existing.status = CompletionStatus.APPROVED
            existing.approved_by_id = actor.id
            existing.approved_at = _now()
        else:
            existing.status = CompletionStatus.REPORTED
            existing.approved_by_id = None
            existing.approved_at = None
        db.commit()
        db.refresh(existing)
        return CompletionRead.model_validate(existing)

    completion = MemberRequirementCompletion(
        member_id=member_id,
        requirement_id=requirement.id,
        date_completed=body.date_completed,
        note=body.note,
        reported_by_id=actor.id,
        recorded_via=RecordedVia.MANUAL,
        status=CompletionStatus.APPROVED if is_recorder else CompletionStatus.REPORTED,
        approved_by_id=actor.id if is_recorder else None,
        approved_at=_now() if is_recorder else None,
    )
    db.add(completion)
    db.commit()
    db.refresh(completion)
    return CompletionRead.model_validate(completion)


@router.patch("/advancement/completions/{completion_id}", response_model=CompletionRead)
def update_completion(
    completion_id: uuid.UUID,
    body: CompletionUpdate,
    mode: ModeDep,
    ctx: MemberContextDep,
    db: DbDep,
) -> CompletionRead:
    actor, perms = ctx
    completion = get_or_404(db, MemberRequirementCompletion, completion_id, "Completion not found")
    fields = body.model_dump(exclude_unset=True)

    if "status" in fields and fields["status"] is not None:
        if Permission.ADVANCEMENT_APPROVE not in perms:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        new_status = CompletionStatus(fields["status"])
        completion.status = new_status
        if new_status is CompletionStatus.APPROVED:
            completion.approved_by_id = actor.id
            completion.approved_at = _now()
        else:
            completion.approved_by_id = (
                actor.id if new_status is CompletionStatus.REJECTED else None
            )
            completion.approved_at = _now() if new_status is CompletionStatus.REJECTED else None

    if "date_completed" in fields or "note" in fields:
        if Permission.ADVANCEMENT_RECORD not in perms:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        if "date_completed" in fields and fields["date_completed"] is not None:
            completion.date_completed = fields["date_completed"]
        if "note" in fields:
            completion.note = fields["note"]

    db.commit()
    db.refresh(completion)
    return CompletionRead.model_validate(completion)


@router.delete("/advancement/completions/{completion_id}", status_code=204)
def revoke_completion(
    completion_id: uuid.UUID, mode: ModeDep, ctx: MemberContextDep, db: DbDep
) -> None:
    _, perms = ctx
    if Permission.ADVANCEMENT_APPROVE not in perms:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    completion = get_or_404(db, MemberRequirementCompletion, completion_id, "Completion not found")
    # Revocation is the tombstone: the auto-credit engine treats this row —
    # deleted included — as "do not re-create".
    completion.is_deleted = True
    db.commit()


@router.get("/advancement/queue", response_model=AdvancementQueueRead)
def approval_queue(mode: ModeDep, ctx: MemberContextDep, db: DbDep) -> AdvancementQueueRead:
    _, perms = ctx
    if Permission.ADVANCEMENT_APPROVE not in perms:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    completions = db.scalars(
        select(MemberRequirementCompletion).where(
            MemberRequirementCompletion.status == CompletionStatus.REPORTED
        )
    ).all()
    badges = db.scalars(
        select(MemberMeritBadge).where(MemberMeritBadge.status == CompletionStatus.REPORTED)
    ).all()
    return AdvancementQueueRead(
        completions=[CompletionRead.model_validate(c) for c in completions],
        merit_badges=[MemberMeritBadgeRead.model_validate(b) for b in badges],
    )


# ---------------------------------------------------------------------------
# Rank progress: elections + board-of-review dates
# ---------------------------------------------------------------------------


@router.put(
    "/members/{member_id}/advancement/ranks/{rank_id}/election",
    response_model=ElectionResult,
)
def set_election(
    member_id: uuid.UUID,
    rank_id: uuid.UUID,
    body: ElectionUpdate,
    mode: ModeDep,
    ctx: MemberContextDep,
    db: DbDep,
) -> ElectionResult:
    _, perms = ctx
    if Permission.ADVANCEMENT_APPROVE not in perms:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    get_or_404(db, Member, member_id, "Member not found")
    rank = db.get(Rank, rank_id)
    if rank is None or rank.is_deleted:
        raise HTTPException(status_code=404, detail="Rank not found")
    new_set = db.get(RequirementSet, body.requirement_set_id)
    if new_set is None or new_set.is_deleted or new_set.rank_id != rank_id:
        raise HTTPException(status_code=422, detail="requirement_set_id is not a set of this rank")

    progress = get_or_create_progress(member_id, rank_id, db)
    result = switch_election(progress, new_set, db)
    db.commit()
    db.refresh(progress)
    return ElectionResult(
        progress=RankProgressRead.model_validate(progress),
        remapped=result.remapped,
        skipped_existing=result.skipped_existing,
        unmatched=result.unmatched,
    )


@router.patch("/members/{member_id}/advancement/ranks/{rank_id}", response_model=RankProgressRead)
def update_rank_progress(
    member_id: uuid.UUID,
    rank_id: uuid.UUID,
    body: RankProgressUpdate,
    mode: ModeDep,
    ctx: MemberContextDep,
    db: DbDep,
) -> RankProgressRead:
    _, perms = ctx
    if Permission.ADVANCEMENT_APPROVE not in perms:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    get_or_404(db, Member, member_id, "Member not found")
    rank = db.get(Rank, rank_id)
    if rank is None or rank.is_deleted:
        raise HTTPException(status_code=404, detail="Rank not found")

    progress = get_or_create_progress(member_id, rank_id, db)
    fields = body.model_dump(exclude_unset=True)
    if "completed_date" in fields:
        progress.completed_date = fields["completed_date"]
    if "awarded_date" in fields:
        progress.awarded_date = fields["awarded_date"]
    db.commit()
    db.refresh(progress)
    return RankProgressRead.model_validate(progress)


# ---------------------------------------------------------------------------
# Merit badge records
# ---------------------------------------------------------------------------


@router.post(
    "/members/{member_id}/merit-badges",
    response_model=MemberMeritBadgeRead,
    status_code=status.HTTP_201_CREATED,
)
def create_member_merit_badge(
    member_id: uuid.UUID,
    body: MemberMeritBadgeCreate,
    mode: ModeDep,
    ctx: MemberContextDep,
    db: DbDep,
) -> MemberMeritBadgeRead:
    actor, perms = ctx
    get_or_404(db, Member, member_id, "Member not found")

    is_recorder = Permission.ADVANCEMENT_RECORD in perms
    if not is_recorder and not _may_self_report(actor, mode, member_id, db):
        raise HTTPException(status_code=403, detail="Insufficient permissions")

    badge = db.get(MeritBadge, body.merit_badge_id)
    if badge is None or badge.is_deleted:
        raise HTTPException(status_code=422, detail="merit_badge_id not found")

    existing = db.scalar(
        select(MemberMeritBadge).where(
            MemberMeritBadge.member_id == member_id,
            MemberMeritBadge.merit_badge_id == badge.id,
        )
    )
    if existing is not None and existing.status is not CompletionStatus.REJECTED:
        raise HTTPException(status_code=409, detail="Merit badge already recorded")

    if existing is not None:
        record = existing
        record.date_started = body.date_started
        record.date_completed = body.date_completed
        record.counselor_name = body.counselor_name
        record.reported_by_id = actor.id
    else:
        record = MemberMeritBadge(
            member_id=member_id,
            merit_badge_id=badge.id,
            date_started=body.date_started,
            date_completed=body.date_completed,
            counselor_name=body.counselor_name,
            reported_by_id=actor.id,
        )
        db.add(record)

    if is_recorder:
        record.status = CompletionStatus.APPROVED
        record.approved_by_id = actor.id
        record.approved_at = _now()
    else:
        record.status = CompletionStatus.REPORTED
        record.approved_by_id = None
        record.approved_at = None

    db.commit()
    db.refresh(record)
    return MemberMeritBadgeRead.model_validate(record)


@router.patch("/advancement/merit-badges/{record_id}", response_model=MemberMeritBadgeRead)
def update_member_merit_badge(
    record_id: uuid.UUID,
    body: MemberMeritBadgeUpdate,
    mode: ModeDep,
    ctx: MemberContextDep,
    db: DbDep,
) -> MemberMeritBadgeRead:
    actor, perms = ctx
    record = get_or_404(db, MemberMeritBadge, record_id, "Merit badge record not found")
    fields = body.model_dump(exclude_unset=True)

    if "status" in fields and fields["status"] is not None:
        if Permission.ADVANCEMENT_APPROVE not in perms:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        new_status = CompletionStatus(fields["status"])
        record.status = new_status
        record.approved_by_id = actor.id if new_status is not CompletionStatus.REPORTED else None
        record.approved_at = _now() if new_status is not CompletionStatus.REPORTED else None

    detail_fields = {"date_started", "date_completed", "counselor_name"} & fields.keys()
    if detail_fields:
        if Permission.ADVANCEMENT_RECORD not in perms:
            raise HTTPException(status_code=403, detail="Insufficient permissions")
        for name in detail_fields:
            setattr(record, name, fields[name])

    db.commit()
    db.refresh(record)
    return MemberMeritBadgeRead.model_validate(record)


@router.delete("/advancement/merit-badges/{record_id}", status_code=204)
def revoke_member_merit_badge(
    record_id: uuid.UUID, mode: ModeDep, ctx: MemberContextDep, db: DbDep
) -> None:
    _, perms = ctx
    if Permission.ADVANCEMENT_APPROVE not in perms:
        raise HTTPException(status_code=403, detail="Insufficient permissions")
    record = get_or_404(db, MemberMeritBadge, record_id, "Merit badge record not found")
    record.is_deleted = True
    db.commit()
