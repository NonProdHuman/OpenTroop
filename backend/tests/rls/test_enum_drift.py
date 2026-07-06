# ruff: noqa: S608
"""Native-enum drift guard (GH-145 hotfix regression test).

Adding a member to a Python enum whose column is a native Postgres enum does
NOT extend the database type — that takes an `ALTER TYPE … ADD VALUE`
migration. The SQLite suite can't catch the gap (SQLite rebuilds its CHECK
constraint from the current Python enum), which is exactly how the photo
permissions broke tenant provisioning in opentroop.dev: `seed_default_rbac`
inserted `PHOTO_READ` into a `permission` type that had never heard of it.

This test compares every `sa.Enum` column type in the ORM metadata against the
labels actually present in the migrated database, so ANY future enum member
added without its migration fails the Postgres CI tier on the PR.
"""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy import text

from app.models import Base


def _metadata_enum_labels() -> dict[str, set[str]]:
    """Every named sa.Enum used by a mapped column → the labels it would emit."""
    enums: dict[str, set[str]] = {}
    for table in Base.metadata.tables.values():
        for column in table.columns:
            if isinstance(column.type, sa.Enum) and column.type.name:
                enums.setdefault(column.type.name, set()).update(column.type.enums)
    return enums


def test_pg_enum_types_cover_every_python_member(owner_conn) -> None:  # type: ignore[no-untyped-def]
    expected = _metadata_enum_labels()
    assert expected, "no native enums found in metadata — test wiring broken"

    rows = owner_conn.execute(
        text(
            """
            SELECT t.typname, e.enumlabel
            FROM pg_type t
            JOIN pg_enum e ON e.enumtypid = t.oid
            """
        )
    ).all()
    db_labels: dict[str, set[str]] = {}
    for typname, label in rows:
        db_labels.setdefault(typname, set()).add(label)

    problems: list[str] = []
    for name, labels in sorted(expected.items()):
        if name not in db_labels:
            problems.append(f"enum type '{name}' missing from the database entirely")
            continue
        missing = labels - db_labels[name]
        if missing:
            problems.append(
                f"enum '{name}' is missing labels {sorted(missing)} — "
                f"add an `ALTER TYPE {name} ADD VALUE` migration"
            )
    assert not problems, "; ".join(problems)
