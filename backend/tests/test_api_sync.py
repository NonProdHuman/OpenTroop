"""API tests for the offline sync pull endpoint (docs/spec/sync-protocol.md, GH-120)."""

import uuid

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import MemberType
from app.models.member import Member
from tests.conftest import TENANT_A


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
