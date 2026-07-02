"""Regression tests for the automatic tenant + soft-delete scoping in database.py.

These lock in the invariants that let route code drop hand-written
``.is_deleted.is_(False)`` predicates and the manual ``tenant_id`` re-check in
``get_or_404``:

- an ORM ``SELECT`` under a tenant scope excludes soft-deleted and cross-tenant rows;
- ``Session.get()`` — used by ``get_or_404`` — honors the same criteria (a fresh
  per-request session sees ``None`` for a deleted or other-tenant primary key);
- ``include_deleted()`` reveals tombstones while keeping tenant scoping;
- ``unscoped()`` disables both filters for cross-tenant platform work.
"""

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.tenant_context import include_deleted, tenant_scope, unscoped
from app.models.enums import MemberType
from app.models.member import Member
from tests.conftest import TENANT_A, TENANT_B


def _make_member(session: Session, tenant_id: uuid.UUID) -> uuid.UUID:
    """Insert a member directly (no request context, so nothing is auto-filtered)."""
    member = Member(
        tenant_id=tenant_id,
        first_name="Scout",
        last_name="Test",
        member_type=MemberType.SCOUT,
    )
    session.add(member)
    session.commit()
    member_id = member.id
    # Model a fresh per-request session: clear the identity map so any subsequent
    # get()/select() must emit a real SELECT that flows through the scoping filters.
    session.expunge_all()
    return member_id


def test_soft_deleted_rows_are_auto_filtered(db_session: Session) -> None:
    member_id = _make_member(db_session, TENANT_A)

    with tenant_scope(TENANT_A):
        assert db_session.get(Member, member_id) is not None
        assert db_session.scalar(select(Member).where(Member.id == member_id)) is not None

    # Soft-delete outside any scope (setup path sees everything).
    member = db_session.get(Member, member_id)
    assert member is not None
    member.is_deleted = True
    db_session.commit()
    db_session.expunge_all()

    with tenant_scope(TENANT_A):
        # get() honors the criteria — this is what lets get_or_404 drop its manual check.
        assert db_session.get(Member, member_id) is None
        assert db_session.scalar(select(Member).where(Member.id == member_id)) is None

    # include_deleted() reveals the tombstone while still scoping to the tenant.
    with tenant_scope(TENANT_A), include_deleted():
        assert db_session.get(Member, member_id) is not None
        assert db_session.scalar(select(Member).where(Member.id == member_id)) is not None


def test_get_is_tenant_scoped(db_session: Session) -> None:
    member_id = _make_member(db_session, TENANT_A)

    with tenant_scope(TENANT_B):
        # A different tenant cannot resolve the row by primary key.
        assert db_session.get(Member, member_id) is None
        assert db_session.scalar(select(Member).where(Member.id == member_id)) is None

    with tenant_scope(TENANT_A):
        assert db_session.get(Member, member_id) is not None


def test_unscoped_disables_both_filters(db_session: Session) -> None:
    member_id = _make_member(db_session, TENANT_A)
    member = db_session.get(Member, member_id)
    assert member is not None
    member.is_deleted = True
    db_session.commit()
    db_session.expunge_all()

    # unscoped(): a soft-deleted row in another (or any) tenant is visible again.
    with tenant_scope(TENANT_B), unscoped():
        assert db_session.get(Member, member_id) is not None
        assert db_session.scalar(select(Member).where(Member.id == member_id)) is not None
