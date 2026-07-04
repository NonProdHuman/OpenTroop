"""Advancement workflow API (GH-92 Phase 2): modes, workflow, elections, authz."""

import uuid
from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import (
    AdvancementMode,
    CompletionStatus,
    Member,
    MemberRelationship,
    MemberType,
    MeritBadge,
    Rank,
    RankCode,
    RecordedVia,
    RelationshipType,
    Requirement,
    RequirementSet,
    Tenant,
)
from tests.conftest import NEW_USER_ID, TENANT_A

DATE = date(2026, 6, 1)


class _Catalog:
    def __init__(self, db: Session) -> None:
        self.rank = Rank(code=RankCode.TENDERFOOT, name="Tenderfoot", sort_order=2)
        db.add(self.rank)
        db.flush()
        self.set_2025 = RequirementSet(
            rank_id=self.rank.id, version="2025", effective_date=date(2025, 1, 1)
        )
        self.set_2026 = RequirementSet(
            rank_id=self.rank.id, version="2026", effective_date=date(2026, 1, 1)
        )
        db.add_all([self.set_2025, self.set_2026])
        db.flush()
        # 2025: container 1 with leaf 1a (stable key), plus leaf 7b (key dropped in 2026).
        self.container = Requirement(
            requirement_set_id=self.set_2025.id,
            number="1",
            letter="",
            text="Do the following:",
            sort_order=0,
        )
        db.add(self.container)
        db.flush()
        self.req_1a = Requirement(
            requirement_set_id=self.set_2025.id,
            number="1",
            letter="a",
            parent_id=self.container.id,
            text="Sleep in a tent you helped pitch.",
            stable_key="tenderfoot.campout",
            sort_order=1,
        )
        self.req_7b = Requirement(
            requirement_set_id=self.set_2025.id,
            number="7",
            letter="b",
            text="One hour of service.",
            stable_key="tenderfoot.service-old",
            sort_order=2,
        )
        # 2026: the campout requirement renumbered to 2a; service requirement replaced.
        self.req_2a_v2026 = Requirement(
            requirement_set_id=self.set_2026.id,
            number="2",
            letter="a",
            text="Sleep in a tent that you helped pitch.",
            stable_key="tenderfoot.campout",
            sort_order=0,
        )
        self.req_9_v2026 = Requirement(
            requirement_set_id=self.set_2026.id,
            number="9",
            letter="",
            text="A brand-new requirement.",
            stable_key="tenderfoot.new",
            sort_order=1,
        )
        self.badge = MeritBadge(name="Camping", eagle_required=True)
        db.add_all([self.req_1a, self.req_7b, self.req_2a_v2026, self.req_9_v2026, self.badge])
        db.flush()


def _scout(db: Session, first: str = "Sam", user_id: uuid.UUID | None = None) -> Member:
    member = Member(
        tenant_id=TENANT_A,
        first_name=first,
        last_name="Scout",
        member_type=MemberType.SCOUT,
        user_id=user_id,
    )
    db.add(member)
    db.flush()
    return member


def _set_mode(db: Session, mode: AdvancementMode) -> None:
    tenant = db.get(Tenant, TENANT_A)
    if tenant is None:
        tenant = Tenant(id=TENANT_A, name="Troop A", slug="troopa", advancement_mode=mode)
        db.add(tenant)
    else:
        tenant.advancement_mode = mode
    db.flush()


# ---------------------------------------------------------------------------
# Catalog endpoints
# ---------------------------------------------------------------------------


def test_catalog_endpoints(client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    r = client.get("/advancement/ranks")
    assert r.status_code == 200
    ranks = r.json()
    assert len(ranks) == 1
    assert ranks[0]["code"] == "tenderfoot"
    assert [s["version"] for s in ranks[0]["requirement_sets"]] == ["2026", "2025"]

    r = client.get(f"/advancement/requirement-sets/{cat.set_2025.id}")
    assert r.status_code == 200
    labels = [req["label"] for req in r.json()["requirements"]]
    assert labels == ["1", "1a", "7b"]

    r = client.get("/merit-badges")
    assert r.status_code == 200
    assert [b["name"] for b in r.json()] == ["Camping"]


def test_disabled_mode_hides_surface(client: TestClient, db_session: Session) -> None:
    _Catalog(db_session)
    _set_mode(db_session, AdvancementMode.DISABLED)
    assert client.get("/advancement/ranks").status_code == 404
    assert client.get("/merit-badges").status_code == 404


# ---------------------------------------------------------------------------
# Chair entry (default mode)
# ---------------------------------------------------------------------------


def test_chair_entry_born_approved(client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    r = client.post(
        f"/members/{scout.id}/advancement/completions",
        json={"requirement_id": str(cat.req_1a.id), "date_completed": DATE.isoformat()},
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "approved"
    assert body["recorded_via"] == "manual"
    assert body["approved_by_id"] is not None

    # First completion elected the requirement's set lazily.
    view = client.get(f"/members/{scout.id}/advancement").json()
    rank_view = view["ranks"][0]
    assert rank_view["progress"]["requirement_set_id"] == str(cat.set_2025.id)
    # 1a approved ⇒ leaf complete ⇒ container 1 complete; 7b outstanding.
    by_label = {rp["requirement"]["label"]: rp for rp in rank_view["requirements"]}
    assert by_label["1a"]["is_complete"] is True
    assert by_label["1"]["is_complete"] is True
    assert by_label["7b"]["is_complete"] is False
    assert rank_view["is_complete"] is False


def test_container_completion_rejected(client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    r = client.post(
        f"/members/{scout.id}/advancement/completions",
        json={"requirement_id": str(cat.container.id), "date_completed": DATE.isoformat()},
    )
    assert r.status_code == 422


def test_duplicate_conflict_and_rejected_rereport(client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    payload = {"requirement_id": str(cat.req_1a.id), "date_completed": DATE.isoformat()}
    first = client.post(f"/members/{scout.id}/advancement/completions", json=payload)
    assert first.status_code == 201
    assert (
        client.post(f"/members/{scout.id}/advancement/completions", json=payload).status_code == 409
    )

    # Reject, then re-report reuses the same row.
    completion_id = first.json()["id"]
    r = client.patch(f"/advancement/completions/{completion_id}", json={"status": "rejected"})
    assert r.status_code == 200 and r.json()["status"] == "rejected"
    again = client.post(f"/members/{scout.id}/advancement/completions", json=payload)
    assert again.status_code == 201
    assert again.json()["id"] == completion_id
    assert again.json()["status"] == "approved"  # admin holds advancement:record


def test_cross_set_completion_rejected(client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    client.post(
        f"/members/{scout.id}/advancement/completions",
        json={"requirement_id": str(cat.req_1a.id), "date_completed": DATE.isoformat()},
    )
    r = client.post(
        f"/members/{scout.id}/advancement/completions",
        json={"requirement_id": str(cat.req_2a_v2026.id), "date_completed": DATE.isoformat()},
    )
    assert r.status_code == 422
    assert "version" in r.json()["detail"]


def test_revoke_completion(client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    created = client.post(
        f"/members/{scout.id}/advancement/completions",
        json={"requirement_id": str(cat.req_1a.id), "date_completed": DATE.isoformat()},
    ).json()
    assert client.delete(f"/advancement/completions/{created['id']}").status_code == 204
    view = client.get(f"/members/{scout.id}/advancement").json()
    by_label = {rp["requirement"]["label"]: rp for rp in view["ranks"][0]["requirements"]}
    assert by_label["1a"]["completion"] is None
    assert by_label["1a"]["is_complete"] is False


# ---------------------------------------------------------------------------
# Scout self-report mode + approval queue
# ---------------------------------------------------------------------------


def _tenant_a_headers() -> dict[str, str]:
    return {"X-Tenant-ID": str(TENANT_A)}


def test_self_report_and_approval_flow(
    client: TestClient, claim_client: TestClient, db_session: Session
) -> None:
    cat = _Catalog(db_session)
    _set_mode(db_session, AdvancementMode.SCOUT_REPORTED)
    scout = _scout(db_session, user_id=NEW_USER_ID)

    r = claim_client.post(
        f"/members/{scout.id}/advancement/completions",
        json={"requirement_id": str(cat.req_1a.id), "date_completed": DATE.isoformat()},
        headers=_tenant_a_headers(),
    )
    assert r.status_code == 201, r.text
    body = r.json()
    assert body["status"] == "reported"
    assert body["approved_by_id"] is None

    # The scout cannot approve their own report.
    r = claim_client.patch(
        f"/advancement/completions/{body['id']}",
        json={"status": "approved"},
        headers=_tenant_a_headers(),
    )
    assert r.status_code == 403

    # It shows in the chair's queue; approval stamps the approver.
    queue = client.get("/advancement/queue").json()
    assert [c["id"] for c in queue["completions"]] == [body["id"]]
    approved = client.patch(
        f"/advancement/completions/{body['id']}", json={"status": "approved"}
    ).json()
    assert approved["status"] == "approved"
    assert approved["approved_by_id"] is not None
    assert client.get("/advancement/queue").json()["completions"] == []


def test_parent_may_report_for_child(
    client: TestClient, claim_client: TestClient, db_session: Session
) -> None:
    cat = _Catalog(db_session)
    _set_mode(db_session, AdvancementMode.SCOUT_REPORTED)
    child = _scout(db_session, first="Kid")
    parent = Member(
        tenant_id=TENANT_A,
        first_name="Pat",
        last_name="Parent",
        member_type=MemberType.ADULT,
        user_id=NEW_USER_ID,
    )
    db_session.add(parent)
    db_session.flush()
    db_session.add(
        MemberRelationship(
            tenant_id=TENANT_A,
            from_member_id=parent.id,
            to_member_id=child.id,
            relationship_type=RelationshipType.PARENT_OF,
        )
    )
    db_session.flush()

    r = claim_client.post(
        f"/members/{child.id}/advancement/completions",
        json={"requirement_id": str(cat.req_1a.id), "date_completed": DATE.isoformat()},
        headers=_tenant_a_headers(),
    )
    assert r.status_code == 201
    assert r.json()["status"] == "reported"


def test_self_report_blocked_outside_mode(claim_client: TestClient, db_session: Session) -> None:
    """Default mode is chair_entry — a permissionless member cannot self-report."""
    cat = _Catalog(db_session)
    scout = _scout(db_session, user_id=NEW_USER_ID)
    r = claim_client.post(
        f"/members/{scout.id}/advancement/completions",
        json={"requirement_id": str(cat.req_1a.id), "date_completed": DATE.isoformat()},
        headers=_tenant_a_headers(),
    )
    assert r.status_code == 403


def test_self_report_only_for_self_or_ward(claim_client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    _set_mode(db_session, AdvancementMode.SCOUT_REPORTED)
    _scout(db_session, user_id=NEW_USER_ID)
    other = _scout(db_session, first="Other")
    r = claim_client.post(
        f"/members/{other.id}/advancement/completions",
        json={"requirement_id": str(cat.req_1a.id), "date_completed": DATE.isoformat()},
        headers=_tenant_a_headers(),
    )
    assert r.status_code == 403


def test_view_authz(client: TestClient, claim_client: TestClient, db_session: Session) -> None:
    _Catalog(db_session)
    me = _scout(db_session, user_id=NEW_USER_ID)
    other = _scout(db_session, first="Other")
    headers = _tenant_a_headers()
    assert claim_client.get(f"/members/{me.id}/advancement", headers=headers).status_code == 200
    assert claim_client.get(f"/members/{other.id}/advancement", headers=headers).status_code == 403
    # advancement:read (admin) sees anyone.
    assert client.get(f"/members/{other.id}/advancement").status_code == 200


# ---------------------------------------------------------------------------
# Version election + remap
# ---------------------------------------------------------------------------


def test_election_switch_remaps_by_stable_key(client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    for req in (cat.req_1a, cat.req_7b):
        assert (
            client.post(
                f"/members/{scout.id}/advancement/completions",
                json={"requirement_id": str(req.id), "date_completed": DATE.isoformat()},
            ).status_code
            == 201
        )

    r = client.put(
        f"/members/{scout.id}/advancement/ranks/{cat.rank.id}/election",
        json={"requirement_set_id": str(cat.set_2026.id)},
    )
    assert r.status_code == 200, r.text
    result = r.json()
    assert result["progress"]["requirement_set_id"] == str(cat.set_2026.id)
    assert result["remapped"] == 1  # campout key exists in 2026 (renumbered to 2a)
    assert result["unmatched"] == ["7b"]  # service requirement has no counterpart

    view = client.get(f"/members/{scout.id}/advancement").json()
    by_label = {rp["requirement"]["label"]: rp for rp in view["ranks"][0]["requirements"]}
    assert by_label["2a"]["completion"]["recorded_via"] == RecordedVia.REMAP.value
    assert by_label["2a"]["completion"]["status"] == CompletionStatus.APPROVED.value
    assert by_label["9"]["is_complete"] is False

    # Switching back does not duplicate: the original 2025 rows still exist.
    r = client.put(
        f"/members/{scout.id}/advancement/ranks/{cat.rank.id}/election",
        json={"requirement_set_id": str(cat.set_2025.id)},
    )
    assert r.status_code == 200
    assert r.json()["skipped_existing"] == 1  # 1a already has its original row
    assert r.json()["remapped"] == 0


def test_election_rejects_foreign_set(client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    other_rank = Rank(code=RankCode.STAR, name="Star", sort_order=5)
    db_session.add(other_rank)
    db_session.flush()
    other_set = RequirementSet(rank_id=other_rank.id, version="2025")
    db_session.add(other_set)
    db_session.flush()
    scout = _scout(db_session)
    r = client.put(
        f"/members/{scout.id}/advancement/ranks/{cat.rank.id}/election",
        json={"requirement_set_id": str(other_set.id)},
    )
    assert r.status_code == 422


def test_rank_dates(client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    r = client.patch(
        f"/members/{scout.id}/advancement/ranks/{cat.rank.id}",
        json={"completed_date": "2026-05-01", "awarded_date": "2026-06-15"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["completed_date"] == "2026-05-01"
    assert body["awarded_date"] == "2026-06-15"


# ---------------------------------------------------------------------------
# Merit badges
# ---------------------------------------------------------------------------


def test_merit_badge_lifecycle(client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    payload = {"merit_badge_id": str(cat.badge.id), "date_completed": DATE.isoformat()}
    created = client.post(f"/members/{scout.id}/merit-badges", json=payload)
    assert created.status_code == 201
    assert created.json()["status"] == "approved"

    assert client.post(f"/members/{scout.id}/merit-badges", json=payload).status_code == 409

    record_id = created.json()["id"]
    updated = client.patch(
        f"/advancement/merit-badges/{record_id}", json={"counselor_name": "Jane Counselor"}
    )
    assert updated.status_code == 200
    assert updated.json()["counselor_name"] == "Jane Counselor"

    assert client.delete(f"/advancement/merit-badges/{record_id}").status_code == 204
    # Revocation frees the slot for a fresh record.
    again = client.post(f"/members/{scout.id}/merit-badges", json=payload)
    assert again.status_code == 201
    assert again.json()["id"] != record_id


# ---------------------------------------------------------------------------
# Tenant settings exposure
# ---------------------------------------------------------------------------


def test_settings_expose_advancement_mode(client: TestClient, db_session: Session) -> None:
    _set_mode(db_session, AdvancementMode.CHAIR_ENTRY)
    r = client.get("/tenant/settings")
    assert r.status_code == 200
    assert r.json()["advancement_mode"] == "chair_entry"

    r = client.patch("/tenant/settings", json={"advancement_mode": "scout_reported"})
    assert r.status_code == 200
    assert r.json()["advancement_mode"] == "scout_reported"
