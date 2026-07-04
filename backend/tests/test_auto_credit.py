"""Auto-credit engine (GH-92 Phase 3): metrics, thresholds, invariants, triggers."""

import uuid
from datetime import UTC, date, datetime

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.advancement import (
    apply_auto_credits,
    compute_member_metrics,
    evaluate_requirement_metrics,
)
from app.models import (
    CompletionStatus,
    Event,
    EventParticipant,
    EventType,
    Member,
    MemberPositionAssignment,
    MemberRankProgress,
    MemberRequirementCompletion,
    MemberType,
    MeritBadge,
    Position,
    Rank,
    RankCode,
    RecordedVia,
    Requirement,
    RequirementSet,
)
from app.models.advancement import MemberMeritBadge
from tests.conftest import TENANT_A


def _scout(db: Session) -> Member:
    member = Member(
        tenant_id=TENANT_A,
        first_name="Auto",
        last_name="Credit",
        member_type=MemberType.SCOUT,
        troop_membership_start_date=date(2025, 1, 1),
    )
    db.add(member)
    db.flush()
    return member


class _Catalog:
    """Tenderfoot (service auto-credit) + First Class / Star (since_rank + badges)."""

    def __init__(self, db: Session) -> None:
        self.tenderfoot = Rank(code=RankCode.TENDERFOOT, name="Tenderfoot", sort_order=2)
        self.first_class = Rank(code=RankCode.FIRST_CLASS, name="First Class", sort_order=4)
        self.star = Rank(code=RankCode.STAR, name="Star", sort_order=5)
        db.add_all([self.tenderfoot, self.first_class, self.star])
        db.flush()
        self.tf_set = RequirementSet(rank_id=self.tenderfoot.id, version="2025")
        self.fc_set = RequirementSet(rank_id=self.first_class.id, version="2025")
        self.star_set = RequirementSet(rank_id=self.star.id, version="2025")
        db.add_all([self.tf_set, self.fc_set, self.star_set])
        db.flush()
        self.tf_service = Requirement(
            requirement_set_id=self.tf_set.id,
            number="7",
            letter="b",
            text="One hour of service.",
            sort_order=0,
            metrics=[{"kind": "service_hours", "threshold": 1, "window": "since_joining"}],
            auto_credit=True,
        )
        self.tf_manual = Requirement(
            requirement_set_id=self.tf_set.id,
            number="9",
            letter="",
            text="Scout spirit.",
            sort_order=1,
        )
        self.fc_any = Requirement(
            requirement_set_id=self.fc_set.id,
            number="1",
            letter="",
            text="Placeholder.",
            sort_order=0,
        )
        # Star: six service hours *while a First Class Scout* (since_rank).
        self.star_service = Requirement(
            requirement_set_id=self.star_set.id,
            number="4",
            letter="",
            text="Six hours of service while a First Class Scout.",
            sort_order=0,
            metrics=[{"kind": "service_hours", "threshold": 6, "window": "since_rank"}],
            auto_credit=True,
        )
        # Star: six badges incl. four Eagle-required (small thresholds for the test).
        self.star_badges = Requirement(
            requirement_set_id=self.star_set.id,
            number="3",
            letter="",
            text="Earn merit badges.",
            sort_order=1,
            metrics=[
                {"kind": "merit_badge_count", "threshold": 2, "window": "any"},
                {"kind": "merit_badge_count_eagle_required", "threshold": 1, "window": "any"},
            ],
            auto_credit=True,
        )
        db.add_all(
            [self.tf_service, self.tf_manual, self.fc_any, self.star_service, self.star_badges]
        )
        db.flush()


def _service_event(
    db: Session,
    *,
    hours: float,
    when: date,
    counts_as_activity: bool = True,
) -> Event:
    event_type = EventType(
        tenant_id=TENANT_A,
        name=f"Service {uuid.uuid4().hex[:6]}",
        tracks_service_hours=True,
        counts_as_activity=counts_as_activity,
    )
    db.add(event_type)
    db.flush()
    event = Event(
        tenant_id=TENANT_A,
        name="Park cleanup",
        event_type_id=event_type.id,
        scheduled_start=datetime(when.year, when.month, when.day, 9, tzinfo=UTC),
        scheduled_end=datetime(when.year, when.month, when.day, 12, tzinfo=UTC),
        community_service_hours=hours,
        attendance_taken=True,
    )
    db.add(event)
    db.flush()
    return event


def _attend(db: Session, event: Event, member: Member, **overrides: object) -> EventParticipant:
    participant = EventParticipant(
        tenant_id=TENANT_A,
        event_id=event.id,
        member_id=member.id,
        attended=True,
        **overrides,
    )
    db.add(participant)
    db.flush()
    return participant


def test_service_hours_auto_credit(db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    _attend(db_session, _service_event(db_session, hours=1.5, when=date(2026, 5, 1)), scout)

    created = apply_auto_credits(scout.id, db_session)
    assert [c.requirement_id for c in created] == [cat.tf_service.id]
    completion = created[0]
    assert completion.status is CompletionStatus.APPROVED
    assert completion.recorded_via is RecordedVia.AUTO

    # A progress row was created lazily with the set elected.
    progress = db_session.scalar(
        select(MemberRankProgress).where(MemberRankProgress.member_id == scout.id)
    )
    assert progress is not None and progress.requirement_set_id == cat.tf_set.id

    # Idempotent: a second pass creates nothing.
    assert apply_auto_credits(scout.id, db_session) == []


def test_below_threshold_no_credit(db_session: Session) -> None:
    _Catalog(db_session)
    scout = _scout(db_session)
    _attend(db_session, _service_event(db_session, hours=0.5, when=date(2026, 5, 1)), scout)
    assert apply_auto_credits(scout.id, db_session) == []


def test_participant_override_wins(db_session: Session) -> None:
    """A per-person zero override (left early, did no service) blocks the credit."""
    _Catalog(db_session)
    scout = _scout(db_session)
    event = _service_event(db_session, hours=2, when=date(2026, 5, 1))
    _attend(db_session, event, scout, community_service_hours_override=0)
    assert apply_auto_credits(scout.id, db_session) == []


def test_not_attended_not_counted(db_session: Session) -> None:
    _Catalog(db_session)
    scout = _scout(db_session)
    event = _service_event(db_session, hours=2, when=date(2026, 5, 1))
    participant = EventParticipant(
        tenant_id=TENANT_A, event_id=event.id, member_id=scout.id, attended=False
    )
    db_session.add(participant)
    db_session.flush()
    assert apply_auto_credits(scout.id, db_session) == []


def test_revoked_credit_never_recreated(db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    _attend(db_session, _service_event(db_session, hours=2, when=date(2026, 5, 1)), scout)
    created = apply_auto_credits(scout.id, db_session)
    assert len(created) == 1

    created[0].is_deleted = True  # chair revokes the credit
    db_session.flush()
    assert apply_auto_credits(scout.id, db_session) == []
    active = db_session.scalars(
        select(MemberRequirementCompletion).where(
            MemberRequirementCompletion.member_id == scout.id,
            MemberRequirementCompletion.requirement_id == cat.tf_service.id,
            MemberRequirementCompletion.is_deleted.is_(False),
        )
    ).all()
    assert active == []


def test_since_rank_requires_previous_bor(db_session: Session) -> None:
    """Star service accrues only after First Class's board-of-review date."""
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    _attend(db_session, _service_event(db_session, hours=8, when=date(2026, 3, 1)), scout)

    # No First Class completion recorded → the since_rank anchor is unavailable.
    created = apply_auto_credits(scout.id, db_session)
    assert cat.star_service.id not in {c.requirement_id for c in created}

    # Record First Class earned before the event → the same pass now credits it.
    db_session.add(
        MemberRankProgress(
            tenant_id=TENANT_A,
            member_id=scout.id,
            rank_id=cat.first_class.id,
            requirement_set_id=cat.fc_set.id,
            completed_date=date(2026, 1, 15),
        )
    )
    db_session.flush()
    created = apply_auto_credits(scout.id, db_session)
    assert cat.star_service.id in {c.requirement_id for c in created}

    # Hours earned *before* the BOR date must not count: a fresh scout with the
    # same setup but the event pre-dating First Class gets nothing.
    scout2 = _scout(db_session)
    _attend(db_session, _service_event(db_session, hours=8, when=date(2025, 12, 1)), scout2)
    db_session.add(
        MemberRankProgress(
            tenant_id=TENANT_A,
            member_id=scout2.id,
            rank_id=cat.first_class.id,
            requirement_set_id=cat.fc_set.id,
            completed_date=date(2026, 1, 15),
        )
    )
    db_session.flush()
    created2 = apply_auto_credits(scout2.id, db_session)
    assert cat.star_service.id not in {c.requirement_id for c in created2}


def test_merit_badge_counts(db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    camping = MeritBadge(name="Camping", eagle_required=True)
    basketry = MeritBadge(name="Basketry", eagle_required=False)
    db_session.add_all([camping, basketry])
    db_session.flush()
    for badge in (camping, basketry):
        db_session.add(
            MemberMeritBadge(
                tenant_id=TENANT_A,
                member_id=scout.id,
                merit_badge_id=badge.id,
                date_completed=date(2026, 4, 1),
                status=CompletionStatus.APPROVED,
            )
        )
    db_session.flush()

    metrics = compute_member_metrics(scout.id, db_session)
    assert metrics.badge_count == 2
    assert metrics.badge_count_eagle_required == 1

    created = apply_auto_credits(scout.id, db_session)
    assert cat.star_badges.id in {c.requirement_id for c in created}


def test_completed_rank_stops_accruing(db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    db_session.add(
        MemberRankProgress(
            tenant_id=TENANT_A,
            member_id=scout.id,
            rank_id=cat.tenderfoot.id,
            requirement_set_id=cat.tf_set.id,
            completed_date=date(2026, 2, 1),
        )
    )
    db_session.flush()
    _attend(db_session, _service_event(db_session, hours=2, when=date(2026, 5, 1)), scout)
    created = apply_auto_credits(scout.id, db_session)
    assert cat.tf_service.id not in {c.requirement_id for c in created}


def test_por_months_meter(db_session: Session) -> None:
    """Concurrent POR terms count elapsed time once; meters expose the value."""
    _Catalog(db_session)
    scout = _scout(db_session)
    pl = Position(tenant_id=TENANT_A, name="Patrol Leader", slug="pl", counts_for_por=True)
    scribe = Position(tenant_id=TENANT_A, name="Scribe", slug="scribe", counts_for_por=True)
    apl = Position(tenant_id=TENANT_A, name="APL", slug="apl", counts_for_por=False)
    db_session.add_all([pl, scribe, apl])
    db_session.flush()
    db_session.add_all(
        [
            MemberPositionAssignment(
                tenant_id=TENANT_A,
                member_id=scout.id,
                position_id=pl.id,
                start_date=date(2026, 1, 1),
                end_date=date(2026, 4, 1),
            ),
            # Overlapping second POR — must not double-count.
            MemberPositionAssignment(
                tenant_id=TENANT_A,
                member_id=scout.id,
                position_id=scribe.id,
                start_date=date(2026, 2, 1),
                end_date=date(2026, 4, 1),
            ),
            # Non-POR position — ignored entirely.
            MemberPositionAssignment(
                tenant_id=TENANT_A,
                member_id=scout.id,
                position_id=apl.id,
                start_date=date(2025, 1, 1),
                end_date=date(2026, 4, 1),
            ),
        ]
    )
    db_session.flush()
    from app.models.enums import MetricKind

    metrics = compute_member_metrics(scout.id, db_session, today=date(2026, 6, 1))
    por = metrics.value(MetricKind.POR_MONTHS, None)
    assert 2.8 < por < 3.2  # Jan 1 – Apr 1 ≈ 3 months, overlap counted once


def test_meters_report_unavailable_anchor(db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    metrics = compute_member_metrics(scout.id, db_session)
    progress = evaluate_requirement_metrics(
        cat.star_service, scout.id, cat.star, metrics, db_session
    )
    assert len(progress) == 1
    assert progress[0].value is None and progress[0].met is False


# ---------------------------------------------------------------------------
# In-request triggers
# ---------------------------------------------------------------------------


def test_attendance_patch_triggers_credit(client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    event = _service_event(db_session, hours=2, when=date(2026, 5, 1))
    participant = EventParticipant(
        tenant_id=TENANT_A, event_id=event.id, member_id=scout.id, attended=False
    )
    db_session.add(participant)
    db_session.commit()

    r = client.patch(f"/events/{event.id}/participants/{scout.id}", json={"attended": True})
    assert r.status_code == 200, r.text
    completion = db_session.scalar(
        select(MemberRequirementCompletion).where(
            MemberRequirementCompletion.member_id == scout.id,
            MemberRequirementCompletion.requirement_id == cat.tf_service.id,
        )
    )
    assert completion is not None
    assert completion.recorded_via is RecordedVia.AUTO


def test_event_metric_edit_triggers_recompute(client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    event = _service_event(db_session, hours=0.25, when=date(2026, 5, 1))
    _attend(db_session, event, scout)
    db_session.commit()
    assert apply_auto_credits(scout.id, db_session) == []  # below threshold

    r = client.patch(f"/events/{event.id}", json={"community_service_hours": "3.0"})
    assert r.status_code == 200, r.text
    completion = db_session.scalar(
        select(MemberRequirementCompletion).where(
            MemberRequirementCompletion.member_id == scout.id,
            MemberRequirementCompletion.requirement_id == cat.tf_service.id,
        )
    )
    assert completion is not None


def test_merit_badge_post_triggers_recompute(client: TestClient, db_session: Session) -> None:
    cat = _Catalog(db_session)
    scout = _scout(db_session)
    camping = MeritBadge(name="Camping", eagle_required=True)
    basketry = MeritBadge(name="Basketry", eagle_required=False)
    db_session.add_all([camping, basketry])
    db_session.flush()
    db_session.commit()

    for badge in (camping, basketry):
        r = client.post(
            f"/members/{scout.id}/merit-badges",
            json={"merit_badge_id": str(badge.id), "date_completed": "2026-04-01"},
        )
        assert r.status_code == 201

    completion = db_session.scalar(
        select(MemberRequirementCompletion).where(
            MemberRequirementCompletion.member_id == scout.id,
            MemberRequirementCompletion.requirement_id == cat.star_badges.id,
        )
    )
    assert completion is not None
    assert completion.recorded_via is RecordedVia.AUTO
