from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import CurrentUserDep, DbDep
from app.core.invite import decode_invite_token
from app.models.member import Member
from app.schemas.member import MemberRead
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserRead)
def get_me(current_user: CurrentUserDep) -> object:
    return current_user


class _ClaimRequest(BaseModel):
    token: str


@router.post("/claim", response_model=MemberRead)
def claim_member(body: _ClaimRequest, user: CurrentUserDep, db: DbDep) -> Member:
    """Link the authenticated user's account to an existing Member record.

    The token is obtained from POST /members/{id}/invite (requires ROLE_ASSIGN).
    Idempotent if the calling user already claimed this member. Returns 409 if
    the member was claimed by a different account, or if this user already holds
    a member record in the same tenant.
    """
    member_id, tenant_id = decode_invite_token(body.token)

    member = db.get(Member, member_id)
    if member is None or member.tenant_id != tenant_id or member.is_deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    if member.user_id is not None:
        if member.user_id == user.id:
            return member  # idempotent — already claimed by this user
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member already claimed by another account",
        )

    existing = db.scalar(
        select(Member).where(
            Member.user_id == user.id,
            Member.tenant_id == tenant_id,
            Member.is_deleted.is_(False),
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="You are already a member of this tenant",
        )

    member.user_id = user.id
    db.commit()
    db.refresh(member)
    return member
