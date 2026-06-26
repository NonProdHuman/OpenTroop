"""Tests for GET /auth/session."""

import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import MemberType, Permission
from app.models.member import Member
from app.models.role import MemberRoleAssignment, Role, RolePermission
from tests.conftest import (
    ADMIN_USER_ID,
    NEW_USER_ID,
    PLATFORM_ADMIN_USER_ID,
    TENANT_A,
    TENANT_B,
    _ADMIN_MEMBER_IDS,
    _seed_admin,
    _set_shared_overrides,
)


def test_session_admin_member(client: TestClient) -> None:
    """Admin member gets the full permission set and their role listed."""
    r = client.get("/auth/session")
    assert r.status_code == 200
    data = r.json()

    assert data["tenant_id"] == str(TENANT_A)
    assert data["member"] is not None
    assert data["member"]["id"] == str(_ADMIN_MEMBER_IDS[TENANT_A])

    # Admin role short-circuits to ALL permissions
    all_perms = {p.value for p in Permission}
    assert set(data["permissions"]) == all_perms

    # Permissions are sorted
    assert data["permissions"] == sorted(data["permissions"])

    # Roles lists the admin role
    assert len(data["roles"]) == 1
    assert data["roles"][0]["name"] == "Administrators"


def test_session_non_admin_member(client: TestClient, db_session: Session) -> None:
    """Non-admin member with specific permissions gets exactly that resolved set."""
    # Create a regular member linked to ADMIN_USER_ID won't work (already a member).
    # Instead create a fresh user + member with a specific role.
    user_id = uuid.UUID("e0000000-0000-0000-0000-000000000001")
    from app.models.user import User

    user = User(id=user_id, email="regular@test.com", display_name="Regular User")
    db_session.add(user)

    member = Member(
        id=uuid.UUID("e0000000-0000-0000-0000-000000000010"),
        tenant_id=TENANT_A,
        user_id=user_id,
        first_name="Regular",
        last_name="User",
        member_type=MemberType.ADULT,
    )
    db_session.add(member)

    role = Role(tenant_id=TENANT_A, name="Event Admin", slug="event_admin_test")
    db_session.add(role)
    db_session.flush()

    db_session.add(RolePermission(tenant_id=TENANT_A, role_id=role.id, permission=Permission.EVENT_READ))
    db_session.add(RolePermission(tenant_id=TENANT_A, role_id=role.id, permission=Permission.EVENT_CREATE))
    db_session.add(MemberRoleAssignment(tenant_id=TENANT_A, member_id=member.id, role_id=role.id))
    db_session.commit()

    # Use a client authenticating as this new user
    from app.core.auth import get_current_user
    from app.core.database import get_db
    from app.core.tenant import get_tenant_id
    from app.main import app

    import pytest
    from fastapi import Header, HTTPException
    from typing import Annotated

    async def _user_override() -> User:
        return user

    app.dependency_overrides[get_current_user] = _user_override

    with TestClient(app, headers={"X-Tenant-ID": str(TENANT_A)}) as c:
        r = c.get("/auth/session")

    app.dependency_overrides.pop(get_current_user)

    assert r.status_code == 200
    data = r.json()
    assert data["member"]["id"] == str(member.id)
    assert set(data["permissions"]) == {"event:read", "event:create"}
    assert Permission.MEMBER_READ.value not in data["permissions"]
    assert data["roles"][0]["name"] == "Event Admin"


def test_session_no_member(db_session: Session) -> None:
    """Authenticated user with no member in the tenant gets 200 with null member."""
    from app.core.auth import get_current_user
    from app.core.database import get_db
    from app.core.tenant import get_tenant_id
    from app.main import app
    from app.models.user import User

    _set_shared_overrides(db_session)
    # NEW_USER_ID has no member seeded in TENANT_A
    with TestClient(
        app,
        headers={"X-Tenant-ID": str(TENANT_A), "X-Test-User-ID": str(NEW_USER_ID)},
    ) as c:
        r = c.get("/auth/session")
    app.dependency_overrides.clear()

    assert r.status_code == 200
    data = r.json()
    assert data["member"] is None
    assert data["permissions"] == []
    assert data["roles"] == []


def test_session_platform_admin_no_member(db_session: Session) -> None:
    """Platform admin browsing a tenant they're not a member of gets 200, member=null."""
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


def test_session_cross_tenant_different_permissions(db_session: Session) -> None:
    """Same user gets different permission sets in different tenants."""
    _seed_admin(db_session, TENANT_A)
    _seed_admin(db_session, TENANT_B)
    _set_shared_overrides(db_session)

    from app.main import app

    with TestClient(
        app,
        headers={"X-Tenant-ID": str(TENANT_A), "X-Test-User-ID": str(ADMIN_USER_ID)},
    ) as c:
        r_a = c.get("/auth/session")

    with TestClient(
        app,
        headers={"X-Tenant-ID": str(TENANT_B), "X-Test-User-ID": str(ADMIN_USER_ID)},
    ) as c:
        r_b = c.get("/auth/session")

    app.dependency_overrides.clear()

    assert r_a.status_code == 200
    assert r_b.status_code == 200

    # Both are admin in their respective tenants — full perms
    assert set(r_a.json()["permissions"]) == {p.value for p in Permission}
    assert set(r_b.json()["permissions"]) == {p.value for p in Permission}

    # But member IDs differ
    assert r_a.json()["member"]["id"] != r_b.json()["member"]["id"]
    assert r_a.json()["tenant_id"] != r_b.json()["tenant_id"]


def test_session_missing_auth(db_session: Session) -> None:
    """No JWT → 401."""
    from app.core.auth import get_current_user
    from app.core.database import get_db
    from app.core.tenant import get_tenant_id
    from app.main import app

    _set_shared_overrides(db_session)
    with TestClient(app, headers={"X-Tenant-ID": str(TENANT_A)}) as c:
        r = c.get("/auth/session")
    app.dependency_overrides.clear()

    assert r.status_code == 401


def test_session_missing_tenant(db_session: Session) -> None:
    """No tenant header → 422 (missing required header in test override)."""
    _set_shared_overrides(db_session)
    from app.main import app

    with TestClient(app, headers={"X-Test-User-ID": str(ADMIN_USER_ID)}) as c:
        r = c.get("/auth/session")
    app.dependency_overrides.clear()

    # The tenant dep raises 422 for a missing header in the test setup
    assert r.status_code in {403, 422}
