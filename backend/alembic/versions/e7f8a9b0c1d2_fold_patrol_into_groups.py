"""fold_patrol_into_groups

Introduces the general Group model (``groups``, ``group_members``,
``group_role_rules``) and folds the standalone ``patrols`` table into it:

- each patrol becomes a ``PATROL``-type group (reusing its UUID), and
- each ``members.patrol_id`` becomes a ``group_members`` row.

The ``members.patrol_id`` column and the ``patrols`` table are then dropped.

Revision ID: e7f8a9b0c1d2
Revises: d6e7f8a9b0c1
Create Date: 2026-06-25 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "e7f8a9b0c1d2"
down_revision: Union[str, None] = "d6e7f8a9b0c1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

group_type_enum = sa.Enum("manual", "dynamic", "patrol", name="grouptype")


def upgrade() -> None:
    # --- New tables --------------------------------------------------------
    op.create_table(
        "groups",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("group_type", group_type_enum, nullable=False),
        sa.Column("color", sa.String(length=20), nullable=True),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "name", name="uq_groups_tenant_name"),
    )
    op.create_index(op.f("ix_groups_is_deleted"), "groups", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_groups_tenant_id"), "groups", ["tenant_id"], unique=False)

    op.create_table(
        "group_members",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("added_by_id", sa.Uuid(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["added_by_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "member_id", name="uq_group_members_group_member"),
    )
    op.create_index(op.f("ix_group_members_group_id"), "group_members", ["group_id"], unique=False)
    op.create_index(
        op.f("ix_group_members_member_id"), "group_members", ["member_id"], unique=False
    )
    op.create_index(
        op.f("ix_group_members_is_deleted"), "group_members", ["is_deleted"], unique=False
    )
    op.create_index(
        op.f("ix_group_members_tenant_id"), "group_members", ["tenant_id"], unique=False
    )

    op.create_table(
        "group_role_rules",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("group_id", "role_id", name="uq_group_role_rules_group_role"),
    )
    op.create_index(
        op.f("ix_group_role_rules_group_id"), "group_role_rules", ["group_id"], unique=False
    )
    op.create_index(
        op.f("ix_group_role_rules_role_id"), "group_role_rules", ["role_id"], unique=False
    )
    op.create_index(
        op.f("ix_group_role_rules_is_deleted"), "group_role_rules", ["is_deleted"], unique=False
    )
    op.create_index(
        op.f("ix_group_role_rules_tenant_id"), "group_role_rules", ["tenant_id"], unique=False
    )

    # --- Data migration: patrols -> groups, members.patrol_id -> group_members
    op.execute(
        """
        INSERT INTO groups
            (id, tenant_id, name, description, group_type, color, is_system,
             created_at, updated_at, is_deleted)
        SELECT id, tenant_id, name, NULL, 'patrol'::grouptype, NULL, false,
               created_at, updated_at, is_deleted
        FROM patrols
        """
    )
    op.execute(
        """
        INSERT INTO group_members
            (id, tenant_id, group_id, member_id, added_by_id,
             created_at, updated_at, is_deleted)
        SELECT gen_random_uuid(), m.tenant_id, m.patrol_id, m.id, NULL,
               now(), now(), false
        FROM members m
        WHERE m.patrol_id IS NOT NULL
        """
    )

    # --- Drop the folded-away column and table ----------------------------
    op.drop_column("members", "patrol_id")
    op.drop_index(op.f("ix_patrols_tenant_id"), table_name="patrols")
    op.drop_index(op.f("ix_patrols_is_deleted"), table_name="patrols")
    op.drop_table("patrols")


def downgrade() -> None:
    # Recreate the patrols table and the members.patrol_id column.
    op.create_table(
        "patrols",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_patrols_is_deleted"), "patrols", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_patrols_tenant_id"), "patrols", ["tenant_id"], unique=False)
    op.add_column("members", sa.Column("patrol_id", sa.Uuid(), nullable=True))
    op.create_foreign_key(
        "members_patrol_id_fkey", "members", "patrols", ["patrol_id"], ["id"]
    )

    # Restore patrol rows and per-member patrol assignment from the group tables.
    op.execute(
        """
        INSERT INTO patrols (id, name, tenant_id, created_at, updated_at, is_deleted)
        SELECT id, name, tenant_id, created_at, updated_at, is_deleted
        FROM groups
        WHERE group_type = 'patrol'::grouptype
        """
    )
    op.execute(
        """
        UPDATE members m
        SET patrol_id = gm.group_id
        FROM group_members gm
        WHERE gm.member_id = m.id
          AND gm.is_deleted = false
          AND gm.group_id IN (SELECT id FROM patrols)
        """
    )

    op.drop_table("group_role_rules")
    op.drop_table("group_members")
    op.drop_table("groups")
    group_type_enum.drop(op.get_bind(), checkfirst=True)
