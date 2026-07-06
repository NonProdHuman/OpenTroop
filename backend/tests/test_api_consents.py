"""Consent ledger (#223): record, list, revoke."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import MemberType
from app.models.member import Member
from tests.conftest import TENANT_A


def _member(db: Session, first: str) -> Member:
    m = Member(tenant_id=TENANT_A, first_name=first, last_name="C", member_type=MemberType.SCOUT)
    db.add(m)
    db.commit()
    return m


def test_record_and_list_consent(client: TestClient, db_session: Session) -> None:
    scout = _member(db_session, "Kid")
    r = client.post(
        "/consents",
        json={
            "subject_member_id": str(scout.id),
            "scope": "account",
            "method": "parent_portal",
            "policy_version": "2026-04-22",
        },
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["scope"] == "account"
    assert body["method"] == "parent_portal"
    assert body["policy_version"] == "2026-04-22"
    assert body["revoked_at"] is None
    assert body["granted_at"] is not None
    assert body["consented_by_user_id"] is not None  # the acting admin, for audit

    listed = client.get("/consents", params={"subject_member_id": str(scout.id)}).json()
    assert len(listed) == 1
    # scope filter narrows
    assert client.get("/consents", params={"scope": "sms"}).json() == []
    assert len(client.get("/consents", params={"scope": "account"}).json()) == 1


def test_record_consent_rejects_unknown_member(client: TestClient) -> None:
    r = client.post("/consents", json={"subject_member_id": str(uuid.uuid4()), "scope": "tos"})
    assert r.status_code == 422  # subject_member_id not in this tenant


def test_revoke_consent_is_idempotent(client: TestClient, db_session: Session) -> None:
    adult = _member(db_session, "Adult")
    created = client.post(
        "/consents",
        json={"subject_member_id": str(adult.id), "scope": "tos", "method": "self"},
    ).json()
    assert created["method"] == "self"

    r = client.post(f"/consents/{created['id']}/revoke")
    assert r.status_code == 200
    first_ts = r.json()["revoked_at"]
    assert first_ts is not None

    # A second revoke keeps the original timestamp (idempotent).
    again = client.post(f"/consents/{created['id']}/revoke").json()
    assert again["revoked_at"] == first_ts
