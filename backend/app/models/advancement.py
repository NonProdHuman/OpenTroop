"""Advancement catalog — platform-global BSA reference data (Pillar 4, GH-92).

Rank requirements are BSA facts, identical for every troop, so the catalog lives
on ``PlatformBase`` (no ``tenant_id``): read-only to tenants, exempt from RLS like
the other platform tables, and seeded from curated data files by
``uv run seed-advancement`` (see ``app/core/advancement_catalog.py``).

Versioning model (the load-bearing decision from GH-92):

- A :class:`RequirementSet` is **one complete copy** of a rank's requirements for
  one BSA version year — no delta/patch modeling. "What does scout X need" is a
  single-set query; renumbering across years can't corrupt anything.
- A scout's per-rank *version election* (Phase 2, ``MemberRankProgress``) points at
  exactly one set. :attr:`Requirement.stable_key` is the curated cross-version
  identity that lets completions remap when a scout switches sets.

Tenant-scoped tracking tables (``MemberRankProgress`` et al.) arrive in Phase 2 —
this module is deliberately catalog-only.
"""

from __future__ import annotations

import uuid
from datetime import date
from typing import Any

from sqlalchemy import Boolean, Date, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy import Enum as SAEnum
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import PlatformBase
from app.models.enums import RankCode
from app.models.types import JsonObjectList


class Rank(PlatformBase):
    """One of the seven Scouts BSA ranks. Global reference data."""

    __tablename__ = "ranks"

    code: Mapped[RankCode] = mapped_column(
        SAEnum(RankCode, values_callable=lambda x: [e.value for e in x]),
        unique=True,
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Earn-in-sequence ordering (Scout=1 … Eagle=7).
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    requirement_sets: Mapped[list[RequirementSet]] = relationship(
        "RequirementSet", back_populates="rank"
    )


class RequirementSet(PlatformBase):
    """A rank's complete requirement list for one BSA version year.

    Each set is a full copy — sharing/deltas are deliberately avoided so version
    switches and renumbering stay mechanically simple (GH-92).
    """

    __tablename__ = "requirement_sets"
    __table_args__ = (
        UniqueConstraint("rank_id", "version", name="uq_requirement_sets_rank_version"),
    )

    rank_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ranks.id"), nullable=False, index=True)
    # BSA version year, e.g. "2025". String — BSA occasionally issues mid-year errata.
    version: Mapped[str] = mapped_column(String(16), nullable=False)
    effective_date: Mapped[date | None] = mapped_column(Date, nullable=True)

    rank: Mapped[Rank] = relationship("Rank", back_populates="requirement_sets")
    requirements: Mapped[list[Requirement]] = relationship(
        "Requirement", back_populates="requirement_set"
    )


class Requirement(PlatformBase):
    """One requirement line within a set — numbered item or lettered sub-item.

    ``letter`` is ``""`` (never NULL) for numbered items so the uniqueness
    constraint is airtight on Postgres, where NULLs never collide. A numbered
    item that has lettered children is a *container* ("Do the following:") whose
    completion is derived from its children — only leaves get completion rows.
    """

    __tablename__ = "requirements"
    __table_args__ = (
        UniqueConstraint(
            "requirement_set_id", "number", "letter", name="uq_requirements_set_number_letter"
        ),
    )

    requirement_set_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("requirement_sets.id"), nullable=False, index=True
    )
    number: Mapped[str] = mapped_column(String(8), nullable=False)
    letter: Mapped[str] = mapped_column(String(4), nullable=False, default="")
    # Container linkage: a lettered item points at its numbered parent within the
    # same set. Assigned by the seed loader; NULL for top-level numbered items.
    parent_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("requirements.id"), nullable=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # Full official requirement text, stored verbatim (GH-92 decision 4).
    text: Mapped[str] = mapped_column(Text, nullable=False)
    # Curated cross-version identity: the same slug on two sets' requirements means
    # "substantively the same requirement" even if BSA renumbered it — the remap key
    # for version switches. Best-effort curation; NULL when no counterpart exists.
    stable_key: Mapped[str | None] = mapped_column(String(120), nullable=True, index=True)
    # Metric conditions (JSON list, AND-ed): {"kind", "threshold", "window"} — see
    # MetricKind / MetricWindow. NULL = plain sign-off item with no progress meter.
    metrics: Mapped[list[dict[str, Any]] | None] = mapped_column(JsonObjectList, nullable=True)
    # True only when the official condition is FULLY computable from the metrics —
    # the auto-credit engine (Phase 3) records completions for these; metric-bearing
    # requirements with auto_credit=False render as progress meters needing sign-off.
    auto_credit: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    requirement_set: Mapped[RequirementSet] = relationship(
        "RequirementSet", back_populates="requirements"
    )
    parent: Mapped[Requirement | None] = relationship("Requirement", remote_side="Requirement.id")

    @property
    def label(self) -> str:
        """Display label, e.g. ``"1a"`` or ``"7"``."""
        return f"{self.number}{self.letter}"


class MeritBadge(PlatformBase):
    """A merit badge in the global catalog. Completions only in Phase 1/2 (GH-92).

    ``eagle_required`` drives the ``merit_badge_count_eagle_required`` metric.
    Discontinued badges stay in the catalog (historical completions reference
    them) with ``is_discontinued=True``.
    """

    __tablename__ = "merit_badges"

    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    eagle_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_discontinued: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
