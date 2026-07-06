"""Advancement catalog: global rank/requirement/merit-badge tables + capability flags.

Pillar 4 Phase 1 (GH-92 / GH-169):

1. Platform-global catalog tables — ``ranks``, ``requirement_sets``,
   ``requirements``, ``merit_badges``. These are BSA reference data shared by
   every tenant, so they carry **no tenant_id and no RLS** (like users/tenants);
   the tenant plane needs read access, the seed CLI writes via the owner role.
2. ``event_types.counts_as_activity`` — whether attended events of this type
   count toward "participate in N activities" requirements. Backfills the two
   seeded types that should not count (Meeting, Court of Honor).
3. ``positions.counts_for_por`` — whether terms in the position accrue the
   position-of-responsibility tenure metric. Backfills the seeded BSA POR list.

Revision ID: f0a1b2c3d4e5
Revises: e5f6a7b8c9d0
Create Date: 2026-07-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "f0a1b2c3d4e5"
down_revision: Union[str, None] = "e5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_CATALOG_TABLES = ["ranks", "requirement_sets", "requirements", "merit_badges"]

# Seeded scout positions whose terms count as a position of responsibility.
_POR_POSITION_SLUGS = (
    "senior-patrol-leader",
    "assistant-senior-patrol-leader",
    "patrol-leader",
    "scribe",
    "troop-guide",
    "quartermaster",
    "historian",
    "librarian",
    "bugler",
    "oa-representative",
)


def _rank_code_enum() -> sa.Enum:
    return sa.Enum(
        "scout",
        "tenderfoot",
        "second_class",
        "first_class",
        "star",
        "life",
        "eagle",
        name="rankcode",
    )


def upgrade() -> None:
    op.create_table(
        "ranks",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", _rank_code_enum(), nullable=False),
        sa.Column("name", sa.String(length=80), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_index(op.f("ix_ranks_is_deleted"), "ranks", ["is_deleted"], unique=False)

    op.create_table(
        "requirement_sets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("rank_id", sa.Uuid(), nullable=False),
        sa.Column("version", sa.String(length=16), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["rank_id"], ["ranks.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("rank_id", "version", name="uq_requirement_sets_rank_version"),
    )
    op.create_index(
        op.f("ix_requirement_sets_rank_id"), "requirement_sets", ["rank_id"], unique=False
    )
    op.create_index(
        op.f("ix_requirement_sets_is_deleted"), "requirement_sets", ["is_deleted"], unique=False
    )

    op.create_table(
        "requirements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("requirement_set_id", sa.Uuid(), nullable=False),
        sa.Column("number", sa.String(length=8), nullable=False),
        sa.Column("letter", sa.String(length=4), nullable=False),
        sa.Column("parent_id", sa.Uuid(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("stable_key", sa.String(length=120), nullable=True),
        sa.Column("metrics", sa.JSON(), nullable=True),
        sa.Column("auto_credit", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["parent_id"], ["requirements.id"]),
        sa.ForeignKeyConstraint(["requirement_set_id"], ["requirement_sets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "requirement_set_id", "number", "letter", name="uq_requirements_set_number_letter"
        ),
    )
    op.create_index(
        op.f("ix_requirements_requirement_set_id"),
        "requirements",
        ["requirement_set_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_requirements_stable_key"), "requirements", ["stable_key"], unique=False
    )
    op.create_index(
        op.f("ix_requirements_is_deleted"), "requirements", ["is_deleted"], unique=False
    )

    op.create_table(
        "merit_badges",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("eagle_required", sa.Boolean(), nullable=False),
        sa.Column("is_discontinued", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name"),
    )
    op.create_index(
        op.f("ix_merit_badges_is_deleted"), "merit_badges", ["is_deleted"], unique=False
    )

    # Catalog tables are platform-global: no RLS, read access for the tenant plane,
    # full DML for the admin plane / seed CLI. Postgres-only (SQLite tests use
    # metadata.create_all and have no roles).
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        for table_name in _CATALOG_TABLES:
            op.execute(
                sa.text(f"GRANT SELECT ON {table_name} TO opentroop_app")  # noqa: S608
            )
            op.execute(
                sa.text(
                    f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table_name} TO opentroop_admin"  # noqa: S608
                )
            )

    # Capability flags on existing tenant tables.
    op.add_column(
        "event_types",
        sa.Column(
            "counts_as_activity", sa.Boolean(), nullable=False, server_default=sa.true()
        ),
    )
    op.add_column(
        "positions",
        sa.Column("counts_for_por", sa.Boolean(), nullable=False, server_default=sa.false()),
    )

    # Backfill seeded system rows to the GH-92 defaults. Tenant-customized rows
    # (is_system false) keep the column default.
    op.execute(
        sa.text(
            "UPDATE event_types SET counts_as_activity = false "
            "WHERE is_system = true AND name IN ('Meeting', 'Court of Honor')"
        )
    )
    por_slugs = ", ".join(f"'{slug}'" for slug in _POR_POSITION_SLUGS)
    op.execute(
        sa.text(
            f"UPDATE positions SET counts_for_por = true "  # noqa: S608 — constant slug list
            f"WHERE is_system = true AND slug IN ({por_slugs})"
        )
    )


def downgrade() -> None:
    op.drop_column("positions", "counts_for_por")
    op.drop_column("event_types", "counts_as_activity")
    op.drop_index(op.f("ix_merit_badges_is_deleted"), table_name="merit_badges")
    op.drop_table("merit_badges")
    op.drop_index(op.f("ix_requirements_is_deleted"), table_name="requirements")
    op.drop_index(op.f("ix_requirements_stable_key"), table_name="requirements")
    op.drop_index(op.f("ix_requirements_requirement_set_id"), table_name="requirements")
    op.drop_table("requirements")
    op.drop_index(op.f("ix_requirement_sets_is_deleted"), table_name="requirement_sets")
    op.drop_index(op.f("ix_requirement_sets_rank_id"), table_name="requirement_sets")
    op.drop_table("requirement_sets")
    op.drop_index(op.f("ix_ranks_is_deleted"), table_name="ranks")
    op.drop_table("ranks")
    _rank_code_enum().drop(op.get_bind(), checkfirst=True)
