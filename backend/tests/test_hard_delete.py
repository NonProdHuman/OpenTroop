"""Hard-delete flows (GH-222): member purge, tombstone reaper, sync watermark,
tenant export + delete.

Member purge is anonymize-in-place (immediate erasure, sync tombstone); the
reaper physically deletes the skeleton after the ≥180-day retention window and
records the ``purged_through_seq`` watermark that drives the sync 410 path.
Tenant delete is immediate, gated on suspension + a fresh export + slug confirm.
"""

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.orm import Session
from uuid6 import uuid7

from app.core.config import Settings
from app.core.deletion import MEMBER_PII_NULLED, reap_purged_members
from app.core.tenant_context import include_deleted, unscoped
from app.models.enums import MemberType, Permission, PositionScope, RelationshipType
from app.models.event import EventParticipant
from app.models.group import GroupMember
from app.models.member import Member, MemberRelationship
from app.models.message import Message, MessageRecipient
from app.models.push import PushToken
from app.models.rbac import (
    FunctionalRole,
    FunctionalRolePermission,
    MemberPositionAssignment,
    Position,
    PositionFunctionalRole,
)
from app.models.tenant import Tenant
from app.models.user import User
from tests.conftest import _ADMIN_MEMBER_IDS, NEW_USER_ID, TENANT_A

ADMIN_MEMBER_A = _ADMIN_MEMBER_IDS[TENANT_A]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk_member(client: TestClient, first: str = "Erased", last: str = "Person") -> uuid.UUID:
    r = client.post(
        "/members",
        json={
            "first_name": first,
            "last_name": last,
            "member_type": "scout",
            "email": "kid@example.com",
            "phone": "555-0000",
            "date_of_birth": "2012-03-04",
            "allergies": "peanuts",
            "notes": "leader-only note",
            "bsa_id": "12345678",
        },
    )
    assert r.status_code == 201, r.text
    return uuid.UUID(r.json()["id"])


def _purge(client: TestClient, member_id: uuid.UUID, confirm: str, **kw: object) -> object:
    return client.post(f"/members/{member_id}/purge", json={"confirm_name": confirm}, **kw)


def _seed_non_admin_deleter(db: Session) -> None:
    """Give NEW_USER_ID a TENANT_A member holding member:delete but *not* admin."""
    member = Member(
        tenant_id=TENANT_A,
        user_id=NEW_USER_ID,
        first_name="Deputy",
        last_name="Deleter",
        member_type=MemberType.ADULT,
    )
    db.add(member)
    db.flush()
    role = FunctionalRole(tenant_id=TENANT_A, name="Member Admins", slug="member-admins")
    db.add(role)
    db.flush()
    db.add(
        FunctionalRolePermission(
            tenant_id=TENANT_A, functional_role_id=role.id, permission=Permission.MEMBER_DELETE
        )
    )
    position = Position(
        tenant_id=TENANT_A, name="Registrar", slug="registrar", applies_to=PositionScope.ADULT
    )
    db.add(position)
    db.flush()
    db.add(
        PositionFunctionalRole(
            tenant_id=TENANT_A, position_id=position.id, functional_role_id=role.id
        )
    )
    db.add(
        MemberPositionAssignment(tenant_id=TENANT_A, member_id=member.id, position_id=position.id)
    )
    db.commit()


# ---------------------------------------------------------------------------
# Member purge — anonymize in place
# ---------------------------------------------------------------------------


def test_purge_nulls_pii_and_tombstones(client: TestClient, db_session: Session) -> None:
    member_id = _mk_member(client)
    event_id = uuid7()
    db_session.add_all(
        [
            MemberRelationship(
                tenant_id=TENANT_A,
                from_member_id=ADMIN_MEMBER_A,
                to_member_id=member_id,
                relationship_type=RelationshipType.PARENT_OF,
            ),
            GroupMember(tenant_id=TENANT_A, group_id=uuid7(), member_id=member_id),
            PushToken(
                tenant_id=TENANT_A,
                member_id=member_id,
                token="ExponentPushToken[x]",  # noqa: S106 — synthetic device token, not a secret
            ),
            EventParticipant(
                tenant_id=TENANT_A,
                event_id=event_id,
                member_id=member_id,
                comment="picky eater, call me",
            ),
            EventParticipant(
                tenant_id=TENANT_A,
                event_id=event_id,
                member_id=ADMIN_MEMBER_A,
                electronic_permission_by_id=member_id,
                electronic_permission_signature="Erased Person",
            ),
        ]
    )
    db_session.commit()

    r = _purge(client, member_id, "erased  PERSON")  # case/whitespace-insensitive
    assert r.status_code == 204, r.text

    with unscoped(), include_deleted():
        m = db_session.get(Member, member_id)
        assert m is not None
        for field in MEMBER_PII_NULLED:
            assert getattr(m, field) is None, field
        assert (m.first_name, m.last_name) == ("Deleted", "Member")
        assert m.is_deleted is True
        assert m.purged_at is not None

        rel = db_session.scalar(
            select(MemberRelationship).where(MemberRelationship.to_member_id == member_id)
        )
        assert rel is not None and rel.is_deleted is True
        gm = db_session.scalar(select(GroupMember).where(GroupMember.member_id == member_id))
        assert gm is not None and gm.is_deleted is True
        assert db_session.scalar(select(PushToken).where(PushToken.member_id == member_id)) is None
        own_part = db_session.scalar(
            select(EventParticipant).where(EventParticipant.member_id == member_id)
        )
        assert own_part is not None and own_part.comment is None  # row kept, text scrubbed
        signed = db_session.scalar(
            select(EventParticipant).where(
                EventParticipant.electronic_permission_by_id == member_id
            )
        )
        assert signed is not None and signed.electronic_permission_signature is None


def test_purge_tombstone_flows_through_sync(client: TestClient) -> None:
    member_id = _mk_member(client, "Sync", "Target")
    purged = _purge(client, member_id, "Sync Target")
    assert purged.status_code == 204

    r = client.get("/sync/members")
    assert r.status_code == 200
    row = next(i for i in r.json()["items"] if i["id"] == str(member_id))
    assert row["is_deleted"] is True
    assert row["first_name"] == "Deleted"
    assert row["email"] is None


def test_purge_requires_tenant_admin(client: TestClient, db_session: Session) -> None:
    _seed_non_admin_deleter(db_session)
    member_id = _mk_member(client)
    r = _purge(client, member_id, "Erased Person", headers={"X-Test-User-ID": str(NEW_USER_ID)})
    assert r.status_code == 403
    assert "administrator" in r.json()["detail"]


def test_purge_confirm_name_mismatch(client: TestClient) -> None:
    member_id = _mk_member(client)
    r = _purge(client, member_id, "Wrong Name")
    assert r.status_code == 400
    # Nothing changed.
    assert client.get(f"/members/{member_id}").status_code == 200


def test_purge_unknown_member_404(client: TestClient) -> None:
    assert _purge(client, uuid7(), "Any One").status_code == 404


def test_purge_cross_tenant_404(client: TestClient, other_client: TestClient) -> None:
    member_id = _mk_member(client)
    assert _purge(other_client, member_id, "Erased Person").status_code == 404


def test_purge_twice_409(client: TestClient) -> None:
    member_id = _mk_member(client)
    first = _purge(client, member_id, "Erased Person")
    assert first.status_code == 204
    r = _purge(client, member_id, "Deleted Member")
    assert r.status_code == 409
    assert "already" in r.json()["detail"]


def test_purge_soft_deleted_member_allowed(client: TestClient) -> None:
    member_id = _mk_member(client)
    removed = client.delete(f"/members/{member_id}")  # roster removal
    assert removed.status_code == 204
    purged = _purge(client, member_id, "Erased Person")  # erasure still works
    assert purged.status_code == 204


def test_purge_sole_admin_self_409_last_admin(client: TestClient) -> None:
    r = _purge(client, ADMIN_MEMBER_A, "Admin User")
    assert r.status_code == 409
    assert "last administrator" in r.json()["detail"]


def test_purge_self_409_with_other_admin(client: TestClient, db_session: Session) -> None:
    # Give a second member the Administrator position so the caller isn't the last.
    other = Member(
        tenant_id=TENANT_A, first_name="Second", last_name="Admin", member_type=MemberType.ADULT
    )
    db_session.add(other)
    db_session.flush()
    admin_pos = db_session.scalar(
        select(Position).where(Position.tenant_id == TENANT_A, Position.slug == "administrator")
    )
    assert admin_pos is not None
    db_session.add(
        MemberPositionAssignment(tenant_id=TENANT_A, member_id=other.id, position_id=admin_pos.id)
    )
    db_session.commit()

    r = _purge(client, ADMIN_MEMBER_A, "Admin User")
    assert r.status_code == 409
    assert "yourself" in r.json()["detail"]


def test_member_columns_reviewed_for_pii() -> None:
    """Tripwire: every Member column must be classified — nulled on purge or
    deliberately kept. A new column failing here means: decide, then add it to
    MEMBER_PII_NULLED (app/core/deletion.py) or the kept-list below."""
    kept = {
        # identity of the row, not the person
        "id",
        "tenant_id",
        "created_at",
        "updated_at",
        "is_deleted",
        "sync_seq",
        "purged_at",
        # replaced with placeholders, not nulled
        "first_name",
        "last_name",
        # non-identifying categorical/history fields
        "member_type",
        "membership_status",
        "swim_classification",
        "troop_membership_start_date",
        "troop_membership_end_date",
        # notification flags (reset to defaults on purge)
        "email_opt_out",
        "email_bounced",
        "sms_opt_in",
        "announcement_email_mode",
        # OA booleans/dates: advancement history, no identity content
        "oa_member",
        "oa_active",
        "oa_election_date",
        "oa_call_out_date",
        "oa_ordeal_date",
        "oa_brotherhood_date",
        "oa_vigil_date",
    }
    all_columns = {c.key for c in Member.__table__.columns}
    unclassified = all_columns - kept - set(MEMBER_PII_NULLED)
    assert not unclassified, f"new Member column(s) need a purge decision: {unclassified}"


# ---------------------------------------------------------------------------
# Reaper + watermark
# ---------------------------------------------------------------------------


def _seed_purged_member(db: Session, *, days_ago: int) -> Member:
    member = Member(
        tenant_id=TENANT_A,
        first_name="Deleted",
        last_name="Member",
        member_type=MemberType.SCOUT,
        is_deleted=True,
        purged_at=datetime.now(UTC) - timedelta(days=days_ago),
    )
    db.add(member)
    db.flush()
    return member


def test_reaper_deletes_only_past_retention(db_session: Session) -> None:
    db_session.add(Tenant(id=TENANT_A, name="Troop A", slug="troop-a"))
    old = _seed_purged_member(db_session, days_ago=181)
    fresh = _seed_purged_member(db_session, days_ago=5)
    survivor = Member(
        tenant_id=TENANT_A, first_name="Still", last_name="Here", member_type=MemberType.ADULT
    )
    db_session.add(survivor)
    db_session.flush()
    db_session.add_all(
        [
            EventParticipant(tenant_id=TENANT_A, event_id=uuid7(), member_id=old.id),
            MemberPositionAssignment(
                tenant_id=TENANT_A,
                member_id=survivor.id,
                position_id=uuid7(),
                assigned_by_id=old.id,
            ),
            Message(
                tenant_id=TENANT_A, subject="hi", body="all", sent_by_id=old.id, is_deleted=False
            ),
            MessageRecipient(tenant_id=TENANT_A, message_id=uuid7(), member_id=old.id),
            MemberRelationship(
                tenant_id=TENANT_A,
                from_member_id=old.id,
                to_member_id=survivor.id,
                relationship_type=RelationshipType.PARENT_OF,
                is_deleted=True,
            ),
        ]
    )
    db_session.commit()
    old_id, fresh_id = old.id, fresh.id

    reaped = reap_purged_members(db_session)
    db_session.commit()
    assert reaped == 1

    with unscoped(), include_deleted():
        assert db_session.get(Member, old_id) is None
        assert db_session.get(Member, fresh_id) is not None  # inside retention — untouched
        assert (
            db_session.scalar(select(EventParticipant).where(EventParticipant.member_id == old_id))
            is None
        )
        assert (
            db_session.scalar(
                select(MemberRelationship).where(MemberRelationship.from_member_id == old_id)
            )
            is None
        )
        assert (
            db_session.scalar(select(MessageRecipient).where(MessageRecipient.member_id == old_id))
            is None
        )
        assignment = db_session.scalar(
            select(MemberPositionAssignment).where(
                MemberPositionAssignment.member_id == survivor.id
            )
        )
        assert assignment is not None and assignment.assigned_by_id is None
        message = db_session.scalar(select(Message).where(Message.subject == "hi"))
        assert message is not None and message.sent_by_id is None

        tenant = db_session.get(Tenant, TENANT_A)
        assert tenant is not None
        assert tenant.purged_through_seq is not None and tenant.purged_through_seq > 0


def test_reaper_rejects_sub_floor_retention(db_session: Session) -> None:
    with pytest.raises(ValueError, match="180"):
        reap_purged_members(db_session, retention_days=90)


def test_settings_reject_sub_floor_retention() -> None:
    kwargs: dict[str, object] = {
        "app_secret": "x" * 32,
        "app_domain": "opentroop.test",
        "cors_origins": ["http://localhost:3000"],
        "_env_file": None,
    }
    with pytest.raises(ValidationError):
        Settings(tombstone_retention_days=90, **kwargs)  # type: ignore[arg-type]
    assert Settings(tombstone_retention_days=365, **kwargs).tombstone_retention_days == 365  # type: ignore[arg-type]


def test_sync_410_behind_watermark(client: TestClient, db_session: Session) -> None:
    db_session.add(Tenant(id=TENANT_A, name="Troop A", slug="troop-a", purged_through_seq=5000))
    db_session.commit()

    stale = client.get("/sync/members", params={"since_seq": 1})
    assert stale.status_code == 410
    assert "since_seq=0" in stale.json()["detail"]

    # A full refetch works and its final cursor is clamped up to the watermark,
    # so the next incremental pull does not 410 again.
    fresh = client.get("/sync/members")
    assert fresh.status_code == 200
    assert fresh.json()["next_since_seq"] == 5000
    assert client.get("/sync/members", params={"since_seq": 5000}).status_code == 200


def test_sync_unaffected_without_watermark(client: TestClient) -> None:
    # No Tenant row / no reap ever: incremental cursors behave as before.
    assert client.get("/sync/members", params={"since_seq": 1}).status_code == 200


# ---------------------------------------------------------------------------
# Tenant export + delete (platform control plane)
# ---------------------------------------------------------------------------


def _provision(client: TestClient, slug: str = "troop-doomed") -> dict:
    r = client.post(
        "/platform/tenants",
        json={
            "name": "Doomed Troop",
            "slug": slug,
            "founder_first_name": "Fiona",
            "founder_last_name": "Founder",
            "founder_email": "fiona@example.com",
        },
    )
    assert r.status_code == 201, r.text
    return r.json()


def test_export_bundle_and_stamp(platform_admin_client: TestClient) -> None:
    tenant = _provision(platform_admin_client, "troop-export")
    r = platform_admin_client.get(f"/platform/tenants/{tenant['id']}/export")
    assert r.status_code == 200
    assert "attachment" in r.headers["content-disposition"]
    bundle = r.json()
    assert bundle["format"] == "opentroop-tenant-export"
    assert bundle["tenant"]["slug"] == "troop-export"
    members = bundle["tables"]["members"]
    assert any(m["email"] == "fiona@example.com" for m in members)
    assert bundle["tables"]["event_types"]  # seeded defaults included
    # The gate is armed.
    after = platform_admin_client.get(f"/platform/tenants/{tenant['id']}")
    assert after.json()["last_export_at"] is not None


def test_export_requires_superadmin(
    platform_admin_client: TestClient, support_client: TestClient
) -> None:
    tenant = _provision(platform_admin_client, "troop-support")
    assert support_client.get(f"/platform/tenants/{tenant['id']}/export").status_code == 403


def _delete(client: TestClient, tenant_id: str, slug: str) -> object:
    return client.request("DELETE", f"/platform/tenants/{tenant_id}", json={"confirm_slug": slug})


def test_delete_gates(platform_admin_client: TestClient) -> None:
    tenant = _provision(platform_admin_client, "troop-gated")
    tid = tenant["id"]

    # 1. Not suspended.
    r = _delete(platform_admin_client, tid, "troop-gated")
    assert r.status_code == 409 and "suspended" in r.json()["detail"]

    # 2. Export taken *before* suspension doesn't count.
    early_export = platform_admin_client.get(f"/platform/tenants/{tid}/export")
    assert early_export.status_code == 200
    suspended = platform_admin_client.post(f"/platform/tenants/{tid}/suspend")
    assert suspended.status_code == 200
    r = _delete(platform_admin_client, tid, "troop-gated")
    assert r.status_code == 409 and "export" in r.json()["detail"]

    # 3. Fresh export, wrong slug.
    fresh_export = platform_admin_client.get(f"/platform/tenants/{tid}/export")
    assert fresh_export.status_code == 200
    r = _delete(platform_admin_client, tid, "troop-wrong")
    assert r.status_code == 400

    # 4. All gates passed.
    deleted = _delete(platform_admin_client, tid, "troop-gated")
    assert deleted.status_code == 204
    assert platform_admin_client.get(f"/platform/tenants/{tid}").status_code == 404


def test_delete_purges_rows_and_frees_slug(
    platform_admin_client: TestClient, db_session: Session
) -> None:
    tenant = _provision(platform_admin_client, "troop-666")
    keeper = _provision(platform_admin_client, "troop-keeper")
    tid = tenant["id"]
    bystander = User(email="spans-tenants@example.com", display_name="Spans Tenants")
    db_session.add(bystander)
    db_session.commit()

    suspended = platform_admin_client.post(f"/platform/tenants/{tid}/suspend")
    assert suspended.status_code == 200
    exported = platform_admin_client.get(f"/platform/tenants/{tid}/export")
    assert exported.status_code == 200
    deleted = _delete(platform_admin_client, tid, "troop-666")
    assert deleted.status_code == 204

    with unscoped(), include_deleted():
        doomed = uuid.UUID(tid)
        for model in (Member, Position, FunctionalRole, MemberPositionAssignment):
            assert db_session.scalar(select(model).where(model.tenant_id == doomed)) is None, (
                model.__name__
            )
        # The other tenant and the platform users survive.
        assert db_session.scalar(select(Member).where(Member.tenant_id == uuid.UUID(keeper["id"])))
        assert db_session.get(User, bystander.id) is not None

    # The slug is immediately reusable — "new Troop 666" just works.
    assert _provision(platform_admin_client, "troop-666")["slug"] == "troop-666"


def test_delete_requires_superadmin(
    platform_admin_client: TestClient, support_client: TestClient
) -> None:
    tenant = _provision(platform_admin_client, "troop-locked")
    assert _delete(support_client, tenant["id"], "troop-locked").status_code == 403


def test_tenant_b_isolated_from_tenant_a_purge(
    client: TestClient, other_client: TestClient, db_session: Session
) -> None:
    """A member purge in tenant A cannot touch tenant B rows (scoping belt)."""
    a_member = _mk_member(client, "Alpha", "Kid")
    b_member = _mk_member(other_client, "Beta", "Kid")
    purged = _purge(client, a_member, "Alpha Kid")
    assert purged.status_code == 204
    with unscoped(), include_deleted():
        b = db_session.get(Member, b_member)
        assert b is not None and b.purged_at is None and b.email is not None
