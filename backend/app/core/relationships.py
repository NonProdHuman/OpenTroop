"""Family-relationship resolution for RSVP authorization.

Defines the *household* a member may act for when RSVPing on behalf of family.
"Family" is **derived** from the directional ``parent_of`` / ``guardian_of`` edges
in ``MemberRelationship`` — there are no stored ``spouse_of``/co-parent edges.

Household rules (see ``docs/spec/event-rsvp-permission.md``):

- A member may always act for **themselves**.
- A parent/guardian may act for their **children/wards** (direct parent/guardian edges).
- A parent/guardian may act for any **co-parent** — another adult who shares one of
  *their* children (covers spouses without a ``spouse_of`` type).
- The closure is **household-bounded, not transitive**: it stops at the actor's own
  children. If A and B share child X, and B has child Y with a different co-parent C,
  then Y and C are **not** in A's household. One hop through a shared child only.

This mirrors ``app.core.groups.resolve_group_members`` — the relationship rules live
in exactly one place so the participants endpoints and any future surface share them.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.enums import RelationshipType
from app.models.member import Member, MemberRelationship

_PARENT_EDGES = (RelationshipType.PARENT_OF, RelationshipType.GUARDIAN_OF)


def _children_of(member_id: uuid.UUID, session: Session) -> set[uuid.UUID]:
    """Members the given member is a parent/guardian of (their wards)."""
    return set(
        session.scalars(
            select(MemberRelationship.to_member_id).where(
                MemberRelationship.from_member_id == member_id,
                MemberRelationship.relationship_type.in_(_PARENT_EDGES),
                MemberRelationship.is_deleted.is_(False),
            )
        ).all()
    )


def _parents_of(
    child_ids: set[uuid.UUID] | frozenset[uuid.UUID], session: Session
) -> set[uuid.UUID]:
    """Adults who are a parent/guardian of any of the given children."""
    if not child_ids:
        return set()
    return set(
        session.scalars(
            select(MemberRelationship.from_member_id).where(
                MemberRelationship.to_member_id.in_(child_ids),
                MemberRelationship.relationship_type.in_(_PARENT_EDGES),
                MemberRelationship.is_deleted.is_(False),
            )
        ).all()
    )


def is_guardian_of(adult_id: uuid.UUID, child_id: uuid.UUID, session: Session) -> bool:
    """Whether ``adult_id`` holds a direct parent/guardian edge over ``child_id``.

    Stricter than household membership — used to gate *signing a permission slip*,
    which only a direct parent/guardian may do (not a mere co-parent or sibling).
    """
    return (
        session.scalar(
            select(MemberRelationship.id).where(
                MemberRelationship.from_member_id == adult_id,
                MemberRelationship.to_member_id == child_id,
                MemberRelationship.relationship_type.in_(_PARENT_EDGES),
                MemberRelationship.is_deleted.is_(False),
            )
        )
        is not None
    )


def family_member_ids(member_id: uuid.UUID, session: Session) -> frozenset[uuid.UUID]:
    """Return every member ``member_id`` may RSVP for — **including themselves**.

    The set is ``{self} ∪ children/wards ∪ co-parents`` (see module docstring). For a
    scout (no children) this collapses to just ``{self}``, enforcing "a scout acts only
    for itself". Soft-deleted members and relationships are excluded; the closure is
    deliberately one hop (household), never transitive.
    """
    children = _children_of(member_id, session)
    # Co-parents: other adults who share one of *my* children with me.
    co_parents = _parents_of(children, session)

    candidates = {member_id} | children | co_parents

    # Filter out soft-deleted members (a child/co-parent edge may point at a tombstone).
    return frozenset(
        session.scalars(
            select(Member.id).where(
                Member.id.in_(candidates),
                Member.is_deleted.is_(False),
            )
        ).all()
    )
