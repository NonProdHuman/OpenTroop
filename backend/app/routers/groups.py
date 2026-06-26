import uuid
from collections.abc import Sequence

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select

from app.core.deps import DbDep, TenantDep, get_or_404, require, require_tenant_fk
from app.core.groups import resolve_group_members
from app.models.enums import GroupType, MemberType, Permission
from app.models.group import Group, GroupMember, GroupRoleRule
from app.models.member import Member
from app.models.role import Role
from app.schemas.group import (
    GroupCreate,
    GroupMemberCreate,
    GroupMemberRead,
    GroupRead,
    GroupRoleRuleCreate,
    GroupRoleRuleRead,
    GroupUpdate,
)
from app.schemas.member import MemberRead

router = APIRouter(prefix="/groups", tags=["groups"])


# ---------------------------------------------------------------------------
# Group CRUD
# ---------------------------------------------------------------------------


@router.get(
    "/", response_model=list[GroupRead], dependencies=[Depends(require(Permission.MEMBER_READ))]
)
def list_groups(tenant_id: TenantDep, db: DbDep) -> Sequence[Group]:
    return db.scalars(
        select(Group).where(Group.tenant_id == tenant_id, Group.is_deleted.is_(False))
    ).all()


@router.post(
    "/",
    response_model=GroupRead,
    status_code=201,
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def create_group(body: GroupCreate, tenant_id: TenantDep, db: DbDep) -> Group:
    existing = db.scalar(
        select(Group).where(
            Group.tenant_id == tenant_id,
            Group.name == body.name,
            Group.is_deleted.is_(False),
        )
    )
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="A group with this name already exists"
        )
    group = Group(tenant_id=tenant_id, **body.model_dump())
    db.add(group)
    db.commit()
    db.refresh(group)
    return group


@router.get(
    "/{group_id}",
    response_model=GroupRead,
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def get_group(group_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> Group:
    return get_or_404(db, Group, group_id, tenant_id, "Group not found")


@router.patch(
    "/{group_id}",
    response_model=GroupRead,
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def update_group(group_id: uuid.UUID, body: GroupUpdate, tenant_id: TenantDep, db: DbDep) -> Group:
    group = get_or_404(db, Group, group_id, tenant_id, "Group not found")
    for k, v in body.model_dump(exclude_unset=True).items():
        setattr(group, k, v)
    db.commit()
    db.refresh(group)
    return group


@router.delete(
    "/{group_id}", status_code=204, dependencies=[Depends(require(Permission.MEMBER_DELETE))]
)
def delete_group(group_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> None:
    group = get_or_404(db, Group, group_id, tenant_id, "Group not found")
    if group.is_system:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="System groups cannot be deleted"
        )
    group.is_deleted = True
    db.commit()


# ---------------------------------------------------------------------------
# Resolved membership
# ---------------------------------------------------------------------------


@router.get(
    "/{group_id}/members",
    response_model=list[MemberRead],
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def list_group_members(group_id: uuid.UUID, tenant_id: TenantDep, db: DbDep) -> Sequence[Member]:
    """Return the group's resolved membership (manual inclusions + rule-derived)."""
    get_or_404(db, Group, group_id, tenant_id, "Group not found")
    member_ids = resolve_group_members(group_id, db)
    if not member_ids:
        return []
    return db.scalars(
        select(Member).where(
            Member.id.in_(member_ids),
            Member.tenant_id == tenant_id,
            Member.is_deleted.is_(False),
        )
    ).all()


@router.post(
    "/{group_id}/members",
    response_model=GroupMemberRead,
    status_code=201,
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def add_group_member(
    group_id: uuid.UUID, body: GroupMemberCreate, tenant_id: TenantDep, db: DbDep
) -> GroupMember:
    """Add a manual (explicit) member to a group.

    Idempotent — re-adding an existing member returns the existing row. For a
    PATROL group, any prior PATROL membership of the member is cleared first, so
    a member belongs to at most one patrol.
    """
    group = get_or_404(db, Group, group_id, tenant_id, "Group not found")
    require_tenant_fk(db, Member, body.member_id, tenant_id, "member_id")

    existing = db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.member_id == body.member_id,
            GroupMember.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return existing

    member = db.get(Member, body.member_id)
    if member is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Member not found",
        )

    if group.group_type is GroupType.PATROL and member.member_type is MemberType.ADULT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Adults cannot be members of a patrol",
        )

    if group.group_type is GroupType.PATROL:
        _clear_patrol_membership(db, tenant_id, body.member_id)

    gm = GroupMember(tenant_id=tenant_id, group_id=group_id, member_id=body.member_id)
    db.add(gm)
    db.commit()
    db.refresh(gm)
    return gm


@router.delete(
    "/{group_id}/members/{member_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def remove_group_member(
    group_id: uuid.UUID, member_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> None:
    get_or_404(db, Group, group_id, tenant_id, "Group not found")
    gm = db.scalar(
        select(GroupMember).where(
            GroupMember.group_id == group_id,
            GroupMember.member_id == member_id,
            GroupMember.tenant_id == tenant_id,
            GroupMember.is_deleted.is_(False),
        )
    )
    if gm is None:
        raise HTTPException(status_code=404, detail="Member is not in this group")
    gm.is_deleted = True
    db.commit()


# ---------------------------------------------------------------------------
# Dynamic role rules
# ---------------------------------------------------------------------------


@router.get(
    "/{group_id}/rules",
    response_model=list[GroupRoleRuleRead],
    dependencies=[Depends(require(Permission.MEMBER_READ))],
)
def list_group_rules(
    group_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> Sequence[GroupRoleRule]:
    get_or_404(db, Group, group_id, tenant_id, "Group not found")
    return db.scalars(
        select(GroupRoleRule).where(
            GroupRoleRule.group_id == group_id, GroupRoleRule.is_deleted.is_(False)
        )
    ).all()


@router.post(
    "/{group_id}/rules",
    response_model=GroupRoleRuleRead,
    status_code=201,
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def add_group_rule(
    group_id: uuid.UUID, body: GroupRoleRuleCreate, tenant_id: TenantDep, db: DbDep
) -> GroupRoleRule:
    """Add a dynamic membership rule — members holding ``role_id`` join the group.

    Idempotent — re-adding an existing rule returns the existing row.
    """
    get_or_404(db, Group, group_id, tenant_id, "Group not found")
    require_tenant_fk(db, Role, body.role_id, tenant_id, "role_id")

    existing = db.scalar(
        select(GroupRoleRule).where(
            GroupRoleRule.group_id == group_id,
            GroupRoleRule.role_id == body.role_id,
            GroupRoleRule.is_deleted.is_(False),
        )
    )
    if existing is not None:
        return existing

    rule = GroupRoleRule(tenant_id=tenant_id, group_id=group_id, role_id=body.role_id)
    db.add(rule)
    db.commit()
    db.refresh(rule)
    return rule


@router.delete(
    "/{group_id}/rules/{role_id}",
    status_code=204,
    dependencies=[Depends(require(Permission.MEMBER_WRITE))],
)
def remove_group_rule(
    group_id: uuid.UUID, role_id: uuid.UUID, tenant_id: TenantDep, db: DbDep
) -> None:
    get_or_404(db, Group, group_id, tenant_id, "Group not found")
    rule = db.scalar(
        select(GroupRoleRule).where(
            GroupRoleRule.group_id == group_id,
            GroupRoleRule.role_id == role_id,
            GroupRoleRule.tenant_id == tenant_id,
            GroupRoleRule.is_deleted.is_(False),
        )
    )
    if rule is None:
        raise HTTPException(status_code=404, detail="Rule not found")
    rule.is_deleted = True
    db.commit()


def _clear_patrol_membership(db: DbDep, tenant_id: uuid.UUID, member_id: uuid.UUID) -> None:
    """Soft-delete a member's existing PATROL-group memberships (one patrol per member)."""
    rows = db.scalars(
        select(GroupMember)
        .join(Group, Group.id == GroupMember.group_id)
        .where(
            GroupMember.member_id == member_id,
            GroupMember.tenant_id == tenant_id,
            GroupMember.is_deleted.is_(False),
            Group.group_type == GroupType.PATROL,
        )
    ).all()
    for row in rows:
        row.is_deleted = True
