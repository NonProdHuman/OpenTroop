"""API tests for the offline sync pull endpoint (docs/spec/sync-protocol.md, GH-120)."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import MemberType, Permission, RelationshipType
from app.models.member import Member, MemberRelationship
from app.models.rbac import (
    FunctionalRole,
    FunctionalRolePermission,
    MemberPositionAssignment,
    Position,
    PositionFunctionalRole,
)
from tests.conftest import NEW_USER_ID, TENANT_A


def _create_member(client: TestClient, first_name: str) -> dict:
    r = client.post(
        "/members/",
        json={"first_name": first_name, "last_name": "Sync", "member_type": "scout"},
    )
    assert r.status_code == 201, r.text
    return r.json()


def _pull(client: TestClient, **params: object) -> dict:
    r = client.get("/sync/members", params=params)  # type: ignore[arg-type]
    assert r.status_code == 200, r.text
    return r.json()


def test_initial_sync_returns_all_members_in_seq_order(client: TestClient) -> None:
    _create_member(client, "Alice")
    _create_member(client, "Bob")

    page = _pull(client)
    names = [m["first_name"] for m in page["items"]]
    # The admin fixture member is also in the stream; ours arrive after it, in order.
    assert names[-2:] == ["Alice", "Bob"]
    assert page["has_more"] is False
    assert page["next_since_id"] == page["items"][-1]["id"]
    assert page["next_since_seq"] > 0


def test_paging_never_skips_or_duplicates(client: TestClient) -> None:
    for i in range(5):
        _create_member(client, f"Scout{i}")

    seen: list[str] = []
    since_seq, since_id = 0, None
    for _ in range(20):  # generous upper bound; loop exits via has_more
        params: dict[str, object] = {"since_seq": since_seq, "limit": 2}
        if since_id is not None:
            params["since_id"] = since_id
        page = _pull(client, **params)
        seen.extend(m["id"] for m in page["items"])
        since_seq, since_id = page["next_since_seq"], page["next_since_id"]
        if not page["has_more"]:
            break

    all_ids = [m["id"] for m in _pull(client, limit=1000)["items"]]
    assert seen == all_ids  # same rows, same order, no skips, no duplicates
    assert len(set(seen)) == len(seen)


def test_update_moves_row_past_existing_cursor(client: TestClient) -> None:
    member = _create_member(client, "Carol")
    _create_member(client, "Dave")
    cursor = _pull(client)

    r = client.patch(f"/members/{member['id']}", json={"nickname": "Caz"})
    assert r.status_code == 200

    page = _pull(client, since_seq=cursor["next_since_seq"], since_id=cursor["next_since_id"])
    assert [m["id"] for m in page["items"]] == [member["id"]]
    assert page["items"][0]["nickname"] == "Caz"


def test_soft_delete_delivers_tombstone(client: TestClient) -> None:
    member = _create_member(client, "Erin")
    cursor = _pull(client)

    r = client.delete(f"/members/{member['id']}")
    assert r.status_code == 204

    page = _pull(client, since_seq=cursor["next_since_seq"], since_id=cursor["next_since_id"])
    assert [m["id"] for m in page["items"]] == [member["id"]]
    assert page["items"][0]["is_deleted"] is True
    # The interactive list endpoint keeps hiding it — only the sync stream sees tombstones.
    assert member["id"] not in {m["id"] for m in client.get("/members/").json()}


def test_empty_page_echoes_request_cursor(client: TestClient) -> None:
    cursor = _pull(client)
    page = _pull(client, since_seq=cursor["next_since_seq"], since_id=cursor["next_since_id"])
    assert page["items"] == []
    assert page["has_more"] is False
    assert page["next_since_seq"] == cursor["next_since_seq"]
    assert page["next_since_id"] == cursor["next_since_id"]


def test_seq_ties_are_ordered_and_paged_by_id(client: TestClient, db_session: Session) -> None:
    # A backfill (or the SQLite fallback under concurrency) can produce duplicate
    # sync_seq values; the (sync_seq, id) keyset must still page a total order.
    ids = sorted(uuid.uuid4() for _ in range(2))
    for i, mid in enumerate(ids):
        db_session.add(
            Member(
                id=mid,
                tenant_id=TENANT_A,
                first_name=f"Tie{i}",
                last_name="Sync",
                member_type=MemberType.SCOUT,
                sync_seq=999_999,
            )
        )
    db_session.commit()

    first = _pull(client, since_seq=999_998, limit=1)
    assert first["has_more"] is True
    assert first["items"][0]["id"] == str(ids[0])

    second = _pull(
        client, since_seq=first["next_since_seq"], since_id=first["next_since_id"], limit=1
    )
    assert second["items"][0]["id"] == str(ids[1])


def test_sync_is_tenant_scoped(client: TestClient, other_client: TestClient) -> None:
    member = _create_member(client, "Frank")
    other_page = other_client.get("/sync/members")
    assert other_page.status_code == 200
    assert member["id"] not in {m["id"] for m in other_page.json()["items"]}


def test_sync_requires_member_read(claim_client: TestClient) -> None:
    r = claim_client.get("/sync/members", headers={"X-Tenant-ID": str(TENANT_A)})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Mobile v1 streams: event_types, locations, events, participants, relationships
# (GH-153 follow-ups / GH-93 M1)
# ---------------------------------------------------------------------------


def _pull_entity(client: TestClient, entity: str, **params: object) -> dict:
    r = client.get(f"/sync/{entity}", params=params)  # type: ignore[arg-type]
    assert r.status_code == 200, r.text
    return r.json()


def _event_type(client: TestClient, name: str = "Hike") -> dict:
    r = client.post("/event-types/", json={"name": name})
    assert r.status_code == 201, r.text
    return r.json()


def _event(client: TestClient, event_type_id: str, name: str = "Outing") -> dict:
    r = client.post(
        "/events/",
        json={
            "name": name,
            "event_type_id": event_type_id,
            "scheduled_start": "2026-07-10T09:00:00Z",
            "scheduled_end": "2026-07-12T17:00:00Z",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def _seed_reader(db: Session) -> Member:
    """A member linked to NEW_USER_ID holding only event:read in TENANT_A."""
    role = FunctionalRole(tenant_id=TENANT_A, name="Reader", slug="reader")
    db.add(role)
    db.flush()
    db.add(
        FunctionalRolePermission(
            tenant_id=TENANT_A, functional_role_id=role.id, permission=Permission.EVENT_READ
        )
    )
    position = Position(tenant_id=TENANT_A, name="Reader Position", slug="reader-position")
    db.add(position)
    db.flush()
    db.add(
        PositionFunctionalRole(
            tenant_id=TENANT_A, position_id=position.id, functional_role_id=role.id
        )
    )
    reader = Member(
        tenant_id=TENANT_A,
        user_id=NEW_USER_ID,
        first_name="Reader",
        last_name="One",
        member_type=MemberType.ADULT,
    )
    db.add(reader)
    db.flush()
    db.add(
        MemberPositionAssignment(tenant_id=TENANT_A, member_id=reader.id, position_id=position.id)
    )
    db.commit()
    return reader


def _tenant_a(client: TestClient) -> dict[str, str]:
    return {"X-Tenant-ID": str(TENANT_A)}


def test_sync_event_types_and_locations_stream(client: TestClient) -> None:
    et = _event_type(client, "Campout")
    r = client.post("/locations/", json={"name": "Camp Ridge"})
    assert r.status_code == 201, r.text
    loc = r.json()

    types_page = _pull_entity(client, "event_types")
    assert et["id"] in [t["id"] for t in types_page["items"]]
    locs_page = _pull_entity(client, "locations")
    assert [item["id"] for item in locs_page["items"]] == [loc["id"]]

    # Tombstones flow past an existing cursor.
    cursor = locs_page
    deleted = client.delete(f"/locations/{loc['id']}")
    assert deleted.status_code == 204
    delta = _pull_entity(
        client, "locations", since_seq=cursor["next_since_seq"], since_id=cursor["next_since_id"]
    )
    assert [item["id"] for item in delta["items"]] == [loc["id"]]
    assert delta["items"][0]["is_deleted"] is True


def test_sync_events_visibility_filter(
    client: TestClient, claim_client: TestClient, db_session: Session
) -> None:
    et = _event_type(client)
    troop_event = _event(client, et["id"], name="Troop-wide")
    scoped_event = _event(client, et["id"], name="Wolf-only")
    group = client.post("/groups", json={"name": "Wolf", "group_type": "custom"}).json()
    r = client.post(f"/events/{scoped_event['id']}/audiences", json={"group_id": group["id"]})
    assert r.status_code == 201

    _seed_reader(db_session)

    # Manager (event:write) receives everything.
    admin_ids = [e["id"] for e in _pull_entity(client, "events")["items"]]
    assert {troop_event["id"], scoped_event["id"]} <= set(admin_ids)

    # The reader is not in the audience group: only the troop-wide event flows.
    reader_page = claim_client.get("/sync/events", headers=_tenant_a(client))
    assert reader_page.status_code == 200, reader_page.text
    reader_ids = [e["id"] for e in reader_page.json()["items"]]
    assert troop_event["id"] in reader_ids
    assert scoped_event["id"] not in reader_ids


def test_sync_event_participants_scoped_to_visible_events(
    client: TestClient, claim_client: TestClient, db_session: Session
) -> None:
    et = _event_type(client)
    troop_event = _event(client, et["id"], name="Troop-wide")
    scoped_event = _event(client, et["id"], name="Hidden")
    group = client.post("/groups", json={"name": "Bear", "group_type": "custom"}).json()
    audience = client.post(
        f"/events/{scoped_event['id']}/audiences", json={"group_id": group["id"]}
    )
    assert audience.status_code == 201

    scout = Member(
        tenant_id=TENANT_A, first_name="Sam", last_name="Scout", member_type=MemberType.SCOUT
    )
    db_session.add(scout)
    db_session.commit()
    for event in (troop_event, scoped_event):
        r = client.post(f"/events/{event['id']}/participants", json={"member_id": str(scout.id)})
        assert r.status_code == 201, r.text

    _seed_reader(db_session)

    admin_events = {p["event_id"] for p in _pull_entity(client, "event_participants")["items"]}
    assert {troop_event["id"], scoped_event["id"]} <= admin_events

    reader_page = claim_client.get("/sync/event_participants", headers=_tenant_a(client))
    assert reader_page.status_code == 200, reader_page.text
    reader_events = {p["event_id"] for p in reader_page.json()["items"]}
    assert troop_event["id"] in reader_events
    assert scoped_event["id"] not in reader_events


def test_sync_member_relationships_stream(client: TestClient, db_session: Session) -> None:
    parent = Member(
        tenant_id=TENANT_A, first_name="Pat", last_name="Parent", member_type=MemberType.ADULT
    )
    child = Member(
        tenant_id=TENANT_A, first_name="Kid", last_name="Parent", member_type=MemberType.SCOUT
    )
    db_session.add_all([parent, child])
    db_session.flush()
    rel = MemberRelationship(
        tenant_id=TENANT_A,
        from_member_id=parent.id,
        to_member_id=child.id,
        relationship_type=RelationshipType.PARENT_OF,
    )
    db_session.add(rel)
    db_session.commit()

    page = _pull_entity(client, "member_relationships")
    assert [item["id"] for item in page["items"]] == [str(rel.id)]
    assert page["items"][0]["relationship_type"] == "parent_of"


def test_sync_streams_require_permissions(claim_client: TestClient, client: TestClient) -> None:
    # NEW_USER_ID has no Member row here — every stream must refuse.
    for entity in (
        "members",
        "member_relationships",
        "event_types",
        "locations",
        "events",
        "event_participants",
    ):
        r = claim_client.get(f"/sync/{entity}", headers=_tenant_a(client))
        assert r.status_code == 403, entity


def test_sync_streams_tenant_isolated(client: TestClient, other_client: TestClient) -> None:
    et = _event_type(client)
    _event(client, et["id"], name="A-only")
    assert _pull_entity(other_client, "events")["items"] == []
    assert _pull_entity(other_client, "event_types")["items"] == []


# ---------------------------------------------------------------------------
# Family-scoped member streams (RSVP-for-everyone; GH-153 §C4 follow-up)
# ---------------------------------------------------------------------------


def _seed_family(db: Session) -> tuple[Member, Member, Member]:
    """Parent (linked to NEW_USER_ID, no permissions beyond event:read), their
    child, and an unrelated scout."""
    parent = Member(
        tenant_id=TENANT_A,
        user_id=NEW_USER_ID,
        first_name="Pat",
        last_name="Parent",
        member_type=MemberType.ADULT,
    )
    child = Member(
        tenant_id=TENANT_A, first_name="Kid", last_name="Parent", member_type=MemberType.SCOUT
    )
    other = Member(
        tenant_id=TENANT_A, first_name="Other", last_name="Scout", member_type=MemberType.SCOUT
    )
    db.add_all([parent, child, other])
    db.flush()
    db.add(
        MemberRelationship(
            tenant_id=TENANT_A,
            from_member_id=parent.id,
            to_member_id=child.id,
            relationship_type=RelationshipType.PARENT_OF,
        )
    )
    db.commit()
    return parent, child, other


def test_sync_members_family_scope_without_member_read(
    claim_client: TestClient, client: TestClient, db_session: Session
) -> None:
    parent, child, other = _seed_family(db_session)

    r = claim_client.get("/sync/members", headers=_tenant_a(client))
    assert r.status_code == 200, r.text
    ids = {m["id"] for m in r.json()["items"]}
    assert ids == {str(parent.id), str(child.id)}
    assert str(other.id) not in ids

    # member:read (admin) still mirrors the whole roster.
    admin_ids = {m["id"] for m in _pull_entity(client, "members")["items"]}
    assert {str(parent.id), str(child.id), str(other.id)} <= admin_ids


def test_sync_relationships_family_scope_without_member_read(
    claim_client: TestClient, client: TestClient, db_session: Session
) -> None:
    parent, child, other = _seed_family(db_session)
    # An unrelated family's edge must not leak into the parent's stream.
    other_parent = Member(
        tenant_id=TENANT_A, first_name="Ann", last_name="Other", member_type=MemberType.ADULT
    )
    db_session.add(other_parent)
    db_session.flush()
    db_session.add(
        MemberRelationship(
            tenant_id=TENANT_A,
            from_member_id=other_parent.id,
            to_member_id=other.id,
            relationship_type=RelationshipType.PARENT_OF,
        )
    )
    db_session.commit()

    r = claim_client.get("/sync/member_relationships", headers=_tenant_a(client))
    assert r.status_code == 200, r.text
    pairs = {(rel["from_member_id"], rel["to_member_id"]) for rel in r.json()["items"]}
    assert pairs == {(str(parent.id), str(child.id))}


# ---------------------------------------------------------------------------
# Security-review regressions (2026-07 review)
# ---------------------------------------------------------------------------


def test_sync_events_visibility_ignores_deleted_audience_rows(
    client: TestClient, claim_client: TestClient, db_session: Session
) -> None:
    """The sync streams lift the soft-delete filter for tombstones; a removed
    audience row must not keep granting (or withholding) visibility."""
    et = _event_type(client)
    event = _event(client, et["id"], name="Was scoped")
    group = client.post("/groups", json={"name": "Owl", "group_type": "custom"}).json()
    added = client.post(f"/events/{event['id']}/audiences", json={"group_id": group["id"]})
    assert added.status_code == 201
    _seed_reader(db_session)

    # Scoped: the reader (not in Owl) must not receive it.
    page = claim_client.get("/sync/events", headers=_tenant_a(client))
    assert event["id"] not in [e["id"] for e in page.json()["items"]]

    # Remove the audience — the event is troop-wide again and must now flow,
    # even though the tombstoned audience row is visible to the lifted filter.
    removed = client.delete(f"/events/{event['id']}/audiences/{group['id']}")
    assert removed.status_code == 204

    page = claim_client.get("/sync/events", headers=_tenant_a(client))
    assert event["id"] in [e["id"] for e in page.json()["items"]]


def test_family_scoped_members_redact_leader_notes(
    claim_client: TestClient, client: TestClient, db_session: Session
) -> None:
    """Parents without member:read get their household's contact/medical data,
    but never leader-facing notes."""
    parent, child, _ = _seed_family(db_session)
    child_row = db_session.get(Member, child.id)
    assert child_row is not None
    child_row.notes = "Leader-only: behavioral plan"
    child_row.oa_notes = "OA ceremony details"
    child_row.allergies = "Peanuts"
    db_session.commit()

    page = claim_client.get("/sync/members", headers=_tenant_a(client)).json()
    by_id = {m["id"]: m for m in page["items"]}
    assert by_id[str(child.id)]["notes"] is None
    assert by_id[str(child.id)]["oa_notes"] is None
    assert by_id[str(child.id)]["allergies"] == "Peanuts"  # family-owned field flows

    # member:read callers still see the notes.
    admin_page = _pull_entity(client, "members")
    admin_child = next(m for m in admin_page["items"] if m["id"] == str(child.id))
    assert admin_child["notes"] == "Leader-only: behavioral plan"


def test_sync_items_carry_sync_seq(client: TestClient) -> None:
    """Every synced row exposes its own ``sync_seq`` — the offline mirror stores
    it as a NOT NULL column per row, so an item without it aborts the client's
    pull transaction and wedges sync at ``since_seq=0`` (the 2026-07-07
    opentroop.dev mobile loop)."""
    _create_member(client, "Seqful")
    _event_type(client, "Seq Campout")

    for entity in ("members", "event_types"):
        page = _pull_entity(client, entity)
        assert page["items"], entity
        for item in page["items"]:
            assert isinstance(item.get("sync_seq"), int), f"{entity} item lacks sync_seq"
            assert item["sync_seq"] > 0
        # The envelope cursor is exactly the last item's (sync_seq, id).
        assert page["items"][-1]["sync_seq"] == page["next_since_seq"]
