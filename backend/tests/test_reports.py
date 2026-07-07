"""Report catalog + rendering endpoints (#147).

Covers catalog visibility (runnable flag), per-report rows/filters, the medical
report's extra permission gate, roster redaction parity with ``/members``, CSV
escaping, group-filter resolution, and advancement percentages consistent with
the member progress endpoint.
"""

import csv
import io
import uuid
from collections.abc import Iterable
from datetime import date, timedelta

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.main import app
from app.models import (
    AdvancementMode,
    Group,
    GroupMember,
    GroupType,
    Member,
    MemberRelationship,
    MemberType,
    Rank,
    RankCode,
    Requirement,
    RequirementSet,
    Tenant,
)
from app.models.enums import Permission, PositionScope, RelationshipType
from app.models.member import MemberStatus
from app.models.rbac import (
    FunctionalRole,
    FunctionalRolePermission,
    MemberPositionAssignment,
    Position,
    PositionFunctionalRole,
)
from tests.conftest import NEW_USER_ID, TENANT_A

TODAY = date.today()


def _reader(db: Session, permissions: Iterable[Permission]) -> tuple[Member, TestClient]:
    """A member holding exactly *permissions*, authenticated as NEW_USER_ID."""
    reader = Member(
        tenant_id=TENANT_A,
        user_id=NEW_USER_ID,
        first_name="Reader",
        last_name="Adult",
        member_type=MemberType.ADULT,
    )
    db.add(reader)
    db.flush()
    role = FunctionalRole(tenant_id=TENANT_A, name="Reporters", slug="reporters")
    db.add(role)
    db.flush()
    for perm in permissions:
        db.add(
            FunctionalRolePermission(
                tenant_id=TENANT_A, functional_role_id=role.id, permission=perm
            )
        )
    position = Position(
        tenant_id=TENANT_A, name="Reporter", slug="reporter", applies_to=PositionScope.ANY
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


def _scout(db: Session, first: str = "Sam", last: str = "Scout", **kw: object) -> Member:
    member = Member(
        tenant_id=TENANT_A,
        first_name=first,
        last_name=last,
        member_type=MemberType.SCOUT,
        **kw,
    )
    db.add(member)
    db.commit()
    return member


def _rows(resp_json: dict) -> list[dict]:
    return resp_json["rows"]


def _by_name(rows: list[dict], name: str) -> dict:
    match = [r for r in rows if r["name"] == name]
    assert match, f"{name} not in rows"
    return match[0]


# ---------------------------------------------------------------------------
# Catalog
# ---------------------------------------------------------------------------


def test_catalog_admin_sees_all_runnable(client: TestClient) -> None:
    entries = client.get("/reports").json()
    keys = {e["key"]: e for e in entries}
    assert set(keys) == {"roster", "swim", "medical", "advancement"}
    assert all(e["runnable"] for e in entries)


def test_catalog_reflects_caller_permissions(client: TestClient, db_session: Session) -> None:
    _, reader_client = _reader(db_session, [Permission.REPORT_READ])
    entries = reader_client.get("/reports").json()
    by_key = {e["key"]: e for e in entries}
    assert by_key["roster"]["runnable"] is True
    assert by_key["swim"]["runnable"] is True
    assert by_key["advancement"]["runnable"] is True
    # No member:read_medical → the medical report is advertised but not runnable.
    assert by_key["medical"]["runnable"] is False


def test_reports_require_report_read(client: TestClient, db_session: Session) -> None:
    _, reader_client = _reader(db_session, [Permission.MEMBER_READ])  # no report:read
    assert reader_client.get("/reports").status_code == 403
    assert reader_client.get("/reports/roster").status_code == 403


# ---------------------------------------------------------------------------
# Roster
# ---------------------------------------------------------------------------


def test_roster_rows_and_type_filter(client: TestClient, db_session: Session) -> None:
    _scout(db_session, "Sammy", "Scout")
    db_session.add(
        Member(
            tenant_id=TENANT_A, first_name="Adam", last_name="Adult", member_type=MemberType.ADULT
        )
    )
    db_session.commit()

    rows = _rows(client.get("/reports/roster").json())
    names = {r["name"] for r in rows}
    assert "Scout, Sammy" in names
    assert "Adult, Adam" in names

    scouts_only = _rows(client.get("/reports/roster", params={"member_type": "scout"}).json())
    assert {r["name"] for r in scouts_only} == {"Scout, Sammy"}


def test_roster_status_filter_defaults_active(client: TestClient, db_session: Session) -> None:
    _scout(db_session, "Active", "One")
    _scout(db_session, "Alum", "Two", membership_status=MemberStatus.ALUMNI)
    db_session.commit()

    default_rows = _rows(client.get("/reports/roster").json())
    assert "One, Active" in {r["name"] for r in default_rows}
    assert "Two, Alum" not in {r["name"] for r in default_rows}

    any_rows = _rows(client.get("/reports/roster", params={"status": "any"}).json())
    assert "Two, Alum" in {r["name"] for r in any_rows}


def test_roster_group_filter_uses_resolution(client: TestClient, db_session: Session) -> None:
    in_group = _scout(db_session, "In", "Group")
    _scout(db_session, "Out", "Group")
    group = Group(tenant_id=TENANT_A, name="Patrol", group_type=GroupType.PATROL)
    db_session.add(group)
    db_session.flush()
    db_session.add(GroupMember(tenant_id=TENANT_A, group_id=group.id, member_id=in_group.id))
    db_session.commit()

    rows = _rows(client.get("/reports/roster", params={"group_id": str(group.id)}).json())
    assert {r["name"] for r in rows} == {"Group, In"}


def test_roster_unknown_group_404(client: TestClient) -> None:
    resp = client.get("/reports/roster", params={"group_id": str(uuid.uuid4())})
    assert resp.status_code == 404


def test_roster_scout_lists_parents(client: TestClient, db_session: Session) -> None:
    scout = _scout(db_session, "Kid", "Jones")
    parent = Member(
        tenant_id=TENANT_A,
        first_name="Pat",
        last_name="Jones",
        member_type=MemberType.ADULT,
        phone="555-1000",
    )
    db_session.add(parent)
    db_session.flush()
    db_session.add(
        MemberRelationship(
            tenant_id=TENANT_A,
            from_member_id=parent.id,
            to_member_id=scout.id,
            relationship_type=RelationshipType.PARENT_OF,
        )
    )
    db_session.commit()

    row = _by_name(_rows(client.get("/reports/roster").json()), "Jones, Kid")
    assert "Pat Jones" in (row["parents"] or "")
    assert "555-1000" in (row["parents"] or "")


# ---------------------------------------------------------------------------
# Redaction parity
# ---------------------------------------------------------------------------


def test_roster_redacts_medical_without_read_medical(
    client: TestClient, db_session: Session
) -> None:
    _scout(
        db_session,
        "Stranger",
        "Scout",
        allergies="peanuts",
        dietary_restrictions="vegetarian",
        emergency_contact_1_name="Kin",
        emergency_contact_1_phone="555-9999",
    )
    reader, reader_client = _reader(db_session, [Permission.REPORT_READ, Permission.MEMBER_READ])

    row = _by_name(_rows(reader_client.get("/reports/roster").json()), "Scout, Stranger")
    assert row["allergies"] is None
    assert row["dietary_restrictions"] is None
    assert row["emergency_contact"] is None
    # Non-medical roster fields still serve.
    assert row["name"] == "Scout, Stranger"


def test_roster_medical_visible_to_read_medical_holder(
    client: TestClient, db_session: Session
) -> None:
    _scout(db_session, "Open", "Scout", allergies="peanuts")
    row = _by_name(_rows(client.get("/reports/roster").json()), "Scout, Open")
    assert row["allergies"] == "peanuts"


# ---------------------------------------------------------------------------
# Swim
# ---------------------------------------------------------------------------


def test_swim_stale_flag(client: TestClient, db_session: Session) -> None:
    _scout(db_session, "Fresh", "Swim", swim_date=TODAY - timedelta(days=30))
    _scout(db_session, "Old", "Swim", swim_date=TODAY - timedelta(days=800))
    _scout(db_session, "Never", "Swim")  # no swim_date
    db_session.commit()

    rows = _rows(client.get("/reports/swim").json())
    by = {r["name"]: r for r in rows}
    assert by["Swim, Fresh"]["stale"] is False
    assert by["Swim, Old"]["stale"] is True
    assert by["Swim, Never"]["stale"] is True


# ---------------------------------------------------------------------------
# Medical
# ---------------------------------------------------------------------------


def test_medical_report_403_without_read_medical(client: TestClient, db_session: Session) -> None:
    _, reader_client = _reader(db_session, [Permission.REPORT_READ, Permission.MEMBER_READ])
    assert reader_client.get("/reports/medical").status_code == 403


def test_medical_report_rows(client: TestClient, db_session: Session) -> None:
    fresh = TODAY - timedelta(days=10)  # ~355 days until expiry, outside the 90d horizon
    # Overdue AB form (expired 30 days ago); part C fresh.
    _scout(
        db_session,
        "Overdue",
        "Med",
        medical_form_ab_date=TODAY - timedelta(days=395),
        medical_form_c_date=fresh,
    )
    # Both parts fresh → outside horizon, excluded.
    _scout(db_session, "Fresh", "Med", medical_form_ab_date=fresh, medical_form_c_date=fresh)
    # Missing forms entirely → always needs attention.
    _scout(db_session, "Missing", "Med")
    db_session.commit()

    rows = _rows(client.get("/reports/medical").json())
    names = {r["name"] for r in rows}
    assert "Med, Overdue" in names
    assert "Med, Missing" in names
    assert "Med, Fresh" not in names  # both parts outside horizon
    overdue = _by_name(rows, "Med, Overdue")
    assert overdue["ab_days_until"] < 0


def test_medical_form_part_filter(client: TestClient, db_session: Session) -> None:
    # Fresh A/B, overdue C: the concern is only in part C.
    _scout(
        db_session,
        "CProblem",
        "Med",
        medical_form_ab_date=TODAY - timedelta(days=10),
        medical_form_c_date=TODAY - timedelta(days=400),
    )
    db_session.commit()
    # Restricting to A/B: the fresh A/B isn't a concern, so the member drops out.
    ab_rows = _rows(client.get("/reports/medical", params={"form_part": "ab"}).json())
    assert "Med, CProblem" not in {r["name"] for r in ab_rows}
    c_rows = _rows(client.get("/reports/medical", params={"form_part": "c"}).json())
    assert "Med, CProblem" in {r["name"] for r in c_rows}


# ---------------------------------------------------------------------------
# CSV
# ---------------------------------------------------------------------------


def test_csv_download_and_escaping(client: TestClient, db_session: Session) -> None:
    # Names carrying a comma, a double-quote, and a newline must round-trip.
    _scout(db_session, 'Bo"bby', "Smith,\nJones")
    db_session.commit()

    resp = client.get("/reports/roster", params={"format": "csv"})
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    assert "attachment" in resp.headers["content-disposition"]

    reader = csv.reader(io.StringIO(resp.text))
    parsed = list(reader)
    assert parsed[0][0] == "Name"  # header uses labels
    name_cell = 'Smith,\nJones, Bo"bby'
    assert any(row and row[0] == name_cell for row in parsed[1:]), parsed


def test_csv_bad_format_rejected(client: TestClient) -> None:
    assert client.get("/reports/roster", params={"format": "pdf"}).status_code == 422


def test_bad_param_rejected(client: TestClient) -> None:
    assert client.get("/reports/swim", params={"stale_months": "notanumber"}).status_code == 422
    assert client.get("/reports/roster", params={"member_type": "alien"}).status_code == 422


def test_unknown_report_404(client: TestClient) -> None:
    assert client.get("/reports/nope").status_code == 404


# ---------------------------------------------------------------------------
# Advancement summary
# ---------------------------------------------------------------------------


def _seed_rank(db: Session) -> tuple[Rank, RequirementSet, list[Requirement]]:
    tenant = db.get(Tenant, TENANT_A)
    if tenant is None:
        db.add(
            Tenant(
                id=TENANT_A,
                name="Troop A",
                slug="troopa",
                advancement_mode=AdvancementMode.CHAIR_ENTRY,
            )
        )
    else:
        tenant.advancement_mode = AdvancementMode.CHAIR_ENTRY
    rank = Rank(code=RankCode.TENDERFOOT, name="Tenderfoot", sort_order=2)
    db.add(rank)
    db.flush()
    req_set = RequirementSet(rank_id=rank.id, version="2025", effective_date=date(2025, 1, 1))
    db.add(req_set)
    db.flush()
    leaves = [
        Requirement(requirement_set_id=req_set.id, number="1", letter="", text="One", sort_order=0),
        Requirement(requirement_set_id=req_set.id, number="2", letter="", text="Two", sort_order=1),
    ]
    db.add_all(leaves)
    db.commit()
    return rank, req_set, leaves


def test_advancement_summary_percent_matches_progress_endpoint(
    client: TestClient, db_session: Session
) -> None:
    _rank, _set, leaves = _seed_rank(db_session)
    scout = _scout(db_session, "Adv", "Scout")

    # Approve one of the two leaves (chair_entry records land approved).
    resp = client.post(
        f"/members/{scout.id}/advancement/completions",
        json={"requirement_id": str(leaves[0].id), "date_completed": "2026-06-01"},
    )
    assert resp.status_code == 201, resp.text

    # Derive the expected percentage from the member progress endpoint itself.
    detail = client.get(f"/members/{scout.id}/advancement").json()
    tenderfoot = next(r for r in detail["ranks"] if r["rank"]["code"] == "tenderfoot")
    parent_ids = {rq["requirement"]["parent_id"] for rq in tenderfoot["requirements"]}
    leaf_reqs = [
        rq for rq in tenderfoot["requirements"] if rq["requirement"]["id"] not in parent_ids
    ]
    total = len(leaf_reqs)
    completed = sum(1 for rq in leaf_reqs if rq["is_complete"])
    expected_percent = round(completed / total * 100)

    rows = _rows(client.get("/reports/advancement").json())
    row = _by_name(rows, "Scout, Adv")
    assert row["next_rank"] == "Tenderfoot"
    assert row["next_rank_percent"] == expected_percent
    assert row["merit_badge_count"] == 0


def test_advancement_summary_only_scouts(client: TestClient, db_session: Session) -> None:
    _seed_rank(db_session)
    _scout(db_session, "Youth", "Scout")
    db_session.add(
        Member(tenant_id=TENANT_A, first_name="Grown", last_name="Up", member_type=MemberType.ADULT)
    )
    db_session.commit()

    names = {r["name"] for r in _rows(client.get("/reports/advancement").json())}
    assert "Scout, Youth" in names
    assert "Up, Grown" not in names
