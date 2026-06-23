import uuid
from collections.abc import Sequence

from fastapi import APIRouter, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.core.deps import DbDep, TenantDep
from app.models.member import Member
from app.models.patrol import Patrol
from app.schemas.member import MemberBase, MemberRead, MemberUpdate

router = APIRouter(prefix="/members", tags=["members"])


def _get_or_404(db: Session, member_id: uuid.UUID, tenant_id: uuid.UUID) -> Member:
    member = db.get(Member, member_id)
    if not member or member.tenant_id != tenant_id or member.is_deleted:
        raise HTTPException(status_code=404, detail="Member not found")
    return member


def _check_patrol_tenant(db: Session, patrol_id: uuid.UUID, tenant_id: uuid.UUID) -> None:
    patrol = db.get(Patrol, patrol_id)
    if not patrol or patrol.tenant_id != tenant_id or patrol.is_deleted:
        raise HTTPException(status_code=422, detail="patrol_id not found in this tenant")


@router.get("/", response_model=list[MemberRead])
def list_members(tenant_id: TenantDep, db: DbDep) -> Sequence[Member]:
    return db.scalars(
        select(Member).where(Member.tenant_id == tenant_id, Member.is_deleted.is_(False))
    ).all()


@router.post("/", response_model=MemberRead, status_code=201)
def create_member(body: MemberBase, tenant_id: TenantDep, db: DbDep) -> Member:
    if body.patrol_id is not None:
        _check_patrol_tenant(db, body.patrol_id, tenant_id)
    member = Member(id=uuid7(), tenant_id=tenant_id, **body.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get("/{member_id}", response_model=MemberRead)
def get_member(member_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> Member:
    return _get_or_404(db, member_id, tenant_id)


@router.patch("/{member_id}", response_model=MemberRead)
def update_member(
    member_id: uuid.UUID, body: MemberUpdate, tenant_id: TenantDep, db: DbDep
) -> Member:
    member = _get_or_404(db, member_id, tenant_id)
    updates = body.model_dump(exclude_unset=True)
    if "patrol_id" in updates and updates["patrol_id"] is not None:
        _check_patrol_tenant(db, updates["patrol_id"], tenant_id)
    for k, v in updates.items():
        setattr(member, k, v)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=204)
def delete_member(member_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    member = _get_or_404(db, member_id, tenant_id)
    member.is_deleted = True
    db.commit()
