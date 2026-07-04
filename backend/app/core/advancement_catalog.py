"""Advancement catalog seed pipeline (GH-92).

Loads the curated data files in ``backend/data/advancement/`` into the global
catalog tables — the "no scraping" answer to catalog collection: requirement
text is transcribed once per BSA version year, reviewed as a normal PR, and
this loader upserts it idempotently (dev bootstrap, deploy step, self-host).

Upsert semantics:

- ``Rank`` keyed by ``code``; ``RequirementSet`` by ``(rank, version)``;
  ``Requirement`` by ``(set, number, letter)``; ``MeritBadge`` by ``name``.
- Text/metric/flag corrections update rows **in place** — history is carried by
  completions pointing at requirement ids, so fixing a typo never forks a row.
- A requirement present in the DB but absent from its set's file is
  **soft-deleted** (and revived if it reappears): the files own the catalog.
  Merit badges are never deleted — retire one by flipping ``is_discontinued``
  in the file.

Data-file schemas are documented in the module they ship with
(``backend/data/advancement/``) and validated here — a malformed metric
condition fails the load loudly rather than seeding a broken meter.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.advancement import MeritBadge, Rank, Requirement, RequirementSet
from app.models.enums import MetricKind, MetricWindow, RankCode

DATA_DIR = Path(__file__).resolve().parents[2] / "data" / "advancement"


@dataclass
class CatalogLoadStats:
    """Counts of what a load actually changed — surfaced by the CLI."""

    ranks: int = 0
    requirement_sets: int = 0
    requirements_created: int = 0
    requirements_updated: int = 0
    requirements_removed: int = 0
    merit_badges_created: int = 0
    merit_badges_updated: int = 0
    files: list[str] = field(default_factory=list)


def _validate_metrics(metrics: object, where: str) -> list[dict[str, Any]] | None:
    if metrics is None:
        return None
    if not isinstance(metrics, list) or not metrics:
        raise ValueError(f"{where}: metrics must be null or a non-empty list")
    validated: list[dict[str, Any]] = []
    for condition in metrics:
        if not isinstance(condition, dict):
            raise ValueError(f"{where}: metric condition must be an object")
        try:
            kind = MetricKind(condition["kind"])
            window = MetricWindow(condition.get("window", "any"))
            threshold = condition["threshold"]
        except (KeyError, ValueError) as exc:
            raise ValueError(f"{where}: invalid metric condition {condition!r}") from exc
        if not isinstance(threshold, int | float) or threshold <= 0:
            raise ValueError(f"{where}: threshold must be a positive number")
        validated.append({"kind": kind.value, "threshold": threshold, "window": window.value})
    return validated


def _upsert_requirement_set(
    session: Session,
    rank: Rank,
    version: str,
    effective_date: date | None,
    items: list[dict[str, Any]],
    stats: CatalogLoadStats,
) -> None:
    req_set = session.scalar(
        select(RequirementSet).where(
            RequirementSet.rank_id == rank.id, RequirementSet.version == version
        )
    )
    if req_set is None:
        req_set = RequirementSet(rank_id=rank.id, version=version, effective_date=effective_date)
        session.add(req_set)
        session.flush()
        stats.requirement_sets += 1
    elif req_set.effective_date != effective_date:
        req_set.effective_date = effective_date

    existing = {
        (r.number, r.letter): r
        for r in session.scalars(
            select(Requirement).where(Requirement.requirement_set_id == req_set.id)
        )
    }
    seen: set[tuple[str, str]] = set()
    by_key: dict[tuple[str, str], Requirement] = {}

    for order, item in enumerate(items):
        number = str(item["number"])
        letter = str(item.get("letter", ""))
        where = f"{rank.code.value} v{version} req {number}{letter}"
        if (number, letter) in seen:
            raise ValueError(f"{where}: duplicate (number, letter) in data file")
        seen.add((number, letter))
        metrics = _validate_metrics(item.get("metrics"), where)
        text = str(item["text"])
        stable_key = item.get("stable_key") or None
        auto_credit = bool(item.get("auto_credit", False))

        row = existing.get((number, letter))
        if row is None:
            row = Requirement(
                requirement_set_id=req_set.id,
                number=number,
                letter=letter,
                sort_order=order,
                text=text,
                stable_key=stable_key,
                metrics=metrics,
                auto_credit=auto_credit,
            )
            session.add(row)
            stats.requirements_created += 1
        else:
            changed = (
                row.text != text
                or row.stable_key != stable_key
                or row.metrics != metrics
                or row.auto_credit != auto_credit
                or row.sort_order != order
                or row.is_deleted
            )
            if changed:
                row.text = text
                row.stable_key = stable_key
                row.metrics = metrics
                row.auto_credit = auto_credit
                row.sort_order = order
                row.is_deleted = False
                stats.requirements_updated += 1
        by_key[(number, letter)] = row

    # The files own the catalog: tombstone rows that fell out of the data file.
    for key, row in existing.items():
        if key not in seen and not row.is_deleted:
            row.is_deleted = True
            stats.requirements_removed += 1

    session.flush()
    # Container linkage: a lettered item hangs off the bare-numbered item when one
    # exists ("1a" → "1"). Assigned after flush so new parents have ids.
    for (number, letter), row in by_key.items():
        parent = by_key.get((number, "")) if letter else None
        parent_id = parent.id if parent is not None else None
        if row.parent_id != parent_id:
            row.parent_id = parent_id
    session.flush()


def _load_ranks_file(session: Session, path: Path, stats: CatalogLoadStats) -> None:
    data = json.loads(path.read_text())
    version = str(data["version"])
    effective = date.fromisoformat(data["effective_date"]) if data.get("effective_date") else None
    for rank_data in data["ranks"]:
        code = RankCode(rank_data["code"])
        rank = session.scalar(select(Rank).where(Rank.code == code))
        if rank is None:
            rank = Rank(
                code=code, name=str(rank_data["name"]), sort_order=int(rank_data["sort_order"])
            )
            session.add(rank)
            session.flush()
            stats.ranks += 1
        else:
            rank.name = str(rank_data["name"])
            rank.sort_order = int(rank_data["sort_order"])
        _upsert_requirement_set(session, rank, version, effective, rank_data["requirements"], stats)
    stats.files.append(path.name)


def _load_merit_badges(session: Session, path: Path, stats: CatalogLoadStats) -> None:
    data = json.loads(path.read_text())
    existing = {b.name: b for b in session.scalars(select(MeritBadge))}
    for badge_data in data["badges"]:
        name = str(badge_data["name"])
        eagle_required = bool(badge_data.get("eagle_required", False))
        is_discontinued = bool(badge_data.get("is_discontinued", False))
        badge = existing.get(name)
        if badge is None:
            session.add(
                MeritBadge(
                    name=name, eagle_required=eagle_required, is_discontinued=is_discontinued
                )
            )
            stats.merit_badges_created += 1
        elif badge.eagle_required != eagle_required or badge.is_discontinued != is_discontinued:
            badge.eagle_required = eagle_required
            badge.is_discontinued = is_discontinued
            stats.merit_badges_updated += 1
    session.flush()
    stats.files.append(path.name)


def load_catalog(session: Session, data_dir: Path = DATA_DIR) -> CatalogLoadStats:
    """Upsert every ``ranks-*.json`` plus ``merit-badges.json`` from *data_dir*.

    Flushes but does not commit — the caller (CLI, provisioning, tests) owns the
    transaction boundary.
    """
    stats = CatalogLoadStats()
    for path in sorted(data_dir.glob("ranks-*.json")):
        _load_ranks_file(session, path, stats)
    badges_path = data_dir / "merit-badges.json"
    if badges_path.exists():
        _load_merit_badges(session, badges_path, stats)
    return stats
