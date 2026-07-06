"""Tests for the TWH importer's advancement mapping (GH-205).

The crosswalk goes rank code + requirement number/letter → global catalog rows
(real exports carry no requirement text, only numbering), so these tests seed
the real shipped catalog and drive the importer with a hand-built XML literal
covering every match tier and skip path.
"""

import uuid
from datetime import date
from xml.etree import ElementTree as ET

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.advancement_catalog import load_catalog
from app.importers.twh import TwhImporter
from app.models.advancement import (
    MemberMeritBadge,
    MemberRankProgress,
    MemberRequirementCompletion,
    MeritBadge,
    Rank,
    Requirement,
)
from app.models.enums import CompletionStatus, RankCode, RecordedVia
from app.models.member import Member

_TENANT = uuid.UUID("10000000-0000-0000-0000-00000000ad01")

# Two scouts; person 999 is deliberately absent. Award/requirement ids mirror the
# shapes seen in real exports (zero-padded codes, "Current" versions, palms,
# "(YYYY rqmts)" badge suffixes).
_XML = """
<database name="Adv Test">
  <Person><i>1</i><Name_First>Alice</Name_First><Name_Last>Scout</Name_Last></Person>
  <Person><i>2</i><Name_First>Ben</Name_First><Name_Last>Scout</Name_Last></Person>

  <BSA_Award><i>515</i><Award_Name>Scout</Award_Name><Award_Type>Rank</Award_Type>
    <Rank_Code>RN</Rank_Code><Requirements_Version>Current</Requirements_Version></BSA_Award>
  <BSA_Award><i>519</i><Award_Name>Star</Award_Name><Award_Type>Rank</Award_Type>
    <Rank_Code>RS</Rank_Code><Requirements_Version>Current</Requirements_Version></BSA_Award>
  <BSA_Award><i>662</i><Award_Name>Bronze Palm</Award_Name><Award_Type>Rank</Award_Type>
    <Rank_Code>RZ</Rank_Code><Requirements_Version>Current</Requirements_Version></BSA_Award>
  <BSA_Award><i>700</i><Award_Name>First Aid</Award_Name>
    <Award_Type>Merit Badge</Award_Type><Requirements_Version>2025</Requirements_Version></BSA_Award>
  <BSA_Award><i>701</i><Award_Name>Personal Fitness (2023 rqmts)</Award_Name>
    <Award_Type>Merit Badge</Award_Type><Requirements_Version>2023</Requirements_Version></BSA_Award>
  <BSA_Award><i>702</i><Award_Name>Totally Unknown Badge</Award_Name>
    <Award_Type>Merit Badge</Award_Type><Requirements_Version>2025</Requirements_Version></BSA_Award>

  <BSA_Requirement><i>2700</i><BSA_Award_ID>515</BSA_Award_ID>
    <Requirement_Code>01.a</Requirement_Code></BSA_Requirement>
  <BSA_Requirement><i>2701</i><BSA_Award_ID>515</BSA_Award_ID>
    <Requirement_Code>02.</Requirement_Code></BSA_Requirement>
  <BSA_Requirement><i>2702</i><BSA_Award_ID>515</BSA_Award_ID>
    <Requirement_Code>6.b</Requirement_Code></BSA_Requirement>
  <BSA_Requirement><i>2703</i><BSA_Award_ID>515</BSA_Award_ID>
    <Requirement_Code>99.</Requirement_Code></BSA_Requirement>
  <BSA_Requirement><i>2800</i><BSA_Award_ID>519</BSA_Award_ID>
    <Requirement_Code>05.</Requirement_Code></BSA_Requirement>
  <BSA_Requirement><i>2801</i><BSA_Award_ID>519</BSA_Award_ID>
    <Requirement_Code>06.</Requirement_Code></BSA_Requirement>
  <BSA_Requirement><i>2802</i><BSA_Award_ID>519</BSA_Award_ID>
    <Requirement_Code>07.</Requirement_Code></BSA_Requirement>

  <Advancement_Earned><i>1</i><Person_ID>1</Person_ID><BSA_Award_ID>515</BSA_Award_ID>
    <Date_Earned>4/15/2023 12:00:00 AM</Date_Earned><Date_Awarded />
    <COH_Date>10/1/2023 12:00:00 AM</COH_Date>
    <Last_Update_UTC>10/28/2025 1:37:31 AM</Last_Update_UTC></Advancement_Earned>
  <Advancement_Earned><i>2</i><Person_ID>1</Person_ID><BSA_Award_ID>662</BSA_Award_ID>
    <Date_Earned>5/1/2024 12:00:00 AM</Date_Earned></Advancement_Earned>
  <Advancement_Earned><i>3</i><Person_ID>999</Person_ID><BSA_Award_ID>515</BSA_Award_ID>
    <Date_Earned>5/1/2024 12:00:00 AM</Date_Earned></Advancement_Earned>

  <Advancement_Requirement_Earned><i>10</i><Person_ID>1</Person_ID>
    <BSA_Award_ID>515</BSA_Award_ID><BSA_Requirement_ID>2700</BSA_Requirement_ID>
    <Date_Earned>1/11/2023 12:00:00 AM</Date_Earned>
    <Last_Update_UTC>8/3/2025 4:28:53 AM</Last_Update_UTC></Advancement_Requirement_Earned>
  <Advancement_Requirement_Earned><i>11</i><Person_ID>1</Person_ID>
    <BSA_Award_ID>515</BSA_Award_ID><BSA_Requirement_ID>2701</BSA_Requirement_ID>
    <Date_Earned>2/1/2023 12:00:00 AM</Date_Earned></Advancement_Requirement_Earned>
  <Advancement_Requirement_Earned><i>12</i><Person_ID>1</Person_ID>
    <BSA_Award_ID>515</BSA_Award_ID><BSA_Requirement_ID>2702</BSA_Requirement_ID>
    <Date_Earned>2/2/2023 12:00:00 AM</Date_Earned></Advancement_Requirement_Earned>
  <Advancement_Requirement_Earned><i>13</i><Person_ID>1</Person_ID>
    <BSA_Award_ID>515</BSA_Award_ID><BSA_Requirement_ID>2703</BSA_Requirement_ID>
    <Date_Earned>2/3/2023 12:00:00 AM</Date_Earned></Advancement_Requirement_Earned>
  <Advancement_Requirement_Earned><i>14</i><Person_ID>1</Person_ID>
    <BSA_Award_ID>515</BSA_Award_ID><BSA_Requirement_ID>2700</BSA_Requirement_ID>
    <Date_Earned>3/1/2023 12:00:00 AM</Date_Earned></Advancement_Requirement_Earned>
  <Advancement_Requirement_Earned><i>15</i><Person_ID>2</Person_ID>
    <BSA_Award_ID>519</BSA_Award_ID><BSA_Requirement_ID>2800</BSA_Requirement_ID>
    <Date_Earned />
    <Inserted_Date_Time>8/2/2025 9:28:53 PM</Inserted_Date_Time></Advancement_Requirement_Earned>

  <Merit_Badge><i>20</i><Person_ID>1</Person_ID><BSA_Award_ID>700</BSA_Award_ID>
    <Date_Started>7/1/2023 12:00:00 AM</Date_Started>
    <Date_Earned>7/28/2023 12:00:00 AM</Date_Earned>
    <Merit_Badge_Counselor>Pat Counselor</Merit_Badge_Counselor>
    <Last_Update_UTC>6/20/2026 9:00:23 AM</Last_Update_UTC></Merit_Badge>
  <Merit_Badge><i>21</i><Person_ID>1</Person_ID><BSA_Award_ID>701</BSA_Award_ID>
    <Date_Started>3/1/2026 12:00:00 AM</Date_Started><Date_Earned /></Merit_Badge>
  <Merit_Badge><i>22</i><Person_ID>1</Person_ID><BSA_Award_ID>702</BSA_Award_ID>
    <Date_Earned>1/1/2024 12:00:00 AM</Date_Earned></Merit_Badge>
  <Merit_Badge><i>23</i><Person_ID>1</Person_ID><BSA_Award_ID>700</BSA_Award_ID>
    <Date_Earned>8/1/2023 12:00:00 AM</Date_Earned></Merit_Badge>

  <Requirement_Pending><i>30</i><Person_ID>2</Person_ID><BSA_Award_ID>519</BSA_Award_ID>
    <BSA_Requirement_ID>2801</BSA_Requirement_ID>
    <Date_Completed>11/2/2025 12:00:00 AM</Date_Completed>
    <Review_Status>Pending</Review_Status></Requirement_Pending>
  <Requirement_Pending><i>31</i><Person_ID>2</Person_ID><BSA_Award_ID>519</BSA_Award_ID>
    <BSA_Requirement_ID>2802</BSA_Requirement_ID>
    <Date_Completed>11/3/2025 12:00:00 AM</Date_Completed>
    <Review_Status>Rejected</Review_Status></Requirement_Pending>
  <Requirement_Pending><i>32</i><Person_ID>2</Person_ID><BSA_Award_ID>519</BSA_Award_ID>
    <BSA_Requirement_ID>2800</BSA_Requirement_ID>
    <Date_Completed>11/4/2025 12:00:00 AM</Date_Completed>
    <Review_Status>Approved</Review_Status></Requirement_Pending>
  <Requirement_Pending><i>33</i><Person_ID>2</Person_ID><BSA_Award_ID>700</BSA_Award_ID>
    <BSA_Requirement_ID>2800</BSA_Requirement_ID><Merit_Badge_ID>818</Merit_Badge_ID>
    <Date_Completed>11/5/2025 12:00:00 AM</Date_Completed>
    <Review_Status>Pending</Review_Status></Requirement_Pending>
</database>
"""


@pytest.fixture
def imported(db_session: Session):
    """Seed the real catalog, run the importer on the literal, return (result, session)."""
    load_catalog(db_session)
    root = ET.fromstring(_XML)  # noqa: S314 — test-local literal, not web input
    result = TwhImporter(db_session, _TENANT).run(root)
    return result, db_session


def _member(session: Session, first: str) -> Member:
    return session.query(Member).filter_by(tenant_id=_TENANT, first_name=first).one()


def _rank(session: Session, code: RankCode) -> Rank:
    return session.query(Rank).filter_by(code=code).one()


def _completions(session: Session, member: Member) -> dict[str, MemberRequirementCompletion]:
    rows = session.execute(
        select(MemberRequirementCompletion, Requirement)
        .join(Requirement, MemberRequirementCompletion.requirement_id == Requirement.id)
        .where(MemberRequirementCompletion.member_id == member.id)
    ).all()
    return {req.label: completion for completion, req in rows}


# ---------------------------------------------------------------------------
# Rank awards → MemberRankProgress
# ---------------------------------------------------------------------------


def test_rank_award_imported_with_dates(imported) -> None:
    result, session = imported
    alice = _member(session, "Alice")
    progress = (
        session.query(MemberRankProgress)
        .filter_by(member_id=alice.id, rank_id=_rank(session, RankCode.SCOUT).id)
        .one()
    )
    assert progress.completed_date == date(2023, 4, 15)
    # Date_Awarded blank → falls back to COH_Date.
    assert progress.awarded_date == date(2023, 10, 1)
    assert progress.tenant_id == _TENANT
    assert result.rank_progress == 1


def test_rank_award_provenance(imported) -> None:
    _, session = imported
    alice = _member(session, "Alice")
    progress = (
        session.query(MemberRankProgress)
        .filter_by(member_id=alice.id, rank_id=_rank(session, RankCode.SCOUT).id)
        .one()
    )
    assert progress.source_system == "twh"
    assert progress.source_id == "1"
    assert progress.source_updated_at is not None


def test_palm_award_skipped_with_warning(imported) -> None:
    result, _ = imported
    assert any("Bronze Palm" in w for w in result.warnings)


def test_unknown_person_award_skipped(imported) -> None:
    result, _ = imported
    assert any("unknown person" in w for w in result.warnings)


def test_election_defaults_to_latest_set(imported) -> None:
    _, session = imported
    alice = _member(session, "Alice")
    progress = (
        session.query(MemberRankProgress)
        .filter_by(member_id=alice.id, rank_id=_rank(session, RankCode.SCOUT).id)
        .one()
    )
    # TWH "Current" has no exact version match → latest shipped set (2025).
    assert progress.requirement_set.version == "2025"


# ---------------------------------------------------------------------------
# Requirement sign-offs → MemberRequirementCompletion
# ---------------------------------------------------------------------------


def test_exact_code_match(imported) -> None:
    _, session = imported
    alice = _member(session, "Alice")
    completion = _completions(session, alice)["1a"]
    assert completion.date_completed == date(2023, 1, 11)
    assert completion.status is CompletionStatus.APPROVED
    assert completion.recorded_via is RecordedVia.IMPORT
    assert completion.source_system == "twh"
    assert completion.source_id == "10"


def test_container_signoff_expands_to_leaf_children(imported) -> None:
    _, session = imported
    alice = _member(session, "Alice")
    labels = set(_completions(session, alice))
    # TWH "02." is a container in the 2025 set → all four leaf children credited.
    assert {"2a", "2b", "2c", "2d"} <= labels
    assert "2" not in labels  # the container itself never carries a row


def test_lettered_signoff_falls_back_to_bare_leaf(imported) -> None:
    _, session = imported
    alice = _member(session, "Alice")
    # TWH "6.b" doesn't exist in the 2025 set; bare "6" is a leaf → credited there.
    assert "6" in _completions(session, alice)


def test_unmatched_code_warned_and_skipped(imported) -> None:
    result, session = imported
    alice = _member(session, "Alice")
    assert "99" not in _completions(session, alice)
    assert any("unmatched requirement scout 99" in w for w in result.warnings)


def test_duplicate_signoff_deduped(imported) -> None:
    result, session = imported
    alice = _member(session, "Alice")
    completion = _completions(session, alice)["1a"]
    # First row wins; the repeat is surfaced as a skip.
    assert completion.date_completed == date(2023, 1, 11)
    assert any("duplicate requirement sign-off" in w for w in result.warnings)


def test_missing_date_falls_back_to_inserted_time(imported) -> None:
    _, session = imported
    ben = _member(session, "Ben")
    completion = _completions(session, ben)["5"]
    assert completion.date_completed == date(2025, 8, 2)


def test_progress_created_lazily_for_completions(imported) -> None:
    _, session = imported
    ben = _member(session, "Ben")
    progress = (
        session.query(MemberRankProgress)
        .filter_by(member_id=ben.id, rank_id=_rank(session, RankCode.STAR).id)
        .one()
    )
    # No Advancement_Earned row for Ben — created for his sign-offs, dates open.
    assert progress.completed_date is None
    assert progress.tenant_id == _TENANT


# ---------------------------------------------------------------------------
# Merit badges → MemberMeritBadge
# ---------------------------------------------------------------------------


def test_completed_badge_imported(imported) -> None:
    result, session = imported
    alice = _member(session, "Alice")
    badge = session.query(MeritBadge).filter(MeritBadge.name == "First Aid").one()
    record = (
        session.query(MemberMeritBadge).filter_by(member_id=alice.id, merit_badge_id=badge.id).one()
    )
    assert record.date_started == date(2023, 7, 1)
    assert record.date_completed == date(2023, 7, 28)
    assert record.counselor_name == "Pat Counselor"
    assert record.status is CompletionStatus.APPROVED
    assert record.source_id == "20"
    assert result.merit_badges == 2


def test_version_suffix_stripped_for_badge_match(imported) -> None:
    _, session = imported
    alice = _member(session, "Alice")
    badge = session.query(MeritBadge).filter(MeritBadge.name == "Personal Fitness").one()
    record = (
        session.query(MemberMeritBadge).filter_by(member_id=alice.id, merit_badge_id=badge.id).one()
    )
    # No Date_Earned → a partial in progress.
    assert record.date_completed is None
    assert record.date_started == date(2026, 3, 1)


def test_badge_name_normalization_matches_official_spellings(db_session: Session) -> None:
    """TWH spellings ("Fly Fishing", "Signs, Signals & Codes") match the catalog's
    official names ("Fly-Fishing", "Signs, Signals, and Codes")."""
    load_catalog(db_session)
    xml = """
    <database>
      <Person><i>1</i><Name_First>Ana</Name_First><Name_Last>Angler</Name_Last></Person>
      <BSA_Award><i>10</i><Award_Name>Fly Fishing</Award_Name>
        <Award_Type>Merit Badge</Award_Type></BSA_Award>
      <BSA_Award><i>11</i><Award_Name>Signs, Signals &amp; Codes (2015 rqmts)</Award_Name>
        <Award_Type>Merit Badge</Award_Type></BSA_Award>
      <Merit_Badge><i>1</i><Person_ID>1</Person_ID><BSA_Award_ID>10</BSA_Award_ID>
        <Date_Earned>6/1/2024 12:00:00 AM</Date_Earned></Merit_Badge>
      <Merit_Badge><i>2</i><Person_ID>1</Person_ID><BSA_Award_ID>11</BSA_Award_ID>
        <Date_Earned>7/1/2024 12:00:00 AM</Date_Earned></Merit_Badge>
    </database>
    """
    result = TwhImporter(db_session, _TENANT).run(ET.fromstring(xml))  # noqa: S314
    assert result.merit_badges == 2
    assert not any("not in global catalog" in w for w in result.warnings)


def test_unknown_badge_warned_never_created(imported) -> None:
    result, session = imported
    assert any("Totally Unknown Badge" in w for w in result.warnings)
    # A tenant import must never write the platform catalog.
    assert (
        session.query(MeritBadge).filter(MeritBadge.name == "Totally Unknown Badge").first() is None
    )


def test_duplicate_badge_row_deduped(imported) -> None:
    result, session = imported
    alice = _member(session, "Alice")
    badge = session.query(MeritBadge).filter(MeritBadge.name == "First Aid").one()
    rows = (
        session.query(MemberMeritBadge).filter_by(member_id=alice.id, merit_badge_id=badge.id).all()
    )
    assert len(rows) == 1
    assert any("duplicate merit badge" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Requirement_Pending → in-review completions
# ---------------------------------------------------------------------------


def test_pending_lands_reported(imported) -> None:
    _, session = imported
    ben = _member(session, "Ben")
    completion = _completions(session, ben)["6"]
    assert completion.status is CompletionStatus.REPORTED
    assert completion.date_completed == date(2025, 11, 2)


def test_rejected_lands_rejected(imported) -> None:
    _, session = imported
    ben = _member(session, "Ben")
    completion = _completions(session, ben)["7"]
    assert completion.status is CompletionStatus.REJECTED


def test_approved_pending_skipped_as_duplicate(imported) -> None:
    _, session = imported
    ben = _member(session, "Ben")
    # "05." already earned via Advancement_Requirement_Earned; the Approved
    # pending row must not overwrite or duplicate it.
    completion = _completions(session, ben)["5"]
    assert completion.status is CompletionStatus.APPROVED
    assert completion.date_completed == date(2025, 8, 2)


def test_merit_badge_pending_skipped(imported) -> None:
    result, _ = imported
    assert any("per-MB tracking deferred" in w for w in result.warnings)


# ---------------------------------------------------------------------------
# Catalog precondition
# ---------------------------------------------------------------------------


def test_empty_catalog_skips_all_advancement_with_one_warning(db_session: Session) -> None:
    root = ET.fromstring(_XML)  # noqa: S314 — test-local literal, not web input
    result = TwhImporter(db_session, _TENANT).run(root)
    assert result.rank_progress == 0
    assert result.requirement_completions == 0
    assert result.merit_badges == 0
    assert db_session.query(MemberRankProgress).count() == 0
    assert sum("seed-advancement" in w for w in result.warnings) == 1
    # Roster import still succeeded.
    assert result.members == 2


def test_no_advancement_elements_no_warning(db_session: Session) -> None:
    xml = "<database><Person><i>1</i><Name_First>A</Name_First><Name_Last>B</Name_Last></Person></database>"
    result = TwhImporter(db_session, _TENANT).run(ET.fromstring(xml))  # noqa: S314
    assert not any("seed-advancement" in w for w in result.warnings)
