import logging
import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import (
    CurrentMemberDep,
    DbDep,
    NotificationServiceDep,
    TenantDep,
    get_or_404,
    require,
)
from app.core.invite import build_claim_url, build_invite_email, create_invite_token
from app.core.notifications import EmailSendError
from app.core.permissions import resolve_permissions
from app.core.relationships import family_member_ids
from app.models.enums import GroupType, MemberType, Permission
from app.models.group import Group, GroupMember
from app.models.member import Member
from app.models.tenant import Tenant
from app.schemas.member import MemberBase, MemberInviteRead, MemberRead, MemberUpdate

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/members", tags=["members"])


@router.get(
    "", response_model=list[MemberRead], dependencies=[Depends(require(Permission.MEMBER_READ))]
)
def list_members(tenant_id: TenantDep, db: DbDep) -> Sequence[Member]:
    return db.scalars(select(Member).where(Member.is_deleted.is_(False))).all()


@router.post(
    "",
    response_model=MemberRead,
    status_code=201,
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def create_member(body: MemberBase, tenant_id: TenantDep, db: DbDep) -> Member:
    member = Member(tenant_id=tenant_id, **body.model_dump())
    db.add(member)
    db.flush()

    from app.core.provisioning import get_or_create_member_position
    from app.models.rbac import MemberPositionAssignment

    member_pos = get_or_create_member_position(db, tenant_id)
    db.add(
        MemberPositionAssignment(
            tenant_id=tenant_id, member_id=member.id, position_id=member_pos.id
        )
    )

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
)
def update_member(
    member_id: uuid.UUID,
    body: MemberUpdate,
    tenant_id: TenantDep,
    db: DbDep,
    caller: CurrentMemberDep,
) -> Member:
    member = get_or_404(db, Member, member_id, tenant_id, "Member not found")

    perms = resolve_permissions(caller.id, db)
    can_full_edit = Permission.MEMBER_WRITE in perms

    if not can_full_edit:
        family_ids = family_member_ids(caller.id, db)
        if member_id != caller.id and member_id not in family_ids:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to edit this member"
            )

    updates = body.model_dump(exclude_unset=True)

    if not can_full_edit:
        allowlist = {
            "phone",
            "email",
            "address_line1",
            "address_line2",
            "city",
            "state",
            "postal_code",
            "country",
            "emergency_contact_1_name",
            "emergency_contact_1_phone",
            "emergency_contact_2_name",
            "emergency_contact_2_phone",
            "medical_form_ab_date",
            "medical_form_c_date",
            "allergies",
            "dietary_restrictions",
        }
        for k in updates:
            if k not in allowlist:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Not authorized to edit field: {k}",
                )

    if updates.get("member_type") == MemberType.ADULT:
        patrol_memberships = db.scalars(
            select(GroupMember)
            .join(Group, Group.id == GroupMember.group_id)
            .where(
                GroupMember.member_id == member.id,
                GroupMember.is_deleted.is_(False),
                Group.group_type == GroupType.PATROL,
            )
        ).all()
        for gm in patrol_memberships:
            gm.is_deleted = True

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
def invite_member(
    member_id: uuid.UUID,
    tenant_id: TenantDep,
    db: DbDep,
    notification_service: NotificationServiceDep,
) -> MemberInviteRead:
    """Generate a signed claim token so a member can link their login account.

    The token is valid for 7 days. Returns 409 if the member already has a
    linked user account. If the member has a usable email address, also sends
    an invite email; the token is still returned (and still valid) even if no
    email was sent, so an admin can share the link manually.
    """
    member = get_or_404(db, Member, member_id, tenant_id, "Member not found")
    if member.user_id is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Member already has a linked user account",
        )
    token, expires_at = create_invite_token(member)
    db.commit()  # persist the token's jti; re-inviting revokes any earlier token

    email_sent = False
    if member.email and not member.email_opt_out and not member.email_bounced:
        tenant = db.get(Tenant, tenant_id)
        if tenant is None:
            raise RuntimeError(f"Tenant {tenant_id} resolved for request but missing from DB")
        claim_url = build_claim_url(tenant.slug, token)
        message = build_invite_email(
            to=member.email,
            first_name=member.first_name,
            tenant_name=tenant.name,
            claim_url=claim_url,
        )
        try:
            notification_service.send_email(message)
            email_sent = True
        except EmailSendError:
            logger.warning("Invite email failed to send for member %s", member_id.hex)

    return MemberInviteRead(token=token, expires_at=expires_at, email_sent=email_sent)
