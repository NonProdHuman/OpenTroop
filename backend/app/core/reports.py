"""Fixed server-side report definitions (#147).

Leaders run a small set of known reports, so v1 ships them as **named
definitions with typed parameters**, not a generic query builder. Each
definition declares its key, title, parameter schema, the permissions it needs
beyond ``report:read``, its columns, and a builder that projects rows.

The roster report's medical bundle flows through the shared
:func:`app.core.member_privacy.redact_medical` helper — exactly the rule
``/members`` applies — so a ``report:read`` holder without ``member:read_medical``
never sees medical fields for members outside their household. Redaction is done
on ``MemberRead`` objects (never the ORM row) before projection.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date, timedelta

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.advancement import (
    compute_member_metrics,
    ordered_ranks,
    rank_leaf_progress,
)
from app.core.groups import resolve_group_members
from app.core.member_privacy import redact_medical
from app.models.advancement import MemberRankProgress, Rank
from app.models.enums import (
    GroupType,
    MemberStatus,
    MemberType,
    Permission,
    RelationshipType,
)
from app.models.group import Group, GroupMember
from app.models.member import Member, MemberRelationship
from app.schemas.member import MemberRead
from app.schemas.report import (
    ReportCatalogEntry,
    ReportColumnSchema,
    ReportParamOption,
    ReportParamSchema,
    ReportValue,
)

# Annual expiry for a BSA medical form: parts A/B and part C are each valid for
# one year from the exam/completion date.
_MEDICAL_VALID_DAYS = 365

_PARENT_EDGES = (RelationshipType.PARENT_OF, RelationshipType.GUARDIAN_OF)


# ---------------------------------------------------------------------------
# Parameter specs + coercion
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportParam:
    """A report parameter: its schema plus how to coerce the raw query value."""

    name: str
    type: str  # "enum" | "int" | "group"
    label: str
    default: ReportValue
    options: tuple[tuple[str, str], ...] | None = None  # (value, label) for enums
    minimum: int | None = None
    maximum: int | None = None

    def schema(self) -> ReportParamSchema:
        return ReportParamSchema(
            name=self.name,
            type=self.type,  # type: ignore[arg-type]
            label=self.label,
            default=self.default,
            options=(
                [ReportParamOption(value=v, label=lbl) for v, lbl in self.options]
                if self.options is not None
                else None
            ),
        )


def _coerce(param: ReportParam, raw: Mapping[str, str]) -> object:
    """Coerce one raw query value for *param*, or raise 422."""
    present = param.name in raw and raw[param.name] != ""
    if param.type == "enum":
        value = raw[param.name] if present else param.default
        valid = {v for v, _ in (param.options or ())}
        if value not in valid:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Invalid value for {param.name!r}: {value!r}",
            )
        return value
    if param.type == "int":
        if not present:
            return param.default
        try:
            number = int(raw[param.name])
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{param.name!r} must be an integer",
            ) from exc
        if param.minimum is not None and number < param.minimum:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{param.name!r} must be ≥ {param.minimum}",
            )
        if param.maximum is not None and number > param.maximum:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{param.name!r} must be ≤ {param.maximum}",
            )
        return number
    if param.type == "group":
        if not present:
            return None
        try:
            return uuid.UUID(raw[param.name])
        except ValueError as exc:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"{param.name!r} must be a group id",
            ) from exc
    raise AssertionError(f"Unknown param type {param.type!r}")  # pragma: no cover


# ---------------------------------------------------------------------------
# Shared value helpers
# ---------------------------------------------------------------------------


def _display_name(m: MemberRead | Member) -> str:
    return f"{m.last_name}, {m.first_name}"


def _iso(value: date | None) -> str | None:
    return value.isoformat() if value is not None else None


def _age(dob: date | None, today: date) -> int | None:
    if dob is None:
        return None
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def _patrol_names(db: Session, member_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    if not member_ids:
        return {}
    rows = db.execute(
        select(GroupMember.member_id, Group.name)
        .join(Group, Group.id == GroupMember.group_id)
        .where(Group.group_type == GroupType.PATROL, GroupMember.member_id.in_(member_ids))
    ).all()
    return {member_id: name for member_id, name in rows}


def _parent_contacts(db: Session, scout_ids: list[uuid.UUID]) -> dict[uuid.UUID, str]:
    """Map each scout id to a display string of their parents' names + contact."""
    if not scout_ids:
        return {}
    rows = db.execute(
        select(MemberRelationship.to_member_id, Member)
        .join(Member, Member.id == MemberRelationship.from_member_id)
        .where(
            MemberRelationship.to_member_id.in_(scout_ids),
            MemberRelationship.relationship_type.in_(_PARENT_EDGES),
        )
    ).all()
    by_scout: dict[uuid.UUID, list[str]] = {}
    for scout_id, parent in rows:
        contact = " / ".join(c for c in (parent.phone, parent.email) if c)
        label = f"{parent.first_name} {parent.last_name}"
        if contact:
            label = f"{label} ({contact})"
        by_scout.setdefault(scout_id, []).append(label)
    return {sid: "; ".join(sorted(labels)) for sid, labels in by_scout.items()}


# ---------------------------------------------------------------------------
# Report builders
# ---------------------------------------------------------------------------


def _build_roster(
    parsed: dict[str, object], caller: Member, permissions: frozenset[Permission], db: Session
) -> list[dict[str, ReportValue]]:
    query = select(Member)
    member_type = parsed["member_type"]
    if member_type != "any":
        query = query.where(Member.member_type == MemberType(str(member_type)))
    membership_status = parsed["status"]
    if membership_status != "any":
        query = query.where(Member.membership_status == MemberStatus(str(membership_status)))
    group_id = parsed["group_id"]
    if isinstance(group_id, uuid.UUID):
        if db.get(Group, group_id) is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Group not found")
        resolved = resolve_group_members(group_id, db)
        query = query.where(Member.id.in_(resolved))

    members = list(db.scalars(query.order_by(Member.last_name, Member.first_name)))
    items = [MemberRead.model_validate(m) for m in members]
    # Parity with /members: null the medical bundle for members outside the
    # caller's household unless they hold member:read_medical.
    redact_medical(items, caller, permissions, db)

    today = date.today()
    patrol_by = _patrol_names(db, [it.id for it in items])
    parent_by = _parent_contacts(db, [it.id for it in items if it.member_type == MemberType.SCOUT])

    rows: list[dict[str, ReportValue]] = []
    for it in items:
        emergency = None
        if it.emergency_contact_1_name:
            emergency = it.emergency_contact_1_name
            if it.emergency_contact_1_phone:
                emergency = f"{emergency} ({it.emergency_contact_1_phone})"
        rows.append(
            {
                "name": _display_name(it),
                "member_type": it.member_type.value,
                "membership_status": it.membership_status.value,
                "patrol": patrol_by.get(it.id),
                "bsa_id": it.bsa_id,
                "age": _age(it.date_of_birth, today),
                "date_of_birth": _iso(it.date_of_birth),
                "phone": it.phone,
                "email": it.email,
                "allergies": it.allergies,
                "dietary_restrictions": it.dietary_restrictions,
                "emergency_contact": emergency,
                "parents": parent_by.get(it.id),
            }
        )
    return rows


def _build_swim(
    parsed: dict[str, object], caller: Member, permissions: frozenset[Permission], db: Session
) -> list[dict[str, ReportValue]]:
    query = select(Member)
    membership_status = parsed["status"]
    if membership_status != "any":
        query = query.where(Member.membership_status == MemberStatus(str(membership_status)))
    stale_months = int(str(parsed["stale_months"]))

    members = list(db.scalars(query.order_by(Member.last_name, Member.first_name)))
    patrol_by = _patrol_names(db, [m.id for m in members])
    today = date.today()
    stale_days = int(stale_months * 30.4375)

    rows: list[dict[str, ReportValue]] = []
    for m in members:
        stale = m.swim_date is None or (today - m.swim_date).days > stale_days
        rows.append(
            {
                "name": _display_name(m),
                "member_type": m.member_type.value,
                "patrol": patrol_by.get(m.id),
                "swim_classification": m.swim_classification.value,
                "swim_date": _iso(m.swim_date),
                "stale": stale,
            }
        )
    return rows


def _build_medical(
    parsed: dict[str, object], caller: Member, permissions: frozenset[Permission], db: Session
) -> list[dict[str, ReportValue]]:
    horizon_days = int(str(parsed["horizon_days"]))
    form_part = str(parsed["form_part"])  # "ab" | "c" | "both"
    check_ab = form_part in ("ab", "both")
    check_c = form_part in ("c", "both")
    today = date.today()

    members = list(db.scalars(select(Member).order_by(Member.last_name, Member.first_name)))

    def days_until(form_date: date | None) -> int | None:
        if form_date is None:
            return None
        return (form_date + timedelta(days=_MEDICAL_VALID_DAYS) - today).days

    rows: list[dict[str, ReportValue]] = []
    for m in members:
        ab_days = days_until(m.medical_form_ab_date) if check_ab else None
        c_days = days_until(m.medical_form_c_date) if check_c else None
        # A part is "attention needed" when it is missing or within the horizon
        # (including already-overdue: negative days).
        ab_flag = check_ab and (
            m.medical_form_ab_date is None or (ab_days is not None and ab_days <= horizon_days)
        )
        c_flag = check_c and (
            m.medical_form_c_date is None or (c_days is not None and c_days <= horizon_days)
        )
        if not (ab_flag or c_flag):
            continue
        rows.append(
            {
                "name": _display_name(m),
                "member_type": m.member_type.value,
                "medical_form_ab_date": _iso(m.medical_form_ab_date) if check_ab else None,
                "ab_days_until": ab_days,
                "medical_form_c_date": _iso(m.medical_form_c_date) if check_c else None,
                "c_days_until": c_days,
            }
        )
    return rows


def _build_advancement(
    parsed: dict[str, object], caller: Member, permissions: frozenset[Permission], db: Session
) -> list[dict[str, ReportValue]]:
    query = select(Member).where(Member.member_type == MemberType.SCOUT)
    membership_status = parsed["status"]
    if membership_status != "any":
        query = query.where(Member.membership_status == MemberStatus(str(membership_status)))
    scouts = list(db.scalars(query.order_by(Member.last_name, Member.first_name)))
    if not scouts:
        return []
    scout_ids = [s.id for s in scouts]

    ranks = ordered_ranks(db)
    rank_by_id = {r.id: r for r in ranks}
    patrol_by = _patrol_names(db, scout_ids)

    # Current rank per scout: the highest sort_order rank with a board-of-review
    # date — the same rule as /advancement/scouts and the GroupRule rank dimension.
    completed_rows = db.execute(
        select(
            MemberRankProgress.member_id,
            MemberRankProgress.rank_id,
            MemberRankProgress.completed_date,
        ).where(
            MemberRankProgress.member_id.in_(scout_ids),
            MemberRankProgress.completed_date.is_not(None),
        )
    ).all()
    current: dict[uuid.UUID, tuple[int, Rank, date]] = {}
    for member_id, rank_id, completed_date in completed_rows:
        rank = rank_by_id.get(rank_id)
        if rank is None or completed_date is None:
            continue
        best = current.get(member_id)
        if best is None or rank.sort_order > best[0]:
            current[member_id] = (rank.sort_order, rank, completed_date)

    rows: list[dict[str, ReportValue]] = []
    for scout in scouts:
        held = current.get(scout.id)
        current_rank = held[1] if held else None
        last_bor = held[2] if held else None
        next_rank = _next_rank(ranks, current_rank)
        percent: int | None = None
        if next_rank is not None:
            completed, total = rank_leaf_progress(scout.id, next_rank.id, db)
            percent = round(completed / total * 100) if total else 0
        metrics = compute_member_metrics(scout.id, db)
        rows.append(
            {
                "name": _display_name(scout),
                "patrol": patrol_by.get(scout.id),
                "current_rank": current_rank.name if current_rank else None,
                "next_rank": next_rank.name if next_rank else None,
                "next_rank_percent": percent,
                "merit_badge_count": metrics.badge_count,
                "last_bor_date": _iso(last_bor),
            }
        )
    return rows


def _next_rank(ranks: list[Rank], current: Rank | None) -> Rank | None:
    """The rank a scout is working toward: the first rank above their current one
    (or the lowest rank when they hold none). None once the top rank is earned."""
    if not ranks:
        return None
    if current is None:
        return ranks[0]
    for rank in ranks:
        if rank.sort_order > current.sort_order:
            return rank
    return None


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

Builder = Callable[
    [dict[str, object], Member, frozenset[Permission], Session],
    list[dict[str, ReportValue]],
]


@dataclass(frozen=True)
class ReportDefinition:
    key: str
    title: str
    description: str
    columns: tuple[ReportColumnSchema, ...]
    params: tuple[ReportParam, ...]
    builder: Builder
    extra_permissions: frozenset[Permission] = field(default_factory=frozenset)

    def runnable_by(self, permissions: frozenset[Permission]) -> bool:
        return self.extra_permissions <= permissions

    def catalog_entry(self, permissions: frozenset[Permission]) -> ReportCatalogEntry:
        return ReportCatalogEntry(
            key=self.key,
            title=self.title,
            description=self.description,
            params=[p.schema() for p in self.params],
            runnable=self.runnable_by(permissions),
        )

    def parse_params(self, raw: Mapping[str, str]) -> dict[str, object]:
        return {p.name: _coerce(p, raw) for p in self.params}


def _col(key: str, label: str) -> ReportColumnSchema:
    return ReportColumnSchema(key=key, label=label)


_MEMBER_TYPE_OPTIONS = (("any", "Any"), ("scout", "Scouts"), ("adult", "Adults"))
_STATUS_OPTIONS = (
    ("active", "Active"),
    ("inactive", "Inactive"),
    ("alumni", "Alumni"),
    ("any", "Any"),
)
_FORM_PART_OPTIONS = (("both", "Parts A/B and C"), ("ab", "Parts A/B"), ("c", "Part C"))


REPORTS: dict[str, ReportDefinition] = {
    "roster": ReportDefinition(
        key="roster",
        title="Roster",
        description="Members with contact info and, for scouts, their parents/guardians.",
        columns=(
            _col("name", "Name"),
            _col("member_type", "Type"),
            _col("membership_status", "Status"),
            _col("patrol", "Patrol"),
            _col("bsa_id", "BSA ID"),
            _col("age", "Age"),
            _col("date_of_birth", "Date of birth"),
            _col("phone", "Phone"),
            _col("email", "Email"),
            _col("allergies", "Allergies"),
            _col("dietary_restrictions", "Dietary"),
            _col("emergency_contact", "Emergency contact"),
            _col("parents", "Parents/guardians"),
        ),
        params=(
            ReportParam("member_type", "enum", "Member type", "any", options=_MEMBER_TYPE_OPTIONS),
            ReportParam("status", "enum", "Membership status", "active", options=_STATUS_OPTIONS),
            ReportParam("group_id", "group", "Group", None),
        ),
        builder=_build_roster,
    ),
    "swim": ReportDefinition(
        key="swim",
        title="Swim classification",
        description="BSA swim classifications and stale swim checks for the aquatics pre-check.",
        columns=(
            _col("name", "Name"),
            _col("member_type", "Type"),
            _col("patrol", "Patrol"),
            _col("swim_classification", "Classification"),
            _col("swim_date", "Swim check date"),
            _col("stale", "Stale"),
        ),
        params=(
            ReportParam("status", "enum", "Membership status", "active", options=_STATUS_OPTIONS),
            ReportParam(
                "stale_months",
                "int",
                "Stale after (months)",
                12,
                minimum=1,
                maximum=120,
            ),
        ),
        builder=_build_swim,
    ),
    "medical": ReportDefinition(
        key="medical",
        title="Medical-form expiry",
        description="Members whose BSA medical forms are missing, expiring soon, or overdue.",
        columns=(
            _col("name", "Name"),
            _col("member_type", "Type"),
            _col("medical_form_ab_date", "A/B date"),
            _col("ab_days_until", "A/B days left"),
            _col("medical_form_c_date", "C date"),
            _col("c_days_until", "C days left"),
        ),
        params=(
            ReportParam("horizon_days", "int", "Horizon (days)", 90, minimum=0, maximum=3650),
            ReportParam("form_part", "enum", "Form part", "both", options=_FORM_PART_OPTIONS),
        ),
        builder=_build_medical,
        extra_permissions=frozenset({Permission.MEMBER_READ_MEDICAL}),
    ),
    "advancement": ReportDefinition(
        key="advancement",
        title="Advancement summary",
        description="Per scout: current rank, next-rank progress, merit badges, and last board of review.",
        columns=(
            _col("name", "Name"),
            _col("patrol", "Patrol"),
            _col("current_rank", "Current rank"),
            _col("next_rank", "Next rank"),
            _col("next_rank_percent", "Next rank %"),
            _col("merit_badge_count", "Merit badges"),
            _col("last_bor_date", "Last BOR"),
        ),
        params=(
            ReportParam("status", "enum", "Membership status", "active", options=_STATUS_OPTIONS),
        ),
        builder=_build_advancement,
    ),
}
