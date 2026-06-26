from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import select

from app.core.deps import CurrentUserDep, DbDep, TenantDep
from app.core.invite import decode_invite_token
from app.core.permissions import resolve_permissions
from app.core.tenant_context import unscoped
from app.models.member import Member
from app.models.role import MemberRoleAssignment, Role
from app.models.tenant import Tenant
from app.schemas.member import MemberRead
from app.schemas.membership import MembershipRead
from app.schemas.session import SessionRead, SessionRoleRead
from app.schemas.user import UserRead

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/me", response_model=UserRead)
def get_me(current_user: CurrentUserDep) -> object:
    return current_user


@router.get("/memberships", response_model=list[MembershipRead])
def get_memberships(user: CurrentUserDep, db: DbDep) -> list[MembershipRead]:
    """Return all troops (tenants) the authenticated user belongs to.

    Cross-tenant by design — the caller asks "which troops am I in?"  Runs via
    ``unscoped()`` so the app-layer tenant filter is bypassed, but the query
    still constrains ``Member.user_id == user.id`` (bypass removes tenant
    scoping, never the user constraint).  Suspended tenants are excluded.
    """
    is_admin_subq = (
        select(MemberRoleAssignment.id)
        .join(Role, Role.id == MemberRoleAssignment.role_id)
        .where(
            MemberRoleAssignment.member_id == Member.id,
            MemberRoleAssignment.is_deleted.is_(False),
            Role.is_admin.is_(True),
            Role.is_deleted.is_(False),
        )
        .exists()
    )

    with unscoped():
        rows = db.execute(
            select(
                Member.id.label("member_id"),
                Member.tenant_id,
                Tenant.name.label("tenant_name"),
                Tenant.slug.label("tenant_slug"),
                is_admin_subq.label("is_admin"),
            )
            .join(Tenant, Tenant.id == Member.tenant_id)
            .where(
                Member.user_id == user.id,
                Member.is_deleted.is_(False),
                Tenant.is_deleted.is_(False),
                Tenant.suspended_at.is_(None),
            )
            .order_by(Tenant.name)
        ).all()

    return [
        MembershipRead(
            tenant_id=row.tenant_id,
            tenant_name=row.tenant_name,
            tenant_slug=row.tenant_slug,
            member_id=row.member_id,
            is_admin=bool(row.is_admin),
        )
        for row in rows
    ]


@router.get("/session", response_model=SessionRead)
def get_session(user: CurrentUserDep, tenant_id: TenantDep, db: DbDep) -> SessionRead:
    """Return the caller's member and resolved permissions in the current tenant.

    Any authenticated user may call this. Returns 200 with member=null and
    permissions=[] when the user has no Member in the active tenant — not an error.
    Protected actions still 403 via require() on their own routes.
    """
    member = db.scalar(
        select(Member).where(
            Member.user_id == user.id,
            Member.tenant_id == tenant_id,
            Member.is_deleted.is_(False),
        )
    )

    if member is None:
        return SessionRead(tenant_id=tenant_id, member=None, permissions=[], roles=[])

    permissions = sorted(resolve_permissions(member.id, db))

    direct_role_ids = set(
        db.scalars(
            select(MemberRoleAssignment.role_id).where(
                MemberRoleAssignment.member_id == member.id,
                MemberRoleAssignment.is_deleted.is_(False),
            )
        ).all()
    )
    roles = list(
        db.scalars(
            select(Role).where(
                Role.id.in_(direct_role_ids),
                Role.tenant_id == tenant_id,
                Role.is_deleted.is_(False),
            )
        ).all()
    )

    return SessionRead(
        tenant_id=tenant_id,
        member=MemberRead.model_validate(member),
        permissions=permissions,
        roles=[SessionRoleRead.model_validate(r) for r in roles],
    )


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

    with unscoped():
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
