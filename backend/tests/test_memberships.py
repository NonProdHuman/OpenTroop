"""Tests for GET /auth/memberships — cross-tenant membership listing."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import MemberType
from app.models.member import Member
from app.models.rbac import (
    FunctionalRole,
    MemberPositionAssignment,
    Position,
    PositionFunctionalRole,
)
from app.models.tenant import Tenant
from tests.conftest import ADMIN_USER_ID, NEW_USER_ID, TENANT_A, TENANT_B


def _seed_tenant(db: Session, tenant_id: uuid.UUID, name: str, slug: str) -> Tenant:
    """Insert a Tenant row required for the JOIN in GET /auth/memberships."""
    existing = db.get(Tenant, tenant_id)
    if existing is not None:
        existing.name = name
        existing.slug = slug
        db.flush()
        return existing
    tenant = Tenant(id=tenant_id, name=name, slug=slug)
    db.add(tenant)
    db.flush()
    return tenant


def _seed_member(
    db: Session,
    tenant_id: uuid.UUID,
    user_id: uuid.UUID | None,
    *,
    is_admin: bool = False,
    is_deleted: bool = False,
) -> Member:
    member = Member(
        tenant_id=tenant_id,
        user_id=user_id,
        first_name="Test",
        last_name="User",
        member_type=MemberType.ADULT,
        is_deleted=is_deleted,
    )
    db.add(member)
    db.flush()

    if is_admin:
        slug = f"admin-{tenant_id}"
        role = FunctionalRole(
            tenant_id=tenant_id,
            name=slug,
            slug=slug,
            is_admin=True,
            is_system=True,
        )
        db.add(role)
        db.flush()
        position = Position(
            tenant_id=tenant_id,
            name=f"admin-position-{tenant_id}",
            slug=f"admin-position-{tenant_id}",
            is_system=True,
        )
        db.add(position)
        db.flush()
        db.add(
            PositionFunctionalRole(
                tenant_id=tenant_id, position_id=position.id, functional_role_id=role.id
            )
        )
        db.add(
            MemberPositionAssignment(
                tenant_id=tenant_id, member_id=member.id, position_id=position.id
            )
        )
        db.flush()

    return member


class TestGetMemberships:
    def test_returns_memberships_across_tenants(
        self, client: TestClient, db_session: Session
    ) -> None:
        """A user with members in two tenants sees both.

        The ``client`` fixture already seeds ADMIN_USER_ID as an admin member in
        TENANT_A, so we only need the Tenant rows and a second membership.
        """
        _seed_tenant(db_session, TENANT_A, "Troop A", "troop-a")
        _seed_tenant(db_session, TENANT_B, "Troop B", "troop-b")
        # TENANT_A member already exists via client fixture; add TENANT_B
        _seed_member(db_session, TENANT_B, ADMIN_USER_ID)
        db_session.commit()

        resp = client.get("/auth/memberships")
        assert resp.status_code == 200
        tenant_ids = {m["tenant_id"] for m in resp.json()}
        assert str(TENANT_A) in tenant_ids
        assert str(TENANT_B) in tenant_ids

    def test_is_admin_flag_set_correctly(self, client: TestClient, db_session: Session) -> None:
        """is_admin reflects whether the member holds an admin role.

        TENANT_A member (seeded by client fixture) is already an admin.
        TENANT_B member added here is not.
        """
        _seed_tenant(db_session, TENANT_A, "Troop A", "troop-a")
        _seed_tenant(db_session, TENANT_B, "Troop B", "troop-b")
        _seed_member(db_session, TENANT_B, ADMIN_USER_ID, is_admin=False)
        db_session.commit()

        resp = client.get("/auth/memberships")
        assert resp.status_code == 200
        by_tenant = {m["tenant_id"]: m for m in resp.json()}
        assert by_tenant[str(TENANT_A)]["is_admin"] is True
        assert by_tenant[str(TENANT_B)]["is_admin"] is False

    def test_another_users_memberships_not_included(
        self, claim_client: TestClient, db_session: Session
    ) -> None:
        """A user sees only their own memberships, never another user's."""
        _seed_tenant(db_session, TENANT_A, "Troop A", "troop-a")
        # Both users have a member in TENANT_A
        _seed_member(db_session, TENANT_A, ADMIN_USER_ID)
        _seed_member(db_session, TENANT_A, NEW_USER_ID)
        db_session.commit()

        # claim_client is authenticated as NEW_USER_ID
        resp = claim_client.get("/auth/memberships")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) == 1
        assert data[0]["tenant_id"] == str(TENANT_A)

    def test_soft_deleted_member_excluded(
        self, claim_client: TestClient, db_session: Session
    ) -> None:
        """Soft-deleted Member rows are not returned.

        Uses ``claim_client`` (NEW_USER_ID, no pre-seeded member) so we control
        exactly which members exist.
        """
        _seed_tenant(db_session, TENANT_A, "Troop A", "troop-a")
        _seed_member(db_session, TENANT_A, NEW_USER_ID, is_deleted=True)
        db_session.commit()

        resp = claim_client.get("/auth/memberships")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_suspended_tenant_excluded(self, claim_client: TestClient, db_session: Session) -> None:
        """Suspended tenants are excluded from the switchable list."""
        tenant_id = uuid.UUID("50000000-0000-0000-0000-000000000005")
        t = Tenant(id=tenant_id, name="Suspended", slug="suspended-troop")
        t.suspended_at = datetime.now(UTC)
        db_session.add(t)
        db_session.flush()
        _seed_member(db_session, tenant_id, NEW_USER_ID)
        db_session.commit()

        resp = claim_client.get("/auth/memberships")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_empty_list_for_user_with_no_memberships(self, claim_client: TestClient) -> None:
        """A user with no member rows gets an empty list (not an error)."""
        resp = claim_client.get("/auth/memberships")
        assert resp.status_code == 200
        assert resp.json() == []

    def test_response_shape(self, client: TestClient, db_session: Session) -> None:
        """Response items contain the documented fields."""
        _seed_tenant(db_session, TENANT_A, "Troop A", "troop-a")
        db_session.commit()

        resp = client.get("/auth/memberships")
        assert resp.status_code == 200
        item = resp.json()[0]
        assert {"tenant_id", "tenant_name", "tenant_slug", "member_id", "is_admin"} <= set(
            item.keys()
        )
        assert item["tenant_name"] == "Troop A"
        assert item["tenant_slug"] == "troop-a"
