import uuid
from datetime import date

from sqlalchemy import inspect

from app.models import (
    Group,
    GroupMember,
    GroupType,
    Member,
    MemberRelationship,
    MemberStatus,
    MemberType,
    RelationshipType,
    SwimClassification,
)


def test_all_tables_created(db_session):
    """Every declared model produces a physical table."""
    table_names = set(inspect(db_session.get_bind()).get_table_names())
    assert {
        "groups",
        "group_members",
        "group_rules",
        "members",
        "member_relationships",
        "positions",
        "functional_roles",
        "functional_role_permissions",
        "position_functional_roles",
        "member_position_assignments",
    } <= table_names


def test_tracking_fields_have_defaults(db_session):
    """The TrackedBase contract populates id/timestamps/is_deleted automatically."""
    tenant_id = uuid.uuid4()
    group = Group(name="Eagle", tenant_id=tenant_id, group_type=GroupType.PATROL)
    db_session.add(group)
    db_session.commit()
    db_session.refresh(group)

    assert isinstance(group.id, uuid.UUID)
    assert group.tenant_id == tenant_id
    assert group.created_at is not None
    assert group.updated_at is not None
    assert group.is_deleted is False


def test_group_membership(db_session):
    """A member belongs to a group via a GroupMember row."""
    tenant_id = uuid.uuid4()
    group = Group(name="Hawk", tenant_id=tenant_id, group_type=GroupType.PATROL)
    scout = Member(
        tenant_id=tenant_id,
        first_name="Sam",
        last_name="Scout",
        member_type=MemberType.SCOUT,
        swim_classification=SwimClassification.SWIMMER,
    )
    db_session.add_all([group, scout])
    db_session.flush()
    membership = GroupMember(tenant_id=tenant_id, group_id=group.id, member_id=scout.id)
    db_session.add(membership)
    db_session.commit()

    assert group.members[0].member_id == scout.id
    assert membership.member is scout
    assert membership.group is group


def test_parent_child_relationship(db_session):
    """Parent <-> Scout link navigates correctly through MemberRelationship."""
    tenant_id = uuid.uuid4()
    parent = Member(
        tenant_id=tenant_id,
        first_name="Pat",
        last_name="Parent",
        member_type=MemberType.ADULT,
    )
    scout = Member(
        tenant_id=tenant_id,
        first_name="Sam",
        last_name="Scout",
        member_type=MemberType.SCOUT,
    )
    link = MemberRelationship(
        tenant_id=tenant_id,
        from_member=parent,
        to_member=scout,
        relationship_type=RelationshipType.PARENT_OF,
    )
    db_session.add(link)
    db_session.commit()

    assert scout.incoming_relationships[0].from_member is parent
    assert parent.outgoing_relationships[0].to_member is scout
    assert scout.incoming_relationships[0].relationship_type is RelationshipType.PARENT_OF


def test_sibling_relationship(db_session):
    """Sibling relationship stored with lower UUID as from_member by convention."""
    tenant_id = uuid.uuid4()
    sibling_a = Member(
        tenant_id=tenant_id,
        first_name="Alex",
        last_name="Scout",
        member_type=MemberType.SCOUT,
    )
    sibling_b = Member(
        tenant_id=tenant_id,
        first_name="Blake",
        last_name="Scout",
        member_type=MemberType.SCOUT,
    )
    db_session.add_all([sibling_a, sibling_b])
    db_session.flush()

    from_id, to_id = sorted([sibling_a.id, sibling_b.id])
    from_member = sibling_a if sibling_a.id == from_id else sibling_b
    to_member = sibling_b if from_member is sibling_a else sibling_a

    link = MemberRelationship(
        tenant_id=tenant_id,
        from_member=from_member,
        to_member=to_member,
        relationship_type=RelationshipType.SIBLING_OF,
    )
    db_session.add(link)
    db_session.commit()

    assert link.relationship_type is RelationshipType.SIBLING_OF
    assert from_member.outgoing_relationships[0].to_member is to_member
    assert to_member.incoming_relationships[0].from_member is from_member


def test_member_status_defaults_to_active(db_session):
    """New members default to ACTIVE; ALUMNI retains history without deletion."""
    tenant_id = uuid.uuid4()
    scout = Member(
        tenant_id=tenant_id,
        first_name="Sam",
        last_name="Scout",
        member_type=MemberType.SCOUT,
    )
    db_session.add(scout)
    db_session.commit()
    db_session.refresh(scout)

    assert scout.membership_status is MemberStatus.ACTIVE

    scout.membership_status = MemberStatus.ALUMNI
    scout.troop_membership_end_date = date(2024, 5, 31)
    db_session.commit()
    db_session.refresh(scout)

    assert scout.membership_status is MemberStatus.ALUMNI
    assert scout.is_deleted is False


def test_soft_delete_flag_is_settable(db_session):
    """is_deleted tombstone can be toggled for sync reconciliation."""
    tenant_id = uuid.uuid4()
    group = Group(name="Fox", tenant_id=tenant_id, group_type=GroupType.PATROL)
    db_session.add(group)
    db_session.commit()

    group.is_deleted = True
    db_session.commit()
    db_session.refresh(group)
    assert group.is_deleted is True


def test_member_extended_fields(db_session):
    """Extended personal and safety fields persist correctly."""
    tenant_id = uuid.uuid4()
    member = Member(
        tenant_id=tenant_id,
        first_name="Jordan",
        middle_name="Lee",
        last_name="Smith",
        name_suffix="Jr.",
        nickname="JJ",
        date_of_birth=date(2010, 3, 15),
        member_type=MemberType.SCOUT,
        address_line1="123 Main St",
        city="Springfield",
        state="IL",
        postal_code="62701",
        country="US",
        allergies="Peanuts",
        dietary_restrictions="Vegetarian",
        emergency_contact_1_name="Casey Smith",
        emergency_contact_1_phone="555-0100",
        medical_form_ab_date=date(2024, 1, 1),
        swim_date=date(2023, 6, 15),
    )
    db_session.add(member)
    db_session.commit()
    db_session.refresh(member)

    assert member.nickname == "JJ"
    assert member.date_of_birth == date(2010, 3, 15)
    assert member.allergies == "Peanuts"
    assert member.emergency_contact_1_name == "Casey Smith"
    assert member.swim_date == date(2023, 6, 15)
