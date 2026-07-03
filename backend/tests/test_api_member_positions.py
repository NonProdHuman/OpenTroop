"""API tests for /members/{member_id}/positions — dated position terms."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import Permission
from app.models.member import Member
from app.models.rbac import Position
from app.models.user import User
from tests.conftest import _ADMIN_MEMBER_IDS, TENANT_A, _seed_admin
from tests.test_api_session import _assign as _assign_db
from tests.test_api_session import (
    _client_for,
    _grant,
    _make_functional_role,
    _make_member,
    _make_position,
    _make_user,
    _map,
)


def _create_member(client: TestClient, first_name: str = "Alice") -> dict:
    r = client.post(
        "/members/",
        json={"first_name": first_name, "last_name": "Test", "member_type": "adult"},
    )
    assert r.status_code == 201
    return r.json()


def _create_position(client: TestClient, slug: str = "scoutmaster") -> dict:
    r = client.post("/positions/", json={"name": slug.replace("-", " ").title(), "slug": slug})
    assert r.status_code == 201
    return r.json()


def _assign(client: TestClient, member_id: str, position_id: str, **extra) -> dict:
    r = client.post(f"/members/{member_id}/positions", json={"position_id": position_id, **extra})
    assert r.status_code == 201, r.text
    return r.json()


def test_assign_position(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    data = _assign(client, m["id"], pos["id"])
    assert data["member_id"] == m["id"]
    assert data["position_id"] == pos["id"]
    assert data["assigned_by_id"] == str(_ADMIN_MEMBER_IDS[TENANT_A])
    # A new term defaults to starting today, open-ended → current.
    assert data["start_date"] is not None
    assert data["end_date"] is None
    assert data["is_current"] is True


def test_list_member_positions(client: TestClient) -> None:
    m = _create_member(client)
    p1 = _create_position(client, "scoutmaster")
    p2 = _create_position(client, "treasurer")
    _assign(client, m["id"], p1["id"])
    _assign(client, m["id"], p2["id"])
    position_ids = {a["position_id"] for a in client.get(f"/members/{m['id']}/positions").json()}
    assert {p1["id"], p2["id"]} <= position_ids


def test_assign_duplicate_current_conflicts(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    _assign(client, m["id"], pos["id"])
    r = client.post(f"/members/{m['id']}/positions", json={"position_id": pos["id"]})
    assert r.status_code == 409


def test_delete_term_by_assignment_id(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    a = _assign(client, m["id"], pos["id"])
    resp = client.delete(f"/members/{m['id']}/positions/{a['id']}")
    assert resp.status_code == 204
    positions = client.get(f"/members/{m['id']}/positions").json()
    assert len(positions) == 1
    # Soft-deleted → gone from history too.
    history = client.get(f"/members/{m['id']}/positions?current=false").json()
    assert len(history) == 1


def test_delete_missing_returns_404(client: TestClient) -> None:
    m = _create_member(client)
    import uuid

    resp = client.delete(f"/members/{m['id']}/positions/{uuid.uuid4()}")
    assert resp.status_code == 404


def test_end_term_then_history_and_reassign(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    # Start the term in the past so we can end it in the past too (end >= start).
    a = _assign(client, m["id"], pos["id"], start_date="2025-01-01")

    # End the term in the past via PATCH → no longer current.
    r = client.patch(f"/members/{m['id']}/positions/{a['id']}", json={"end_date": "2025-06-01"})
    assert r.status_code == 200
    assert r.json()["is_current"] is False

    # Default (current) list has the Member position; full history shows the ended term + Member.
    current_pos = client.get(f"/members/{m['id']}/positions").json()
    assert len(current_pos) == 1
    history = client.get(f"/members/{m['id']}/positions?current=false").json()
    assert len(history) == 2
    ended_term = next(a for a in history if a["position_id"] == pos["id"])
    assert ended_term["end_date"] == "2025-06-01"

    # The position can be re-assigned now that the prior term has ended (new row).
    b = _assign(client, m["id"], pos["id"])
    assert b["id"] != a["id"]
    assert len(client.get(f"/members/{m['id']}/positions?current=false").json()) == 3


def test_patch_end_before_start_rejected(client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    a = _assign(client, m["id"], pos["id"], start_date="2025-06-01")
    r = client.patch(f"/members/{m['id']}/positions/{a['id']}", json={"end_date": "2025-01-01"})
    assert r.status_code == 422


def test_assign_position_wrong_tenant(client: TestClient, other_client: TestClient) -> None:
    m = _create_member(client)
    foreign_pos = _create_position(other_client, "foreign")
    r = client.post(f"/members/{m['id']}/positions", json={"position_id": foreign_pos["id"]})
    assert r.status_code == 404


def test_assign_to_member_wrong_tenant(client: TestClient, other_client: TestClient) -> None:
    outsider = _create_member(other_client)
    pos = _create_position(client)
    r = client.post(f"/members/{outsider['id']}/positions", json={"position_id": pos["id"]})
    assert r.status_code == 404


def test_tenant_isolation(client: TestClient, other_client: TestClient) -> None:
    m = _create_member(client)
    pos = _create_position(client)
    _assign(client, m["id"], pos["id"])
    assert other_client.get(f"/members/{m['id']}/positions").status_code == 404


def test_cannot_delete_default_member_assignment(client: TestClient) -> None:
    m = _create_member(client)
    positions = client.get(f"/members/{m['id']}/positions").json()
    assert len(positions) == 1
    default_assignment_id = positions[0]["id"]

    resp = client.delete(f"/members/{m['id']}/positions/{default_assignment_id}")
    assert resp.status_code == 409
    assert resp.json()["detail"] == "Default positions cannot be deleted"


# ---------------------------------------------------------------------------
# GH-175 Finding 1 — privileged-position guardrail + last-admin guard
# ---------------------------------------------------------------------------


def _admin_position_id(db: Session) -> uuid.UUID:
    pos = db.scalar(
        select(Position).where(Position.tenant_id == TENANT_A, Position.slug == "administrator")
    )
    assert pos is not None
    return pos.id


def _make_role_assign_holder(db: Session, email: str = "chair@test.com") -> tuple[User, Member]:
    """A Membership-Chair-style member: holds role:assign but is *not* an admin."""
    role = _make_functional_role(db, TENANT_A, f"member-admins-{email}")
    _grant(db, TENANT_A, role, Permission.ROLE_ASSIGN)
    _grant(db, TENANT_A, role, Permission.MEMBER_READ)
    chair_pos = _make_position(db, TENANT_A, f"membership-chair-{email}")
    _map(db, TENANT_A, chair_pos, role)
    user = _make_user(db, uuid.uuid4(), email)
    member = _make_member(db, TENANT_A, user.id)
    _assign_db(db, TENANT_A, member, chair_pos)
    return user, member


def test_role_assign_holder_cannot_self_assign_admin_position(db_session: Session) -> None:
    """The proven exploit: a Membership Chair must not be able to become Administrator."""
    _seed_admin(db_session, TENANT_A)
    admin_pos_id = _admin_position_id(db_session)
    user, member = _make_role_assign_holder(db_session)
    db_session.commit()

    with _client_for(db_session, user, TENANT_A) as c:
        r = c.post(f"/members/{member.id}/positions", json={"position_id": str(admin_pos_id)})
    assert r.status_code == 403
    assert "administrators" in r.json()["detail"].lower()


def test_role_assign_holder_cannot_assign_admin_position_to_other(db_session: Session) -> None:
    _seed_admin(db_session, TENANT_A)
    admin_pos_id = _admin_position_id(db_session)
    user, _ = _make_role_assign_holder(db_session)
    target = _make_member(db_session, TENANT_A, _make_user(db_session, uuid.uuid4(), "t@t.com").id)
    db_session.commit()

    with _client_for(db_session, user, TENANT_A) as c:
        r = c.post(f"/members/{target.id}/positions", json={"position_id": str(admin_pos_id)})
    assert r.status_code == 403


def test_role_assign_holder_cannot_assign_role_manage_position(db_session: Session) -> None:
    """A custom non-admin position whose role grants role:manage is privileged too."""
    _seed_admin(db_session, TENANT_A)
    user, member = _make_role_assign_holder(db_session)
    governance_role = _make_functional_role(db_session, TENANT_A, "governance")
    _grant(db_session, TENANT_A, governance_role, Permission.ROLE_MANAGE)
    governance_pos = _make_position(db_session, TENANT_A, "governance-chair")
    _map(db_session, TENANT_A, governance_pos, governance_role)
    db_session.commit()

    with _client_for(db_session, user, TENANT_A) as c:
        r = c.post(f"/members/{member.id}/positions", json={"position_id": str(governance_pos.id)})
    assert r.status_code == 403


def test_role_assign_holder_can_assign_ordinary_position(db_session: Session) -> None:
    """No false positive: routine delegation (e.g. Treasurer) must keep working."""
    _seed_admin(db_session, TENANT_A)
    user, _ = _make_role_assign_holder(db_session)
    finance_role = _make_functional_role(db_session, TENANT_A, "finance-admins")
    _grant(db_session, TENANT_A, finance_role, Permission.FINANCE_READ)
    _grant(db_session, TENANT_A, finance_role, Permission.FINANCE_WRITE)
    treasurer = _make_position(db_session, TENANT_A, "treasurer")
    _map(db_session, TENANT_A, treasurer, finance_role)
    target = _make_member(db_session, TENANT_A, _make_user(db_session, uuid.uuid4(), "n@t.com").id)
    db_session.commit()

    with _client_for(db_session, user, TENANT_A) as c:
        r = c.post(f"/members/{target.id}/positions", json={"position_id": str(treasurer.id)})
    assert r.status_code == 201, r.text


def test_role_assign_holder_cannot_edit_or_delete_admin_term(db_session: Session) -> None:
    """A role:assign holder must not be able to end or delete an Administrator's term."""
    _seed_admin(db_session, TENANT_A)
    user, _ = _make_role_assign_holder(db_session)
    db_session.commit()
    admin_member_id = _ADMIN_MEMBER_IDS[TENANT_A]

    with _client_for(db_session, user, TENANT_A) as c:
        terms = c.get(f"/members/{admin_member_id}/positions").json()
        admin_term_id = terms[0]["id"]
        r_patch = c.patch(
            f"/members/{admin_member_id}/positions/{admin_term_id}",
            json={"end_date": "2020-01-01"},
        )
        r_delete = c.delete(f"/members/{admin_member_id}/positions/{admin_term_id}")
    assert r_patch.status_code == 403
    assert r_delete.status_code == 403


def test_admin_can_assign_admin_position(client: TestClient, db_session: Session) -> None:
    m = _create_member(client)
    admin_pos_id = _admin_position_id(db_session)
    r = client.post(f"/members/{m['id']}/positions", json={"position_id": str(admin_pos_id)})
    assert r.status_code == 201, r.text


def test_cannot_end_or_delete_last_admin_term(client: TestClient, db_session: Session) -> None:
    """Ending or deleting the tenant's only Administrator term returns 409."""
    admin_member_id = _ADMIN_MEMBER_IDS[TENANT_A]
    terms = client.get(f"/members/{admin_member_id}/positions").json()
    admin_term_id = terms[0]["id"]

    r_patch = client.patch(
        f"/members/{admin_member_id}/positions/{admin_term_id}", json={"end_date": "2020-01-01"}
    )
    assert r_patch.status_code == 409
    assert "last administrator" in r_patch.json()["detail"]

    r_delete = client.delete(f"/members/{admin_member_id}/positions/{admin_term_id}")
    assert r_delete.status_code == 409
    assert "last administrator" in r_delete.json()["detail"]


def test_can_end_admin_term_when_second_admin_exists(
    client: TestClient, db_session: Session
) -> None:
    admin_member_id = _ADMIN_MEMBER_IDS[TENANT_A]
    admin_pos_id = _admin_position_id(db_session)

    # Promote a second admin, then ending the first admin's term is allowed.
    second = _create_member(client, "Second")
    r = client.post(f"/members/{second['id']}/positions", json={"position_id": str(admin_pos_id)})
    assert r.status_code == 201

    terms = client.get(f"/members/{admin_member_id}/positions").json()
    admin_term_id = terms[0]["id"]
    r_patch = client.patch(
        f"/members/{admin_member_id}/positions/{admin_term_id}", json={"end_date": "2020-01-01"}
    )
    assert r_patch.status_code == 200
    assert r_patch.json()["is_current"] is False
