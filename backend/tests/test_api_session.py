"""Tests for GET /auth/session.

Security-critical coverage:
- Correct permissions for admin and non-admin members
- Soft-deleted member treated as no-member (not a permission grant)
- Revoked position assignment removes permission from session
- Asymmetric cross-tenant isolation: member of A gets null/[] in B
- Permissions inherited via a position's functional roles surface in permissions
- Multiple positions: union of permissions from all assigned positions
- roles[] lists the member's positions, never the functional roles behind them
- 401 on missing auth, 422/403 on missing tenant
"""

import uuid
from collections.abc import Generator
from contextlib import contextmanager

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import MemberType, Permission
from app.models.member import Member
from app.models.rbac import (
    FunctionalRole,
    FunctionalRolePermission,
    MemberPositionAssignment,
    Position,
    PositionFunctionalRole,
)
from app.models.user import User
from tests.conftest import (
    _ADMIN_MEMBER_IDS,
    ADMIN_USER_ID,
    NEW_USER_ID,
    PLATFORM_ADMIN_USER_ID,
    TENANT_A,
    TENANT_B,
    _seed_admin,
    _set_shared_overrides,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_user(db: Session, uid: uuid.UUID, email: str = "user@test.com") -> User:
    u = User(id=uid, email=email, display_name=email)
    db.add(u)
    db.flush()
    return u


def _make_member(
    db: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID,
    *,
    mid: uuid.UUID | None = None,
) -> Member:
    m = Member(
        id=mid or uuid.uuid4(),
        tenant_id=tenant_id,
        user_id=user_id,
        first_name="Test",
        last_name="User",
        member_type=MemberType.ADULT,
    )
    db.add(m)
    db.flush()
    return m


def _title(slug: str) -> str:
    return slug.replace("_", " ").replace("-", " ").title()


def _make_position(db: Session, tenant_id: uuid.UUID, slug: str, **kwargs: object) -> Position:
    p = Position(tenant_id=tenant_id, name=_title(slug), slug=slug, **kwargs)
    db.add(p)
    db.flush()
    return p


def _make_functional_role(
    db: Session, tenant_id: uuid.UUID, slug: str, **kwargs: object
) -> FunctionalRole:
    r = FunctionalRole(tenant_id=tenant_id, name=_title(slug), slug=slug, **kwargs)
    db.add(r)
    db.flush()
    return r


def _grant(db: Session, tenant_id: uuid.UUID, role: FunctionalRole, perm: Permission) -> None:
    db.add(
        FunctionalRolePermission(tenant_id=tenant_id, functional_role_id=role.id, permission=perm)
    )
    db.flush()


def _map(db: Session, tenant_id: uuid.UUID, position: Position, role: FunctionalRole) -> None:
    db.add(
        PositionFunctionalRole(
            tenant_id=tenant_id, position_id=position.id, functional_role_id=role.id
        )
    )
    db.flush()


def _assign(
    db: Session, tenant_id: uuid.UUID, member: Member, position: Position
) -> MemberPositionAssignment:
    a = MemberPositionAssignment(tenant_id=tenant_id, member_id=member.id, position_id=position.id)
    db.add(a)
    db.flush()
    return a


def _position_with_perms(
    db: Session, tenant_id: uuid.UUID, slug: str, *perms: Permission
) -> Position:
    """Create a position mapped to a functional role holding ``perms``."""
    position = _make_position(db, tenant_id, slug)
    role = _make_functional_role(db, tenant_id, f"{slug}-role")
    for perm in perms:
        _grant(db, tenant_id, role, perm)
    _map(db, tenant_id, position, role)
    return position


@contextmanager
def _client_for(db: Session, user: User, tenant_id: uuid.UUID) -> Generator[TestClient, None, None]:
    """Yield a TestClient authenticated as the given User in the specified tenant.

    Overrides get_current_user directly so arbitrary user objects work without
    needing to be pre-registered in the conftest _USERS map. Dependency overrides
    are cleared automatically on exit so callers don't repeat the cleanup.
    """
    from app.core.auth import get_current_user
    from app.core.database import get_db
    from app.core.tenant import get_tenant_id
    from app.main import app
    from tests.conftest import _simple_tenant_id

    captured_user = user  # capture for the closure

    async def _user_override() -> User:
        return captured_user

    app.dependency_overrides[get_db] = lambda: db
    app.dependency_overrides[get_tenant_id] = _simple_tenant_id
    app.dependency_overrides[get_current_user] = _user_override

    try:
        with TestClient(app, headers={"X-Tenant-ID": str(tenant_id)}) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# Basic correctness
# ---------------------------------------------------------------------------


def test_session_admin_full_permissions(client: TestClient) -> None:
    """Admin member (is_admin role) gets the complete permission set."""
    r = client.get("/auth/session")
    assert r.status_code == 200
    data = r.json()

    assert data["tenant_id"] == str(TENANT_A)
    assert data["member"]["id"] == str(_ADMIN_MEMBER_IDS[TENANT_A])
    assert set(data["permissions"]) == {p.value for p in Permission}
    assert data["permissions"] == sorted(data["permissions"])  # stable order
    assert len(data["roles"]) == 1
    assert data["roles"][0]["name"] == "Administrator"  # the position, not the functional role


def test_session_non_admin_exact_permissions(db_session: Session) -> None:
    """Non-admin member gets exactly the permissions of their assigned role — no more."""
    _seed_admin(db_session, TENANT_A)
    user_id = uuid.UUID("e1000000-0000-0000-0000-000000000001")
    user = _make_user(db_session, user_id, "regular@test.com")
    member = _make_member(db_session, TENANT_A, user_id)
    position = _position_with_perms(
        db_session, TENANT_A, "event_manager", Permission.EVENT_READ, Permission.EVENT_CREATE
    )
    _assign(db_session, TENANT_A, member, position)
    db_session.commit()

    with _client_for(db_session, user, TENANT_A) as c:
        r = c.get("/auth/session")
    assert r.status_code == 200
    data = r.json()
    assert set(data["permissions"]) == {"event:read", "event:create"}
    assert "member:read" not in data["permissions"]
    assert data["member"]["id"] == str(member.id)
    assert data["roles"][0]["name"] == "Event Manager"


def test_session_no_member_returns_200_with_nulls(db_session: Session) -> None:
    """Authenticated user with no Member in the tenant gets 200, member=null, empty lists."""
    from tests.conftest import _USERS

    no_member_user = _USERS[str(NEW_USER_ID)]
    with _client_for(db_session, no_member_user, TENANT_A) as c:
        r = c.get("/auth/session")
    assert r.status_code == 200
    assert r.json() == {"tenant_id": str(TENANT_A), "member": None, "permissions": [], "roles": []}


def test_session_platform_admin_not_a_member(db_session: Session) -> None:
    """Platform admin browsing a troop they don't belong to gets member=null."""
    from app.main import app

    _set_shared_overrides(db_session)
    with TestClient(
        app,
        headers={"X-Tenant-ID": str(TENANT_A), "X-Test-User-ID": str(PLATFORM_ADMIN_USER_ID)},
    ) as c:
        r = c.get("/auth/session")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()
    assert data["member"] is None
    assert data["permissions"] == []


# ---------------------------------------------------------------------------
# Isolation: soft-deleted member
# ---------------------------------------------------------------------------


def test_session_deleted_member_treated_as_no_member(db_session: Session) -> None:
    """A soft-deleted member must not receive their former permissions.

    This prevents revoked members from retaining access by hitting /auth/session
    after their record has been soft-deleted.
    """
    _seed_admin(db_session, TENANT_A)
    user_id = uuid.UUID("e2000000-0000-0000-0000-000000000001")
    user = _make_user(db_session, user_id, "deleted@test.com")
    member = _make_member(db_session, TENANT_A, user_id)
    position = _position_with_perms(db_session, TENANT_A, "member_reader", Permission.MEMBER_READ)
    _assign(db_session, TENANT_A, member, position)

    # Soft-delete the member
    member.is_deleted = True
    db_session.commit()

    with _client_for(db_session, user, TENANT_A) as c:
        r = c.get("/auth/session")
    assert r.status_code == 200
    data = r.json()
    assert data["member"] is None, "Deleted member must not appear"
    assert data["permissions"] == [], "Deleted member must not have any permissions"


# ---------------------------------------------------------------------------
# Isolation: revoked role assignment
# ---------------------------------------------------------------------------


def test_session_revoked_assignment_drops_permission(db_session: Session) -> None:
    """Soft-deleting a MemberPositionAssignment must remove the permission from the session.

    A position revocation should take effect on the next /auth/session call.
    """
    _seed_admin(db_session, TENANT_A)
    user_id = uuid.UUID("e3000000-0000-0000-0000-000000000001")
    user = _make_user(db_session, user_id, "revoke@test.com")
    member = _make_member(db_session, TENANT_A, user_id)
    position = _position_with_perms(db_session, TENANT_A, "finance_viewer", Permission.FINANCE_READ)
    assignment = _assign(db_session, TENANT_A, member, position)
    db_session.commit()

    # Confirm permission is present before revocation
    with _client_for(db_session, user, TENANT_A) as c:
        before = c.get("/auth/session")
    assert "finance:read" in before.json()["permissions"]

    # Revoke the assignment
    assignment.is_deleted = True
    db_session.commit()

    with _client_for(db_session, user, TENANT_A) as c:
        after = c.get("/auth/session")

    assert after.status_code == 200
    assert after.json()["permissions"] == [], "Revoked assignment must yield no permissions"


# ---------------------------------------------------------------------------
# Isolation: cross-tenant — asymmetric membership
# ---------------------------------------------------------------------------


def test_session_member_of_a_gets_null_in_b(db_session: Session) -> None:
    """A user who is a member of tenant A must get member=null when querying tenant B.

    This is the primary leakage scenario: permissions from one tenant must not
    bleed into another when the user has no member row there.
    """
    _seed_admin(db_session, TENANT_A)
    user_id = uuid.UUID("e4000000-0000-0000-0000-000000000001")
    user = _make_user(db_session, user_id, "onlya@test.com")
    member_a = _make_member(db_session, TENANT_A, user_id)
    position = _position_with_perms(db_session, TENANT_A, "event_writer", Permission.EVENT_WRITE)
    _assign(db_session, TENANT_A, member_a, position)
    db_session.commit()

    # Tenant A — should have permission
    with _client_for(db_session, user, TENANT_A) as c:
        r_a = c.get("/auth/session")
    assert r_a.status_code == 200
    assert "event:write" in r_a.json()["permissions"]

    # Tenant B — user has NO member row; must get member=null and empty permissions
    with _client_for(db_session, user, TENANT_B) as c:
        r_b = c.get("/auth/session")

    assert r_b.status_code == 200
    data_b = r_b.json()
    assert data_b["member"] is None, "User must not get a member record from tenant A"
    assert data_b["permissions"] == [], "User must not inherit tenant A permissions in tenant B"
    assert data_b["tenant_id"] == str(TENANT_B)


def test_session_cross_tenant_different_member_ids(db_session: Session) -> None:
    """Same user as admin in both tenants returns distinct member IDs and tenant IDs."""
    _seed_admin(db_session, TENANT_A)
    _seed_admin(db_session, TENANT_B)
    _set_shared_overrides(db_session)

    from app.main import app

    with TestClient(
        app, headers={"X-Tenant-ID": str(TENANT_A), "X-Test-User-ID": str(ADMIN_USER_ID)}
    ) as c:
        r_a = c.get("/auth/session")

    with TestClient(
        app, headers={"X-Tenant-ID": str(TENANT_B), "X-Test-User-ID": str(ADMIN_USER_ID)}
    ) as c:
        r_b = c.get("/auth/session")

    app.dependency_overrides.clear()

    assert r_a.status_code == 200
    assert r_b.status_code == 200
    assert r_a.json()["member"]["id"] != r_b.json()["member"]["id"]
    assert r_a.json()["tenant_id"] == str(TENANT_A)
    assert r_b.json()["tenant_id"] == str(TENANT_B)


# ---------------------------------------------------------------------------
# Role inheritance: transitive permissions
# ---------------------------------------------------------------------------


def test_session_position_inherits_functional_role_permissions(db_session: Session) -> None:
    """Permissions from a functional role surface via the position that maps to it.

    A member assigned the 'Scoutmaster' position (mapped to the 'event_admin'
    functional role) must have event_admin's permissions in the session response.
    """
    _seed_admin(db_session, TENANT_A)
    user_id = uuid.UUID("e5000000-0000-0000-0000-000000000001")
    user = _make_user(db_session, user_id, "sm@test.com")
    member = _make_member(db_session, TENANT_A, user_id)

    # Functional role with permissions
    event_admin = _make_functional_role(db_session, TENANT_A, "event_admin_group")
    _grant(db_session, TENANT_A, event_admin, Permission.EVENT_CREATE)
    _grant(db_session, TENANT_A, event_admin, Permission.EVENT_WRITE)

    # Position mapped to the functional role
    scoutmaster = _make_position(db_session, TENANT_A, "scoutmaster_pos")
    _map(db_session, TENANT_A, scoutmaster, event_admin)

    _assign(db_session, TENANT_A, member, scoutmaster)
    db_session.commit()

    with _client_for(db_session, user, TENANT_A) as c:
        r = c.get("/auth/session")
    assert r.status_code == 200
    data = r.json()
    # Inherited permissions appear in the resolved set
    assert "event:create" in data["permissions"]
    assert "event:write" in data["permissions"]


def test_session_roles_list_shows_positions_not_functional_roles(db_session: Session) -> None:
    """The roles[] list contains the member's positions, never the functional roles.

    Per the spec: roles[] surfaces the member's positions; the functional roles
    behind them are an implementation detail already folded into permissions.
    """
    _seed_admin(db_session, TENANT_A)
    user_id = uuid.UUID("e6000000-0000-0000-0000-000000000001")
    user = _make_user(db_session, user_id, "direct@test.com")
    member = _make_member(db_session, TENANT_A, user_id)

    functional_role = _make_functional_role(db_session, TENANT_A, "member_admin_group")
    _grant(db_session, TENANT_A, functional_role, Permission.MEMBER_READ)

    position = _make_position(db_session, TENANT_A, "asst_scoutmaster")
    _map(db_session, TENANT_A, position, functional_role)
    _assign(db_session, TENANT_A, member, position)
    db_session.commit()

    with _client_for(db_session, user, TENANT_A) as c:
        r = c.get("/auth/session")
    assert r.status_code == 200
    data = r.json()
    role_names = {role["name"] for role in data["roles"]}
    assert "Asst Scoutmaster" in role_names
    assert "Member Admin Group" not in role_names, (
        "Functional role must not appear in roles[] — only positions do"
    )
    # But the inherited permission must still be present
    assert "member:read" in data["permissions"]


# ---------------------------------------------------------------------------
# Multiple roles: union of permissions
# ---------------------------------------------------------------------------


def test_session_multiple_positions_union(db_session: Session) -> None:
    """Member assigned two positions gets the union of permissions from both."""
    _seed_admin(db_session, TENANT_A)
    user_id = uuid.UUID("e7000000-0000-0000-0000-000000000001")
    user = _make_user(db_session, user_id, "multi@test.com")
    member = _make_member(db_session, TENANT_A, user_id)

    position_a = _position_with_perms(db_session, TENANT_A, "event_viewer", Permission.EVENT_READ)
    position_b = _position_with_perms(db_session, TENANT_A, "member_viewer", Permission.MEMBER_READ)

    _assign(db_session, TENANT_A, member, position_a)
    _assign(db_session, TENANT_A, member, position_b)
    db_session.commit()

    with _client_for(db_session, user, TENANT_A) as c:
        r = c.get("/auth/session")
    assert r.status_code == 200
    data = r.json()
    assert set(data["permissions"]) == {"event:read", "member:read"}
    role_names = {role["name"] for role in data["roles"]}
    assert role_names == {"Event Viewer", "Member Viewer"}


# ---------------------------------------------------------------------------
# Auth and tenant errors
# ---------------------------------------------------------------------------


def test_session_missing_auth_returns_401(db_session: Session) -> None:
    _set_shared_overrides(db_session)
    from app.main import app

    with TestClient(app, headers={"X-Tenant-ID": str(TENANT_A)}) as c:
        r = c.get("/auth/session")
    app.dependency_overrides.clear()

    assert r.status_code == 401


def test_session_missing_tenant_returns_4xx(db_session: Session) -> None:
    _set_shared_overrides(db_session)
    from app.main import app

    with TestClient(app, headers={"X-Test-User-ID": str(ADMIN_USER_ID)}) as c:
        r = c.get("/auth/session")
    app.dependency_overrides.clear()

    assert r.status_code in {403, 422}
