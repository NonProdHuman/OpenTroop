"""The medical bundle requires ``member:read_medical`` (GH-122 §2).

Every read path that serves ``MemberRead`` — the roster list, the member
detail, resolved group membership, and ``/sync/members`` — must null the
medical fields (allergies, dietary restrictions, medical-form dates,
emergency contacts) for callers holding only ``member:read``. The caller's
own household is exempt: a family always sees the fields it can already
edit interactively (the PATCH allowlist).
"""

import datetime
import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.core.member_privacy import MEDICAL_FIELDS
from app.main import app
from app.models.enums import MemberType, Permission, PositionScope, RelationshipType
from app.models.member import Member, MemberRelationship
from app.models.rbac import (
    FunctionalRole,
    FunctionalRolePermission,
    MemberPositionAssignment,
    Position,
    PositionFunctionalRole,
)
from tests.conftest import NEW_USER_ID, TENANT_A

MEDICAL_VALUES: dict[str, object] = {
    "medical_form_ab_date": datetime.date(2026, 1, 1),
    "medical_form_c_date": datetime.date(2026, 2, 1),
    "allergies": "peanuts",
    "dietary_restrictions": "vegetarian",
    "emergency_contact_1_name": "Alex Contact",
    "emergency_contact_1_phone": "555-0101",
    "emergency_contact_2_name": "Bo Contact",
    "emergency_contact_2_phone": "555-0102",
}


def _member_with_medical(db: Session, first: str, **kw: object) -> Member:
    member = Member(
        tenant_id=TENANT_A,
        first_name=first,
        last_name="Test",
        member_type=MemberType.SCOUT,
        **MEDICAL_VALUES,
        **kw,
    )
    db.add(member)
    db.commit()
    return member


def _roster_reader(db: Session) -> tuple[Member, TestClient]:
    """A member holding member:read + event:read (the baseline bundle) but
    not member:read_medical, authenticated as NEW_USER_ID in TENANT_A."""
    reader = Member(
        tenant_id=TENANT_A,
        user_id=NEW_USER_ID,
        first_name="Reader",
        last_name="Adult",
        member_type=MemberType.ADULT,
        allergies="shellfish",  # own row must never be redacted
    )
    db.add(reader)
    db.flush()
    role = FunctionalRole(tenant_id=TENANT_A, name="Members", slug="members")
    db.add(role)
    db.flush()
    for perm in (Permission.MEMBER_READ, Permission.EVENT_READ):
        db.add(
            FunctionalRolePermission(
                tenant_id=TENANT_A, functional_role_id=role.id, permission=perm
            )
        )
    position = Position(
        tenant_id=TENANT_A,
        name="Roster Reader",
        slug="roster-reader",
        applies_to=PositionScope.ANY,
    )
    db.add(position)
    db.flush()
    db.add(
        PositionFunctionalRole(
            tenant_id=TENANT_A, position_id=position.id, functional_role_id=role.id
        )
    )
    db.add(
        MemberPositionAssignment(tenant_id=TENANT_A, member_id=reader.id, position_id=position.id)
    )
    db.commit()
    return reader, TestClient(
        app, headers={"X-Tenant-ID": str(TENANT_A), "X-Test-User-ID": str(NEW_USER_ID)}
    )


def _row(items: list[dict], member_id: uuid.UUID) -> dict:
    matches = [item for item in items if item["id"] == str(member_id)]
    assert matches, f"member {member_id} missing from response"
    return matches[0]


def _assert_redacted(row: dict) -> None:
    for field in MEDICAL_FIELDS:
        assert row[field] is None, f"{field} leaked: {row[field]!r}"


def _assert_present(row: dict) -> None:
    for field in MEDICAL_FIELDS:
        assert row[field] is not None, f"{field} unexpectedly redacted"


def test_roster_list_redacts_medical_without_read_medical(
    client: TestClient, db_session: Session
) -> None:
    scout = _member_with_medical(db_session, "Stranger")
    reader, reader_client = _roster_reader(db_session)

    items = reader_client.get("/members").json()
    _assert_redacted(_row(items, scout.id))
    # Non-medical fields still serve the roster.
    assert _row(items, scout.id)["first_name"] == "Stranger"
    # The caller's own row is exempt.
    assert _row(items, reader.id)["allergies"] == "shellfish"


def test_member_detail_redacts_medical_without_read_medical(
    client: TestClient, db_session: Session
) -> None:
    scout = _member_with_medical(db_session, "Stranger")
    _, reader_client = _roster_reader(db_session)

    row = reader_client.get(f"/members/{scout.id}").json()
    _assert_redacted(row)


def test_family_rows_keep_medical(client: TestClient, db_session: Session) -> None:
    reader, reader_client = _roster_reader(db_session)
    child = _member_with_medical(db_session, "Ward")
    db_session.add(
        MemberRelationship(
            tenant_id=TENANT_A,
            from_member_id=reader.id,
            to_member_id=child.id,
            relationship_type=RelationshipType.PARENT_OF,
        )
    )
    db_session.commit()

    items = reader_client.get("/members").json()
    _assert_present(_row(items, child.id))
    detail = reader_client.get(f"/members/{child.id}").json()
    _assert_present(detail)


def test_sync_members_redacts_medical_without_read_medical(
    client: TestClient, db_session: Session
) -> None:
    scout = _member_with_medical(db_session, "Stranger")
    reader, reader_client = _roster_reader(db_session)
    child = _member_with_medical(db_session, "Ward")
    db_session.add(
        MemberRelationship(
            tenant_id=TENANT_A,
            from_member_id=reader.id,
            to_member_id=child.id,
            relationship_type=RelationshipType.PARENT_OF,
        )
    )
    db_session.commit()

    page = reader_client.get("/sync/members", params={"since_seq": 0}).json()
    _assert_redacted(_row(page["items"], scout.id))
    _assert_present(_row(page["items"], child.id))


def test_group_members_redacts_medical_without_read_medical(
    client: TestClient, db_session: Session
) -> None:
    scout = _member_with_medical(db_session, "Stranger")
    _, reader_client = _roster_reader(db_session)
    group = client.post("/groups/", json={"name": "Redaction Patrol"}).json()
    added = client.post(f"/groups/{group['id']}/members", json={"member_id": str(scout.id)})
    assert added.status_code == 201, added.text

    items = reader_client.get(f"/groups/{group['id']}/members").json()
    _assert_redacted(_row(items, scout.id))


def test_read_medical_holders_see_everything(client: TestClient, db_session: Session) -> None:
    # The admin fixture short-circuits to all permissions (is_admin role).
    scout = _member_with_medical(db_session, "Stranger")
    items = client.get("/members").json()
    _assert_present(_row(items, scout.id))
    page = client.get("/sync/members", params={"since_seq": 0}).json()
    _assert_present(_row(page["items"], scout.id))
