import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends
from sqlalchemy import select

from app.core.deps import DbDep, TenantDep, get_or_404, require, require_tenant_fk
from app.models.enums import Permission
from app.models.member import Member
from app.models.patrol import Patrol
from app.schemas.member import MemberBase, MemberRead, MemberUpdate

router = APIRouter(prefix="/members", tags=["members"])


@router.get("/", response_model=list[MemberRead], dependencies=[Depends(require(Permission.MEMBER_READ))])
def list_members(tenant_id: TenantDep, db: DbDep) -> Sequence[Member]:
    return db.scalars(
        select(Member).where(Member.tenant_id == tenant_id, Member.is_deleted.is_(False))
    ).all()


@router.post("/", response_model=MemberRead, status_code=201, dependencies=[Depends(require(Permission.MEMBER_WRITE))])
def create_member(body: MemberBase, tenant_id: TenantDep, db: DbDep) -> Member:
    if body.patrol_id is not None:
        require_tenant_fk(db, Patrol, body.patrol_id, tenant_id, "patrol_id")
    member = Member(tenant_id=tenant_id, **body.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get("/{member_id}", response_model=MemberRead, dependencies=[Depends(require(Permission.MEMBER_READ))])
def get_member(member_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> Member:
    return get_or_404(db, Member, member_id, tenant_id, "Member not found")


@router.patch("/{member_id}", response_model=MemberRead, dependencies=[Depends(require(Permission.MEMBER_WRITE))])
def update_member(
    member_id: uuid.UUID, body: MemberUpdate, tenant_id: TenantDep, db: DbDep
) -> Member:
    member = get_or_404(db, Member, member_id, tenant_id, "Member not found")
    updates = body.model_dump(exclude_unset=True)
    if "patrol_id" in updates and updates["patrol_id"] is not None:
        require_tenant_fk(db, Patrol, updates["patrol_id"], tenant_id, "patrol_id")
    for k, v in updates.items():
        setattr(member, k, v)
    db.commit()
    db.refresh(member)
    return member


@router.delete("/{member_id}", status_code=204, dependencies=[Depends(require(Permission.MEMBER_DELETE))])
def delete_member(member_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    member = get_or_404(db, Member, member_id, tenant_id, "Member not found")
    member.is_deleted = True
    db.commit()
