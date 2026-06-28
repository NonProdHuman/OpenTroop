"""add_dynamic_group_rules

Revision ID: 7f9bd698851b
Revises: c1d2e3f4a5b6
Create Date: 2026-06-28 14:20:31.136854

"""
from __future__ import annotations

import json
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import uuid6

from app.core import rls

# revision identifiers, used by Alembic.
revision: str = '7f9bd698851b'
down_revision: Union[str, None] = 'c1d2e3f4a5b6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _tracked_columns() -> list[sa.Column]:
    """Fresh copies of the standard TrackedBase columns for each create_table call."""
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
    ]


def _standard_indexes(table: str) -> None:
    op.create_index(op.f(f"ix_{table}_is_deleted"), table, ["is_deleted"], unique=False)
    op.create_index(op.f(f"ix_{table}_tenant_id"), table, ["tenant_id"], unique=False)


def upgrade() -> None:
    bind = op.get_bind()

    # --- Add rule_logic to groups ---
    rule_logic_enum = sa.Enum("and", "or", name="rulelogic")
    op.add_column(
        "groups",
        sa.Column("rule_logic", rule_logic_enum, nullable=False, server_default="and")
    )

    # --- Create group_rules ---
    rule_dimension_enum = sa.Enum(
        "member_type",
        "membership_status",
        "oa_member",
        "oa_active",
        "position",
        "group_member",
        "relationship",
        "rank",
        name="ruledimension",
    )
    op.create_table(
        "group_rules",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("dimension", rule_dimension_enum, nullable=False),
        sa.Column("values", sa.JSON(), nullable=True),
        *_tracked_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.UniqueConstraint("group_id", "dimension", name="uq_group_rules_group_dimension"),
    )
    op.create_index(op.f("ix_group_rules_group_id"), "group_rules", ["group_id"], unique=False)
    _standard_indexes("group_rules")
    rls.enable_rls_for(op, "group_rules")

    # --- Migrate existing position rules ---
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT tenant_id, group_id, position_id FROM group_position_rules WHERE is_deleted = false"
        )
    ).fetchall()

    from collections import defaultdict
    rules_by_group = defaultdict(list)
    for row in rows:
        tenant_id = str(row[0])
        group_id = str(row[1])
        position_id = str(row[2])
        rules_by_group[(tenant_id, group_id)].append(position_id)

    for (tenant_id, group_id), position_ids in rules_by_group.items():
        rule_id = str(uuid6.uuid7())
        values_json = json.dumps(position_ids)
        connection.execute(
            sa.text(
                """
                INSERT INTO group_rules (id, tenant_id, group_id, dimension, values, created_at, updated_at, is_deleted)
                VALUES (:id, :tenant_id, :group_id, :dimension, :values, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, false)
                """
            ),
            {
                "id": rule_id,
                "tenant_id": tenant_id,
                "group_id": group_id,
                "dimension": "position",
                "values": values_json,
            }
        )

    # --- Drop group_position_rules ---
    rls.disable_rls_for(op, "group_position_rules")
    op.drop_table("group_position_rules")


def downgrade() -> None:
    bind = op.get_bind()

    # --- Recreate group_position_rules ---
    op.create_table(
        "group_position_rules",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=False),
        *_tracked_columns(),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "group_id", "position_id", name="uq_group_position_rules_group_position"
        ),
    )
    op.create_index(
        op.f("ix_group_position_rules_group_id"),
        "group_position_rules",
        ["group_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_group_position_rules_position_id"),
        "group_position_rules",
        ["position_id"],
        unique=False,
    )
    _standard_indexes("group_position_rules")
    rls.enable_rls_for(op, "group_position_rules")

    # --- Migrate position rules data back ---
    connection = op.get_bind()
    rows = connection.execute(
        sa.text(
            "SELECT tenant_id, group_id, values FROM group_rules WHERE dimension = 'position' AND is_deleted = false"
        )
    ).fetchall()

    for row in rows:
        tenant_id = str(row[0])
        group_id = str(row[1])
        raw_val = row[2]
        if isinstance(raw_val, str):
            pos_ids = json.loads(raw_val)
        elif isinstance(raw_val, list):
            pos_ids = raw_val
        else:
            pos_ids = []

        for pos_id in pos_ids:
            rule_id = str(uuid6.uuid7())
            connection.execute(
                sa.text(
                    """
                    INSERT INTO group_position_rules (id, tenant_id, group_id, position_id, created_at, updated_at, is_deleted)
                    VALUES (:id, :tenant_id, :group_id, :position_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, false)
                    """
                ),
                {
                    "id": rule_id,
                    "tenant_id": tenant_id,
                    "group_id": group_id,
                    "position_id": pos_id,
                }
            )

    # --- Drop group_rules ---
    rls.disable_rls_for(op, "group_rules")
    op.drop_table("group_rules")

    # --- Drop rule_logic from groups ---
    op.drop_column("groups", "rule_logic")

    # --- Drop Postgres Enums ---
    if bind.dialect.name == "postgresql":
        sa.Enum(name="rulelogic").drop(bind, checkfirst=True)
        sa.Enum(name="ruledimension").drop(bind, checkfirst=True)
