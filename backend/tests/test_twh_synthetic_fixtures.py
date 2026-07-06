"""Round-trip tests for the committed synthetic TWH fixtures (GH-205).

The fixtures are fully synthetic (see ``scripts/generate_twh_fixture.py``) and
regenerable with ``uv run generate-twh-fixture``. These tests are the contract
that both committed files stay importable end to end — roster, events, and
advancement — against the real shipped advancement catalog.
"""

import gzip
import uuid
from pathlib import Path
from xml.etree import ElementTree as ET

import pytest
from sqlalchemy.orm import Session

from app.core.advancement_catalog import load_catalog
from app.importers.twh import TwhImporter
from app.models.advancement import (
    MemberMeritBadge,
    MemberRankProgress,
    MemberRequirementCompletion,
)
from app.models.enums import CompletionStatus, RecordedVia

_FIXTURES = Path(__file__).parent / "fixtures"
_TENANTS = {
    1: uuid.UUID("10000000-0000-0000-0000-0000000000f1"),
    2: uuid.UUID("10000000-0000-0000-0000-0000000000f2"),
}


@pytest.fixture(params=[1, 2], ids=["troop1", "troop2"])
def fixture_import(request, db_session: Session):
    load_catalog(db_session)
    path = _FIXTURES / f"synthetic_troop{request.param}.xml.gz"
    xml = gzip.decompress(path.read_bytes())
    root = ET.fromstring(xml)  # noqa: S314 — committed synthetic fixture
    tenant = _TENANTS[request.param]
    result = TwhImporter(db_session, tenant).run(root)
    return result, db_session, tenant


def test_roster_and_events_import(fixture_import) -> None:
    result, _, _ = fixture_import
    assert result.patrols == 3
    assert result.members >= 20
    assert result.relationships >= 10
    assert result.position_assignments >= 8
    assert result.locations == 4  # the disabled one is skipped
    assert result.event_types >= 6
    assert result.events >= 20
    assert result.participants >= 150


def test_advancement_imports(fixture_import) -> None:
    result, session, tenant = fixture_import
    assert result.rank_progress >= 30
    assert result.requirement_completions >= 30
    assert result.merit_badges >= 80

    progress_rows = session.query(MemberRankProgress).filter_by(tenant_id=tenant).all()
    assert progress_rows
    # The Eagle alumni earned all seven ranks.
    per_member: dict[uuid.UUID, int] = {}
    for row in progress_rows:
        if row.completed_date is not None:
            per_member[row.member_id] = per_member.get(row.member_id, 0) + 1
    assert max(per_member.values()) == 7

    completions = session.query(MemberRequirementCompletion).filter_by(tenant_id=tenant).all()
    assert all(c.recorded_via is RecordedVia.IMPORT for c in completions)
    statuses = {c.status for c in completions}
    # Chair-entered history + one Pending + one Rejected from Requirement_Pending.
    assert CompletionStatus.APPROVED in statuses
    assert CompletionStatus.REPORTED in statuses
    assert CompletionStatus.REJECTED in statuses

    badges = session.query(MemberMeritBadge).filter_by(tenant_id=tenant).all()
    assert any(b.date_completed is None for b in badges)  # partials preserved
    assert all(b.source_system == "twh" for b in badges)


def test_expected_warnings_only(fixture_import) -> None:
    """The fixtures' deliberate edge cases produce exactly these warning families."""
    result, _, _ = fixture_import
    families = {
        "palm": lambda w: "Palm" in w,
        "unknown badge": lambda w: "Sample Legacy Badge" in w,
        "legacy unmatched": lambda w: "unmatched requirement scout 3" in w,
        "mb pending deferred": lambda w: "per-MB tracking deferred" in w,
    }
    for name, match in families.items():
        assert any(match(w) for w in result.warnings), f"expected a {name} warning"
    unexpected = [
        w
        for w in result.warnings
        if not any(match(w) for match in families.values())
        and not w.startswith("Created ")  # positions not in seeded defaults (unseeded RBAC)
    ]
    assert unexpected == []


def test_fixture_regeneration_is_deterministic() -> None:
    """`uv run generate-twh-fixture` reproduces the committed files byte-for-byte.

    Compared on *decompressed* content so a different zlib build can never
    produce a false drift.
    """
    from scripts.generate_twh_fixture import generate_xml

    for troop in (1, 2):
        committed = gzip.decompress((_FIXTURES / f"synthetic_troop{troop}.xml.gz").read_bytes())
        assert generate_xml(troop) == committed, (
            f"synthetic_troop{troop}.xml.gz drifted — rerun `uv run generate-twh-fixture`"
        )
