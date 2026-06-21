"""Tests for the Role/Permission/RoleMembership/MemberRoleAssignment models
and the resolve_permissions() algorithm."""

import uuid

from app.core.permissions import resolve_permissions
from app.models import (
    Member,
    MemberRoleAssignment,
    MemberType,
    Permission,
    Role,
    RoleMembership,
    RolePermission,
)


def _make_member(db_session, tenant_id: uuid.UUID, first: str = "Test") -> Member:
    m = Member(
        tenant_id=tenant_id,
        first_name=first,
        last_name="User",
        member_type=MemberType.ADULT,
    )
    db_session.add(m)
    db_session.flush()
    return m


def _make_role(db_session, tenant_id: uuid.UUID, slug: str, **kwargs: object) -> Role:
    r = Role(tenant_id=tenant_id, name=slug.replace("_", " ").title(), slug=slug, **kwargs)
    db_session.add(r)
    db_session.flush()
    return r


def test_role_creation(db_session):
    """Role persists with correct fields and defaults."""
    tenant_id = uuid.uuid4()
    role = _make_role(db_session, tenant_id, "event_admin")
    db_session.commit()
    db_session.refresh(role)

    assert role.slug == "event_admin"
    assert role.is_system is False
    assert role.is_admin is False
    assert role.is_deleted is False


def test_role_permission_assignment(db_session):
    """Permissions can be attached to a role and navigated via relationship."""
    tenant_id = uuid.uuid4()
    role = _make_role(db_session, tenant_id, "event_admin")
    for perm in (Permission.EVENT_CREATE, Permission.EVENT_WRITE, Permission.EVENT_DELETE):
        db_session.add(RolePermission(tenant_id=tenant_id, role_id=role.id, permission=perm))
    db_session.commit()
    db_session.refresh(role)

    granted = {rp.permission for rp in role.permissions}
    assert granted == {Permission.EVENT_CREATE, Permission.EVENT_WRITE, Permission.EVENT_DELETE}


def test_role_membership_hierarchy(db_session):
    """Position role linked to functional group via RoleMembership."""
    tenant_id = uuid.uuid4()
    event_admin = _make_role(db_session, tenant_id, "event_admin")
    scoutmaster = _make_role(db_session, tenant_id, "scoutmaster")

    membership = RoleMembership(
        tenant_id=tenant_id,
        group_role=event_admin,
        member_role=scoutmaster,
    )
    db_session.add(membership)
    db_session.commit()
    db_session.refresh(scoutmaster)
    db_session.refresh(event_admin)

    assert scoutmaster.group_memberships[0].group_role is event_admin
    assert event_admin.role_members[0].member_role is scoutmaster


def test_member_role_assignment(db_session):
    """Member can be assigned to a role; assignment navigates back to member."""
    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)
    role = _make_role(db_session, tenant_id, "scoutmaster", is_system=True)

    assignment = MemberRoleAssignment(
        tenant_id=tenant_id,
        member=member,
        role=role,
        assigned_by_id=member.id,
    )
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(member)

    assert member.role_assignments[0].role is role


def test_resolve_permissions_direct(db_session):
    """Member directly assigned to a functional group gets its permissions."""
    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)
    event_admin = _make_role(db_session, tenant_id, "event_admin")

    for perm in (Permission.EVENT_CREATE, Permission.EVENT_WRITE):
        db_session.add(RolePermission(tenant_id=tenant_id, role_id=event_admin.id, permission=perm))
    db_session.add(
        MemberRoleAssignment(tenant_id=tenant_id, member_id=member.id, role_id=event_admin.id)
    )
    db_session.commit()

    perms = resolve_permissions(member.id, db_session)
    assert Permission.EVENT_CREATE in perms
    assert Permission.EVENT_WRITE in perms
    assert Permission.MEMBER_WRITE not in perms


def test_resolve_permissions_inherited(db_session):
    """Member assigned to a position inherits permissions from its functional groups."""
    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)

    event_admin = _make_role(db_session, tenant_id, "event_admin")
    member_admin = _make_role(db_session, tenant_id, "member_admin")
    scoutmaster = _make_role(db_session, tenant_id, "scoutmaster")

    db_session.add(
        RolePermission(
            tenant_id=tenant_id, role_id=event_admin.id, permission=Permission.EVENT_CREATE
        )
    )
    db_session.add(
        RolePermission(
            tenant_id=tenant_id, role_id=member_admin.id, permission=Permission.MEMBER_WRITE
        )
    )

    # Scoutmaster is a member of both functional groups
    db_session.add(
        RoleMembership(
            tenant_id=tenant_id, group_role_id=event_admin.id, member_role_id=scoutmaster.id
        )
    )
    db_session.add(
        RoleMembership(
            tenant_id=tenant_id, group_role_id=member_admin.id, member_role_id=scoutmaster.id
        )
    )

    db_session.add(
        MemberRoleAssignment(tenant_id=tenant_id, member_id=member.id, role_id=scoutmaster.id)
    )
    db_session.commit()

    perms = resolve_permissions(member.id, db_session)
    assert Permission.EVENT_CREATE in perms
    assert Permission.MEMBER_WRITE in perms
    assert Permission.FINANCE_READ not in perms


def test_resolve_permissions_admin_bypass(db_session):
    """Member in the administrators role receives all permissions."""
    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)
    admins = _make_role(db_session, tenant_id, "administrators", is_admin=True, is_system=True)

    db_session.add(
        MemberRoleAssignment(tenant_id=tenant_id, member_id=member.id, role_id=admins.id)
    )
    db_session.commit()

    perms = resolve_permissions(member.id, db_session)
    assert perms == frozenset(Permission)


def test_resolve_permissions_no_roles(db_session):
    """Member with no role assignments has no permissions."""
    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)
    db_session.commit()

    assert resolve_permissions(member.id, db_session) == frozenset()


def test_resolve_permissions_cycle_safe(db_session):
    """Circular role memberships do not cause infinite recursion."""
    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)
    role_a = _make_role(db_session, tenant_id, "role_a")
    role_b = _make_role(db_session, tenant_id, "role_b")

    # A → B → A cycle
    db_session.add(
        RoleMembership(tenant_id=tenant_id, group_role_id=role_b.id, member_role_id=role_a.id)
    )
    db_session.add(
        RoleMembership(tenant_id=tenant_id, group_role_id=role_a.id, member_role_id=role_b.id)
    )
    db_session.add(
        MemberRoleAssignment(tenant_id=tenant_id, member_id=member.id, role_id=role_a.id)
    )
    db_session.commit()

    # Should not raise RecursionError; result is empty (no permissions on either role)
    perms = resolve_permissions(member.id, db_session)
    assert isinstance(perms, frozenset)
