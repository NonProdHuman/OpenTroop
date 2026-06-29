"""Tests for the Position / FunctionalRole RBAC models and resolve_permissions()."""

import uuid

from app.core.permissions import resolve_permissions
from app.models import (
    FunctionalRole,
    FunctionalRolePermission,
    Member,
    MemberPositionAssignment,
    MemberType,
    Permission,
    Position,
    PositionFunctionalRole,
    PositionScope,
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


def _make_position(db_session, tenant_id: uuid.UUID, slug: str, **kwargs: object) -> Position:
    p = Position(
        tenant_id=tenant_id,
        name=slug.replace("-", " ").title(),
        slug=slug,
        applies_to=PositionScope.ANY,
        **kwargs,
    )
    db_session.add(p)
    db_session.flush()
    return p


def _make_functional_role(
    db_session, tenant_id: uuid.UUID, slug: str, **kwargs: object
) -> FunctionalRole:
    r = FunctionalRole(
        tenant_id=tenant_id, name=slug.replace("-", " ").title(), slug=slug, **kwargs
    )
    db_session.add(r)
    db_session.flush()
    return r


def _grant(db_session, tenant_id, role: FunctionalRole, *perms: Permission) -> None:
    for perm in perms:
        db_session.add(
            FunctionalRolePermission(
                tenant_id=tenant_id, functional_role_id=role.id, permission=perm
            )
        )


def _map(db_session, tenant_id, position: Position, role: FunctionalRole) -> None:
    db_session.add(
        PositionFunctionalRole(
            tenant_id=tenant_id, position_id=position.id, functional_role_id=role.id
        )
    )


def _assign(db_session, tenant_id, member: Member, position: Position) -> None:
    db_session.add(
        MemberPositionAssignment(tenant_id=tenant_id, member_id=member.id, position_id=position.id)
    )


def test_position_creation(db_session):
    """Position persists with correct fields and defaults."""
    tenant_id = uuid.uuid4()
    position = _make_position(db_session, tenant_id, "scoutmaster")
    db_session.commit()
    db_session.refresh(position)

    assert position.slug == "scoutmaster"
    assert position.is_system is False
    assert position.applies_to is PositionScope.ANY
    assert position.is_deleted is False


def test_functional_role_permission_assignment(db_session):
    """Permissions attach to a functional role and navigate via relationship."""
    tenant_id = uuid.uuid4()
    role = _make_functional_role(db_session, tenant_id, "event-admins")
    _grant(
        db_session,
        tenant_id,
        role,
        Permission.EVENT_CREATE,
        Permission.EVENT_WRITE,
        Permission.EVENT_DELETE,
    )
    db_session.commit()
    db_session.refresh(role)

    granted = {rp.permission for rp in role.permissions}
    assert granted == {Permission.EVENT_CREATE, Permission.EVENT_WRITE, Permission.EVENT_DELETE}


def test_position_functional_role_mapping(db_session):
    """A position maps to a functional role and navigates both directions."""
    tenant_id = uuid.uuid4()
    event_admins = _make_functional_role(db_session, tenant_id, "event-admins")
    scoutmaster = _make_position(db_session, tenant_id, "scoutmaster")
    _map(db_session, tenant_id, scoutmaster, event_admins)
    db_session.commit()
    db_session.refresh(scoutmaster)
    db_session.refresh(event_admins)

    assert scoutmaster.functional_role_links[0].functional_role is event_admins
    assert event_admins.position_links[0].position is scoutmaster


def test_member_position_assignment(db_session):
    """Member can be assigned to a position; assignment navigates to both sides."""
    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)
    position = _make_position(db_session, tenant_id, "scoutmaster", is_system=True)
    assignment = MemberPositionAssignment(
        tenant_id=tenant_id,
        member=member,
        position=position,
        assigned_by_id=member.id,
    )
    db_session.add(assignment)
    db_session.commit()
    db_session.refresh(assignment)

    assert assignment.member is member
    assert assignment.position is position


def test_resolve_permissions_single_position(db_session):
    """A member holding a position gets its functional roles' permissions."""
    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)
    event_admins = _make_functional_role(db_session, tenant_id, "event-admins")
    scoutmaster = _make_position(db_session, tenant_id, "scoutmaster")

    _grant(db_session, tenant_id, event_admins, Permission.EVENT_CREATE, Permission.EVENT_WRITE)
    _map(db_session, tenant_id, scoutmaster, event_admins)
    _assign(db_session, tenant_id, member, scoutmaster)
    db_session.commit()

    perms = resolve_permissions(member.id, db_session)
    assert Permission.EVENT_CREATE in perms
    assert Permission.EVENT_WRITE in perms
    assert Permission.MEMBER_WRITE not in perms


def test_resolve_permissions_union_across_roles(db_session):
    """A position mapped to multiple functional roles unions their permissions."""
    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)

    event_admins = _make_functional_role(db_session, tenant_id, "event-admins")
    member_admins = _make_functional_role(db_session, tenant_id, "member-admins")
    scoutmaster = _make_position(db_session, tenant_id, "scoutmaster")

    _grant(db_session, tenant_id, event_admins, Permission.EVENT_CREATE)
    _grant(db_session, tenant_id, member_admins, Permission.MEMBER_WRITE)
    _map(db_session, tenant_id, scoutmaster, event_admins)
    _map(db_session, tenant_id, scoutmaster, member_admins)
    _assign(db_session, tenant_id, member, scoutmaster)
    db_session.commit()

    perms = resolve_permissions(member.id, db_session)
    assert Permission.EVENT_CREATE in perms
    assert Permission.MEMBER_WRITE in perms
    assert Permission.FINANCE_READ not in perms


def test_resolve_permissions_union_across_positions(db_session):
    """A member holding multiple positions unions all their permissions."""
    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)

    finance = _make_functional_role(db_session, tenant_id, "finance-admins")
    advancement = _make_functional_role(db_session, tenant_id, "advancement-admins")
    treasurer = _make_position(db_session, tenant_id, "treasurer")
    adv_chair = _make_position(db_session, tenant_id, "advancement-chair")

    _grant(db_session, tenant_id, finance, Permission.FINANCE_WRITE)
    _grant(db_session, tenant_id, advancement, Permission.ADVANCEMENT_APPROVE)
    _map(db_session, tenant_id, treasurer, finance)
    _map(db_session, tenant_id, adv_chair, advancement)
    _assign(db_session, tenant_id, member, treasurer)
    _assign(db_session, tenant_id, member, adv_chair)
    db_session.commit()

    perms = resolve_permissions(member.id, db_session)
    assert Permission.FINANCE_WRITE in perms
    assert Permission.ADVANCEMENT_APPROVE in perms


def test_resolve_permissions_admin_bypass(db_session):
    """A member whose position maps to an is_admin role receives all permissions."""
    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)
    admins = _make_functional_role(
        db_session, tenant_id, "administrators", is_admin=True, is_system=True
    )
    admin_position = _make_position(db_session, tenant_id, "administrator", is_system=True)
    _map(db_session, tenant_id, admin_position, admins)
    _assign(db_session, tenant_id, member, admin_position)
    db_session.commit()

    perms = resolve_permissions(member.id, db_session)
    assert perms == frozenset(Permission)


def test_resolve_permissions_no_positions(db_session):
    """A member with no positions has no permissions."""
    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)
    db_session.commit()

    assert resolve_permissions(member.id, db_session) == frozenset()


def test_resolve_permissions_excludes_soft_deleted(db_session):
    """Soft-deleting the position assignment removes the permissions."""
    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)
    event_admins = _make_functional_role(db_session, tenant_id, "event-admins")
    scoutmaster = _make_position(db_session, tenant_id, "scoutmaster")

    _grant(db_session, tenant_id, event_admins, Permission.EVENT_CREATE)
    _map(db_session, tenant_id, scoutmaster, event_admins)
    assignment = MemberPositionAssignment(
        tenant_id=tenant_id, member_id=member.id, position_id=scoutmaster.id
    )
    db_session.add(assignment)
    db_session.commit()

    assert Permission.EVENT_CREATE in resolve_permissions(member.id, db_session)

    assignment.is_deleted = True
    db_session.commit()
    assert resolve_permissions(member.id, db_session) == frozenset()


def test_resolve_permissions_excludes_ended_term(db_session):
    """A term with a past end_date no longer grants permissions; a future end stays current."""
    from datetime import UTC, datetime, timedelta

    tenant_id = uuid.uuid4()
    member = _make_member(db_session, tenant_id)
    event_admins = _make_functional_role(db_session, tenant_id, "event-admins")
    scoutmaster = _make_position(db_session, tenant_id, "scoutmaster")
    _grant(db_session, tenant_id, event_admins, Permission.EVENT_CREATE)
    _map(db_session, tenant_id, scoutmaster, event_admins)

    today = datetime.now(UTC).date()
    assignment = MemberPositionAssignment(
        tenant_id=tenant_id,
        member_id=member.id,
        position_id=scoutmaster.id,
        start_date=today - timedelta(days=365),
        end_date=today - timedelta(days=1),  # ended yesterday
    )
    db_session.add(assignment)
    db_session.commit()
    assert resolve_permissions(member.id, db_session) == frozenset()

    # A future end_date is still current → permissions return.
    assignment.end_date = today + timedelta(days=30)
    db_session.commit()
    assert Permission.EVENT_CREATE in resolve_permissions(member.id, db_session)

    # Open-ended (no end_date) is current.
    assignment.end_date = None
    db_session.commit()
    assert Permission.EVENT_CREATE in resolve_permissions(member.id, db_session)
