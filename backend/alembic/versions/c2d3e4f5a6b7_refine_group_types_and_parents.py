"""refine group types and parent options

Collapse GroupType {manual, dynamic} -> custom (patrol unchanged); add
``include_parents`` and ``cc_parents_on_messages`` to groups; drop the
``relationship`` rule dimension (rules dropped silently — pre-production).

Revision ID: c2d3e4f5a6b7
Revises: 7f9bd698851b
Create Date: 2026-06-29 00:00:00.000000

"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "7f9bd698851b"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()

    # --- New parent-option columns on groups ---
    op.add_column(
        "groups",
        sa.Column("include_parents", sa.Boolean(), nullable=False, server_default="false"),
    )
    op.add_column(
        "groups",
        sa.Column("cc_parents_on_messages", sa.Boolean(), nullable=False, server_default="false"),
    )

    # --- Drop legacy relationship rules (no real data; semantic no longer maps) ---
    op.execute("DELETE FROM group_rules WHERE dimension = 'relationship'")

    if bind.dialect.name != "postgresql":
        return

    # --- GroupType: {manual, dynamic, patrol} -> {custom, patrol} ---
    sa.Enum("custom", "patrol", name="grouptype_new").create(bind, checkfirst=True)
    op.execute(
        "ALTER TABLE groups ALTER COLUMN group_type TYPE grouptype_new "
        "USING (CASE WHEN group_type::text IN ('manual', 'dynamic') "
        "THEN 'custom' ELSE group_type::text END::grouptype_new)"
    )
    op.execute("DROP TYPE grouptype")
    op.execute("ALTER TYPE grouptype_new RENAME TO grouptype")

    # --- RuleDimension: drop 'relationship' ---
    sa.Enum(
        "member_type",
        "membership_status",
        "oa_member",
        "oa_active",
        "position",
        "group_member",
        "rank",
        name="ruledimension_new",
    ).create(bind, checkfirst=True)
    op.execute(
        "ALTER TABLE group_rules ALTER COLUMN dimension TYPE ruledimension_new "
        "USING dimension::text::ruledimension_new"
    )
    op.execute("DROP TYPE ruledimension")
    op.execute("ALTER TYPE ruledimension_new RENAME TO ruledimension")


def downgrade() -> None:
    bind = op.get_bind()

    if bind.dialect.name == "postgresql":
        # --- RuleDimension: restore 'relationship' ---
        sa.Enum(
            "member_type",
            "membership_status",
            "oa_member",
            "oa_active",
            "position",
            "group_member",
            "relationship",
            "rank",
            name="ruledimension_old",
        ).create(bind, checkfirst=True)
        op.execute(
            "ALTER TABLE group_rules ALTER COLUMN dimension TYPE ruledimension_old "
            "USING dimension::text::ruledimension_old"
        )
        op.execute("DROP TYPE ruledimension")
        op.execute("ALTER TYPE ruledimension_old RENAME TO ruledimension")

        # --- GroupType: {custom, patrol} -> {manual, dynamic, patrol} (custom -> manual) ---
        sa.Enum("manual", "dynamic", "patrol", name="grouptype_old").create(bind, checkfirst=True)
        op.execute(
            "ALTER TABLE groups ALTER COLUMN group_type TYPE grouptype_old "
            "USING (CASE WHEN group_type::text = 'custom' "
            "THEN 'manual' ELSE group_type::text END::grouptype_old)"
        )
        op.execute("DROP TYPE grouptype")
        op.execute("ALTER TYPE grouptype_old RENAME TO grouptype")

    op.drop_column("groups", "cc_parents_on_messages")
    op.drop_column("groups", "include_parents")
