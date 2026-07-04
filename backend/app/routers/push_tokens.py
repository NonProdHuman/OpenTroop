"""Push token registration (GH-82). Any authenticated member, own tokens only."""

from fastapi import APIRouter, status
from pydantic import BaseModel, Field
from sqlalchemy import select

from app.core.deps import DbDep, MemberContextDep, TenantDep
from app.models.push import PushToken

router = APIRouter(prefix="/notifications", tags=["notifications"])


class PushTokenRegister(BaseModel):
    token: str = Field(min_length=1, max_length=200)
    platform: str | None = Field(default=None, max_length=16)


class PushTokenRead(BaseModel):
    token: str
    platform: str | None


@router.post("/push-tokens", response_model=PushTokenRead, status_code=status.HTTP_201_CREATED)
def register_push_token(
    body: PushTokenRegister, tenant_id: TenantDep, ctx: MemberContextDep, db: DbDep
) -> PushTokenRead:
    """Idempotent upsert. A token re-registered by a different user (device
    changed hands) re-points to the new member."""
    actor, _ = ctx
    existing = db.scalar(select(PushToken).where(PushToken.token == body.token))
    if existing is not None:
        existing.member_id = actor.id
        existing.platform = body.platform
        existing.is_deleted = False
    else:
        db.add(PushToken(member_id=actor.id, token=body.token, platform=body.platform))
    db.commit()
    return PushTokenRead(token=body.token, platform=body.platform)


@router.delete("/push-tokens", status_code=status.HTTP_204_NO_CONTENT)
def unregister_push_token(
    body: PushTokenRegister, tenant_id: TenantDep, ctx: MemberContextDep, db: DbDep
) -> None:
    """Sign-out cleanup — removes the caller's registration of this token."""
    actor, _ = ctx
    row = db.scalar(
        select(PushToken).where(PushToken.token == body.token, PushToken.member_id == actor.id)
    )
    if row is not None:
        row.is_deleted = True
        db.commit()
