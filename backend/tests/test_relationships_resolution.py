"""Unit tests for family_member_ids — the household closure used for RSVP authorization.

Covers the bounded (non-transitive) household rule and the A/B/C boundary case from
docs/spec/event-rsvp-permission.md.
"""

import uuid

from app.core.relationships import family_member_ids
from app.core.tenant_context import tenant_scope
from app.models.enums import MemberType, RelationshipType
from app.models.member import Member, MemberRelationship

_TENANT = uuid.UUID("10000000-0000-0000-0000-000000000001")


def _member(session, name: str, member_type: MemberType = MemberType.ADULT) -> Member:
    m = Member(
        tenant_id=_TENANT,
        first_name=name,
        last_name="Test",
        member_type=member_type,
    )
    session.add(m)
    session.flush()
    return m


def _parent(session, adult: Member, child: Member, rel=RelationshipType.PARENT_OF) -> None:
    session.add(
        MemberRelationship(
            tenant_id=_TENANT,
            from_member_id=adult.id,
            to_member_id=child.id,
            relationship_type=rel,
        )
    )
    session.flush()


def test_scout_acts_only_for_self(db_session) -> None:
    scout = _member(db_session, "Scout", MemberType.SCOUT)
    assert family_member_ids(scout.id, db_session) == frozenset({scout.id})


def test_parent_reaches_children_and_coparent(db_session) -> None:
    a = _member(db_session, "ParentA")
    b = _member(db_session, "ParentB")
    x = _member(db_session, "ChildX", MemberType.SCOUT)
    _parent(db_session, a, x)
    _parent(db_session, b, x)  # B is co-parent of X

    # A reaches: self, child X, and co-parent B — not anyone else.
    assert family_member_ids(a.id, db_session) == frozenset({a.id, x.id, b.id})
    # Symmetric: B reaches A too.
    assert family_member_ids(b.id, db_session) == frozenset({b.id, x.id, a.id})


def test_guardian_edge_counts(db_session) -> None:
    guardian = _member(db_session, "Guardian")
    ward = _member(db_session, "Ward", MemberType.SCOUT)
    _parent(db_session, guardian, ward, RelationshipType.GUARDIAN_OF)
    assert ward.id in family_member_ids(guardian.id, db_session)


def test_household_is_not_transitive_abc_boundary(db_session) -> None:
    """A and B share X; B and C share Y. A must not reach C or Y."""
    a = _member(db_session, "A")
    b = _member(db_session, "B")
    c = _member(db_session, "C")
    x = _member(db_session, "X", MemberType.SCOUT)  # A & B
    y = _member(db_session, "Y", MemberType.SCOUT)  # B & C
    z = _member(db_session, "Z", MemberType.SCOUT)  # A only
    _parent(db_session, a, x)
    _parent(db_session, b, x)
    _parent(db_session, b, y)
    _parent(db_session, c, y)
    _parent(db_session, a, z)

    a_family = family_member_ids(a.id, db_session)
    # A reaches own children X, Z and co-parent B (shares X).
    assert a_family == frozenset({a.id, x.id, z.id, b.id})
    # A must NOT reach B's other child Y, nor Y's other parent C.
    assert y.id not in a_family
    assert c.id not in a_family

    # B sits in the middle and reaches both households' adults and children.
    b_family = family_member_ids(b.id, db_session)
    assert b_family == frozenset({b.id, x.id, y.id, a.id, c.id})
    assert z.id not in b_family  # A's solo child is not B's


def test_soft_deleted_member_and_relationship_excluded(db_session) -> None:
    a = _member(db_session, "A")
    child = _member(db_session, "Child", MemberType.SCOUT)
    gone = _member(db_session, "GoneChild", MemberType.SCOUT)
    _parent(db_session, a, child)
    _parent(db_session, a, gone)
    gone.is_deleted = True
    db_session.flush()

    # Resolvers run under a tenant scope in production; the soft-delete exclusion is a
    # session-level guarantee (see app.core.database), so scope the call here too.
    with tenant_scope(_TENANT):
        fam = family_member_ids(a.id, db_session)
    assert child.id in fam
    assert gone.id not in fam  # soft-deleted member dropped

    # Soft-deleting the edge also removes the child.
    rel = db_session.query(MemberRelationship).filter_by(to_member_id=child.id).one()
    rel.is_deleted = True
    db_session.flush()
    with tenant_scope(_TENANT):
        assert child.id not in family_member_ids(a.id, db_session)
