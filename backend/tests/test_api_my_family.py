"""``GET /members/me/family`` — the "My Family" household view (GH-143).

Any authenticated member may call it (no extra permission); the response is
``{self} ∪ children/wards ∪ co-parents`` (``family_member_ids``) plus the
relationship edges among that household. The medical bundle is intentionally
intact — the household is exactly the ``redact_medical`` exemption, so a
positionless parent sees their own child's allergies.
"""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models.enums import MemberType, RelationshipType
from app.models.member import Member, MemberRelationship
from tests.conftest import NEW_USER_ID, TENANT_A, TENANT_B


def _member(db: Session, first: str, tenant_id: uuid.UUID = TENANT_A, **kw: object) -> Member:
    kw.setdefault("member_type", MemberType.SCOUT)
    member = Member(tenant_id=tenant_id, first_name=first, last_name="Test", **kw)
    db.add(member)
    db.commit()
    return member


def _rel(
    db: Session,
    frm: Member,
    to: Member,
    rtype: RelationshipType = RelationshipType.PARENT_OF,
    tenant_id: uuid.UUID = TENANT_A,
) -> None:
    db.add(
        MemberRelationship(
            tenant_id=tenant_id,
            from_member_id=frm.id,
            to_member_id=to.id,
            relationship_type=rtype,
        )
    )
    db.commit()


def _caller(db: Session, tenant_id: uuid.UUID = TENANT_A, **kw: object) -> Member:
    """A positionless member linked to NEW_USER_ID — no roles, no permissions."""
    return _member(
        db, "Caller", tenant_id=tenant_id, member_type=MemberType.ADULT, user_id=NEW_USER_ID, **kw
    )


def _client(tenant_id: uuid.UUID = TENANT_A) -> TestClient:
    return TestClient(
        app, headers={"X-Tenant-ID": str(tenant_id), "X-Test-User-ID": str(NEW_USER_ID)}
    )


def _ids(payload: dict) -> set[str]:
    return {m["id"] for m in payload["members"]}


def test_parent_sees_self_children_and_coparent(client: TestClient, db_session: Session) -> None:
    parent = _caller(db_session)
    child = _member(db_session, "Child")
    coparent = _member(db_session, "CoParent", member_type=MemberType.ADULT)
    _rel(db_session, parent, child)
    _rel(db_session, coparent, child)

    resp = _client().get("/members/me/family")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert _ids(body) == {str(parent.id), str(child.id), str(coparent.id)}


def test_scout_sees_only_self(client: TestClient, db_session: Session) -> None:
    scout = _member(db_session, "SoloScout", user_id=NEW_USER_ID)
    resp = _client().get("/members/me/family")
    assert resp.status_code == 200, resp.text
    assert _ids(resp.json()) == {str(scout.id)}


def test_adult_no_edges_sees_only_self(client: TestClient, db_session: Session) -> None:
    adult = _caller(db_session)
    resp = _client().get("/members/me/family")
    assert resp.status_code == 200, resp.text
    assert _ids(resp.json()) == {str(adult.id)}


def test_relationship_payload_scoped_to_household(client: TestClient, db_session: Session) -> None:
    parent = _caller(db_session)
    child = _member(db_session, "Child")
    _rel(db_session, parent, child)

    body = _client().get("/members/me/family").json()
    edges = body["relationships"]
    assert len(edges) == 1
    edge = edges[0]
    assert edge["from_member_id"] == str(parent.id)
    assert edge["to_member_id"] == str(child.id)
    assert edge["relationship_type"] == RelationshipType.PARENT_OF.value


def test_tenant_isolation(client: TestClient, db_session: Session) -> None:
    # Same user linked to a member in TENANT_B with a child there — must not leak.
    parent_b = _member(
        db_session, "ParentB", tenant_id=TENANT_B, member_type=MemberType.ADULT, user_id=NEW_USER_ID
    )
    child_b = _member(db_session, "ChildB", tenant_id=TENANT_B)
    _rel(db_session, parent_b, child_b, tenant_id=TENANT_B)

    # Caller in TENANT_A (same user) with their own separate household.
    parent_a = _caller(db_session)
    child_a = _member(db_session, "ChildA")
    _rel(db_session, parent_a, child_a)

    body = _client(TENANT_A).get("/members/me/family").json()
    assert _ids(body) == {str(parent_a.id), str(child_a.id)}


def test_positionless_parent_sees_child_medical(client: TestClient, db_session: Session) -> None:
    """The household is the ``redact_medical`` exemption — a parent with no
    position (thus no ``member:read_medical``) still sees their child's
    allergies and medical-form dates on this endpoint."""
    parent = _caller(db_session)
    child = _member(db_session, "Child", allergies="peanuts", dietary_restrictions="vegetarian")
    _rel(db_session, parent, child)

    body = _client().get("/members/me/family").json()
    child_row = next(m for m in body["members"] if m["id"] == str(child.id))
    assert child_row["allergies"] == "peanuts"
    assert child_row["dietary_restrictions"] == "vegetarian"


def test_requires_authenticated_member(client: TestClient, db_session: Session) -> None:
    # NEW_USER_ID has no Member row in TENANT_A → 403.
    resp = _client().get("/members/me/family")
    assert resp.status_code == 403
