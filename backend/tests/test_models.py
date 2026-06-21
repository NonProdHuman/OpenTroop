import uuid

from sqlalchemy import inspect

from app.models import (
    Member,
    MemberRelationship,
    MemberType,
    Patrol,
    RelationshipType,
    SwimClassification,
    TroopRole,
)


def test_all_tables_created(db_session):
    """Every declared model produces a physical table."""
    table_names = set(inspect(db_session.get_bind()).get_table_names())
    assert {"patrols", "members", "member_relationships"} <= table_names


def test_tracking_fields_have_defaults(db_session):
    """The TrackedBase contract populates id/timestamps/is_deleted automatically."""
    tenant_id = uuid.uuid4()
    patrol = Patrol(name="Eagle", tenant_id=tenant_id)
    db_session.add(patrol)
    db_session.commit()
    db_session.refresh(patrol)

    assert isinstance(patrol.id, uuid.UUID)
    assert patrol.tenant_id == tenant_id
    assert patrol.created_at is not None
    assert patrol.updated_at is not None
    assert patrol.is_deleted is False


def test_patrol_member_relationship(db_session):
    """Member <-> Patrol back-populates resolve in both directions."""
    tenant_id = uuid.uuid4()
    patrol = Patrol(name="Hawk", tenant_id=tenant_id)
    scout = Member(
        tenant_id=tenant_id,
        first_name="Sam",
        last_name="Scout",
        member_type=MemberType.SCOUT,
        troop_role=TroopRole.SENIOR_PATROL_LEADER,
        swim_classification=SwimClassification.SWIMMER,
        patrol=patrol,
    )
    db_session.add(scout)
    db_session.commit()

    assert scout.patrol is patrol
    assert patrol.members == [scout]


def test_guardian_junction_graph(db_session):
    """Adult <-> Scout link navigates correctly through MemberRelationship."""
    tenant_id = uuid.uuid4()
    adult = Member(
        tenant_id=tenant_id,
        first_name="Pat",
        last_name="Parent",
        member_type=MemberType.ADULT,
        troop_role=TroopRole.SCOUTMASTER,
    )
    scout = Member(
        tenant_id=tenant_id,
        first_name="Sam",
        last_name="Scout",
        member_type=MemberType.SCOUT,
    )
    link = MemberRelationship(
        tenant_id=tenant_id,
        adult=adult,
        scout=scout,
        relationship_type=RelationshipType.PARENT,
    )
    db_session.add(link)
    db_session.commit()

    assert scout.guardian_links[0].adult is adult
    assert adult.dependent_links[0].scout is scout
    assert scout.guardian_links[0].relationship_type is RelationshipType.PARENT


def test_soft_delete_flag_is_settable(db_session):
    """is_deleted tombstone can be toggled for sync reconciliation."""
    tenant_id = uuid.uuid4()
    patrol = Patrol(name="Fox", tenant_id=tenant_id)
    db_session.add(patrol)
    db_session.commit()

    patrol.is_deleted = True
    db_session.commit()
    db_session.refresh(patrol)
    assert patrol.is_deleted is True
