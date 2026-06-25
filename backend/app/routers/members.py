import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbDep, TenantDep, get_or_404, require
from app.core.invite import create_invite_token
from app.models.enums import Permission
from app.models.member import Member
from app.schemas.member import MemberBase, MemberInviteRead, MemberRead, MemberUpdate

router = APIRouter(prefix="/members", tags=["members"])


@router.get(
    "/", response_model=list[MemberRead], dependencies=[Depends(require(Permission.MEMBER_READ))]
)
def list_members(tenant_id: TenantDep, db: DbDep) -> Sequence[Member]:
    return db.scalars(
        select(Member).where(Member.tenant_id == tenant_id, Member.is_deleted.is_(False))
    ).all()


@router.post(
    "/",
    response_model=MemberRead,
    status_code=201,
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def create_member(body: MemberBase, tenant_id: TenantDep, db: DbDep) -> Member:
    member = Member(tenant_id=tenant_id, **body.model_dump())
    db.add(member)
    db.commit()
    db.refresh(member)
    return member


@router.get(
    "/{member_id}",
    response_model=MemberRead,
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def get_member(member_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> Member:
    return get_or_404(db, Member, member_id, tenant_id, "Member not found")


@router.patch(
    "/{member_id}",
    response_model=MemberRead,
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def update_member(
    member_id: uuid.UUID, body: MemberUpdate, tenant_id: TenantDep, db: DbDep
) -> Member:
    member = get_or_404(db, Member, member_id, tenant_id, "Member not found")
    updates = body.model_dump(exclude_unset=True)
    for k, v in updates.items():
        setattr(member, k, v)
    db.commit()
    db.refresh(member)
    return member


@router.delete(
    "/{member_id}", status_code=204, dependencies=[Depends(require(Permission.MEMBER_DELETE))]
)
def delete_member(member_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    member = get_or_404(db, Member, member_id, tenant_id, "Member not found")
    member.is_deleted = True
    db.commit()


@router.post(
    "/{member_id}/invite",
    response_model=MemberInviteRead,
    dependencies=[Depends(require(Permission.ROLE_ASSIGN))],
)
def invite_member(member_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> MemberInviteRead:
    """Generate a signed claim token so a member can link their login account.

    The token is valid for 7 days. Returns 409 if the member already has a
    linked user account.
    """
    member = get_or_404(db, Member, member_id, tenant_id, "Member not found")
    if member.user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member already has a linked user account",
        )
    token, expires_at = create_invite_token(member_id, tenant_id)
    return MemberInviteRead(token=token, expires_at=expires_at)
