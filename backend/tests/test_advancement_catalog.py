"""Advancement catalog: models, seed loader, and provisioning flags (GH-92 Phase 1)."""

import json
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.advancement_catalog import DATA_DIR, load_catalog
from app.core.provisioning import seed_default_event_types, seed_default_rbac
from app.models import (
    EventType,
    MeritBadge,
    Position,
    Rank,
    RankCode,
    Requirement,
    RequirementSet,
)

TENANT = uuid.UUID("10000000-0000-0000-0000-000000000001")


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


def test_requirement_unique_within_set(db_session: Session) -> None:
    rank = Rank(code=RankCode.SCOUT, name="Scout", sort_order=1)
    db_session.add(rank)
    db_session.flush()
    req_set = RequirementSet(rank_id=rank.id, version="2025")
    db_session.add(req_set)
    db_session.flush()
    db_session.add(
        Requirement(requirement_set_id=req_set.id, number="1", letter="a", text="x", sort_order=0)
    )
    db_session.flush()
    db_session.add(
        Requirement(requirement_set_id=req_set.id, number="1", letter="a", text="y", sort_order=1)
    )
    with pytest.raises(IntegrityError):
        db_session.flush()
    db_session.rollback()


def test_requirement_label(db_session: Session) -> None:
    rank = Rank(code=RankCode.EAGLE, name="Eagle", sort_order=7)
    db_session.add(rank)
    db_session.flush()
    req_set = RequirementSet(rank_id=rank.id, version="2025")
    db_session.add(req_set)
    db_session.flush()
    bare = Requirement(requirement_set_id=req_set.id, number="3", text="badges", sort_order=0)
    lettered = Requirement(
        requirement_set_id=req_set.id, number="1", letter="b", text="x", sort_order=1
    )
    db_session.add_all([bare, lettered])
    db_session.flush()  # letter's column default ("") applies at flush
    assert bare.label == "3"
    assert lettered.label == "1b"


# ---------------------------------------------------------------------------
# Seed loader (synthetic fixture files)
# ---------------------------------------------------------------------------


def _write_rank_file(path: Path, requirements: list[dict[str, object]]) -> None:
    payload = {
        "version": "2025",
        "effective_date": "2025-01-01",
        "ranks": [
            {
                "code": "tenderfoot",
                "name": "Tenderfoot",
                "sort_order": 2,
                "requirements": requirements,
            }
        ],
    }
    path.write_text(json.dumps(payload))


_REQS: list[dict[str, object]] = [
    {"number": "1", "letter": "", "text": "Do the following:", "stable_key": "tf.1"},
    {
        "number": "1",
        "letter": "a",
        "text": "Sleep in a tent you helped pitch.",
        "stable_key": "tf.1a-campout",
    },
    {
        "number": "7",
        "letter": "b",
        "text": "Participate in one hour of service.",
        "stable_key": "tf.7b-service",
        "metrics": [{"kind": "service_hours", "threshold": 1, "window": "since_joining"}],
        "auto_credit": True,
    },
]


def test_loader_creates_and_links(db_session: Session, tmp_path: Path) -> None:
    _write_rank_file(tmp_path / "ranks-2025.json", _REQS)
    (tmp_path / "merit-badges.json").write_text(
        json.dumps(
            {
                "badges": [
                    {"name": "Camping", "eagle_required": True, "is_discontinued": False},
                    {"name": "Basketry", "eagle_required": False, "is_discontinued": False},
                ]
            }
        )
    )

    stats = load_catalog(db_session, tmp_path)
    assert stats.ranks == 1
    assert stats.requirement_sets == 1
    assert stats.requirements_created == 3
    assert stats.merit_badges_created == 2

    # Container linkage: 1a hangs off 1; 7b has no bare "7" so no parent.
    reqs = {(r.number, r.letter): r for r in db_session.scalars(select(Requirement)).all()}
    assert reqs[("1", "a")].parent_id == reqs[("1", "")].id
    assert reqs[("7", "b")].parent_id is None
    assert reqs[("7", "b")].auto_credit is True
    assert reqs[("7", "b")].metrics == [
        {"kind": "service_hours", "threshold": 1, "window": "since_joining"}
    ]


def test_loader_is_idempotent(db_session: Session, tmp_path: Path) -> None:
    _write_rank_file(tmp_path / "ranks-2025.json", _REQS)
    load_catalog(db_session, tmp_path)
    stats = load_catalog(db_session, tmp_path)
    assert stats.ranks == 0
    assert stats.requirements_created == 0
    assert stats.requirements_updated == 0
    assert stats.requirements_removed == 0


def test_loader_updates_text_in_place(db_session: Session, tmp_path: Path) -> None:
    _write_rank_file(tmp_path / "ranks-2025.json", _REQS)
    load_catalog(db_session, tmp_path)
    original = db_session.scalar(
        select(Requirement).where(Requirement.number == "1", Requirement.letter == "a")
    )
    assert original is not None
    original_id = original.id

    fixed = [dict(r) for r in _REQS]
    fixed[1]["text"] = "Sleep in a tent that you helped pitch."
    _write_rank_file(tmp_path / "ranks-2025.json", fixed)
    stats = load_catalog(db_session, tmp_path)
    assert stats.requirements_updated == 1

    updated = db_session.get(Requirement, original_id)
    assert updated is not None
    assert updated.text == "Sleep in a tent that you helped pitch."


def test_loader_tombstones_and_revives(db_session: Session, tmp_path: Path) -> None:
    _write_rank_file(tmp_path / "ranks-2025.json", _REQS)
    load_catalog(db_session, tmp_path)

    _write_rank_file(tmp_path / "ranks-2025.json", _REQS[:2])  # drop 7b
    stats = load_catalog(db_session, tmp_path)
    assert stats.requirements_removed == 1
    dropped = db_session.scalar(select(Requirement).where(Requirement.number == "7"))
    assert dropped is not None and dropped.is_deleted is True

    _write_rank_file(tmp_path / "ranks-2025.json", _REQS)  # re-add
    load_catalog(db_session, tmp_path)
    revived = db_session.get(Requirement, dropped.id)
    assert revived is not None and revived.is_deleted is False


def test_loader_rejects_invalid_metric(db_session: Session, tmp_path: Path) -> None:
    bad = [dict(_REQS[2])]
    bad[0]["metrics"] = [{"kind": "not-a-kind", "threshold": 1, "window": "any"}]
    _write_rank_file(tmp_path / "ranks-2025.json", bad)
    with pytest.raises(ValueError, match="invalid metric condition"):
        load_catalog(db_session, tmp_path)


def test_loader_rejects_duplicate_requirement(db_session: Session, tmp_path: Path) -> None:
    _write_rank_file(tmp_path / "ranks-2025.json", [_REQS[0], dict(_REQS[0])])
    with pytest.raises(ValueError, match="duplicate"):
        load_catalog(db_session, tmp_path)


# ---------------------------------------------------------------------------
# The real data files (backend/data/advancement/)
# ---------------------------------------------------------------------------


def test_real_catalog_loads(db_session: Session) -> None:
    """The shipped data files load cleanly and cover the whole program."""
    stats = load_catalog(db_session, DATA_DIR)
    assert stats.ranks == 7

    ranks = db_session.scalars(select(Rank).order_by(Rank.sort_order)).all()
    assert [r.code for r in ranks] == [
        RankCode.SCOUT,
        RankCode.TENDERFOOT,
        RankCode.SECOND_CLASS,
        RankCode.FIRST_CLASS,
        RankCode.STAR,
        RankCode.LIFE,
        RankCode.EAGLE,
    ]
    # Every rank has at least one requirement set with a plausible number of items.
    for rank in ranks:
        sets = db_session.scalars(
            select(RequirementSet).where(RequirementSet.rank_id == rank.id)
        ).all()
        assert sets, f"{rank.code} has no requirement set"
        for req_set in sets:
            count = len(
                db_session.scalars(
                    select(Requirement).where(Requirement.requirement_set_id == req_set.id)
                ).all()
            )
            assert count >= 7, f"{rank.code} v{req_set.version} has only {count} requirements"

    badges = db_session.scalars(select(MeritBadge)).all()
    assert len(badges) >= 130
    eagle_required = [b for b in badges if b.eagle_required]
    # The Eagle-required list including both alternates in each either/or pair.
    assert len(eagle_required) >= 14

    # Idempotency against the real files too.
    stats2 = load_catalog(db_session, DATA_DIR)
    assert stats2.requirements_created == 0
    assert stats2.requirements_updated == 0


def test_real_catalog_has_auto_credit_service_hours(db_session: Session) -> None:
    """The differentiating feature: service-hour requirements are auto-creditable."""
    load_catalog(db_session, DATA_DIR)
    auto = db_session.scalars(select(Requirement).where(Requirement.auto_credit.is_(True))).all()
    assert auto, "no auto-credit requirements seeded"
    kinds = {c["kind"] for r in auto for c in (r.metrics or [])}
    assert "service_hours" in kinds


# ---------------------------------------------------------------------------
# Provisioning flags (counts_as_activity / counts_for_por)
# ---------------------------------------------------------------------------


def test_seeded_event_types_activity_flags(db_session: Session) -> None:
    seed_default_event_types(db_session, TENANT)
    db_session.flush()
    types = {t.name: t for t in db_session.scalars(select(EventType)).all()}
    assert types["Meeting"].counts_as_activity is False
    assert types["Court of Honor"].counts_as_activity is False
    assert types["Campout"].counts_as_activity is True
    assert types["Service Project"].counts_as_activity is True


def test_seeded_positions_por_flags(db_session: Session) -> None:
    seed_default_rbac(db_session, TENANT)
    positions = {p.slug: p for p in db_session.scalars(select(Position)).all()}
    assert positions["senior-patrol-leader"].counts_for_por is True
    assert positions["patrol-leader"].counts_for_por is True
    assert positions["scribe"].counts_for_por is True
    assert positions["assistant-patrol-leader"].counts_for_por is False
    assert positions["scoutmaster"].counts_for_por is False
    assert positions["member"].counts_for_por is False
