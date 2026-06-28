"""Split the single Role model into Positions and Functional Roles.

Replaces the ``roles`` / ``role_permissions`` / ``role_memberships`` /
``member_role_assignments`` tables (and ``group_role_rules``) with the two-level
RBAC model from ``docs/spec/roles-rbac.md``:

    positions ──position_functional_roles──▶ functional_roles ──▶ functional_role_permissions
        ▲                                                              (Permission enum)
        │
    member_position_assignments, group_position_rules

This is a greenfield replacement — acceptable because the product is pre-1.0 and
the old tables were only lightly seeded. The shared ``permission`` Postgres enum
type is reused (not dropped/recreated); a new ``positionscope`` enum is added.

Revision ID: c1d2e3f4a5b6
Revises: 1a2b3c4d5e6f
Create Date: 2026-06-26 00:00:00.000000
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core import rls

revision: str = "c1d2e3f4a5b6"
down_revision: str | None = "1a2b3c4d5e6f"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# The shared Permission enum already exists in the DB (created with role_permissions
# in the initial migration). Reuse it without re-creating or dropping the type.
_PERMISSION_LABELS = [
    "MEMBER_READ",
    "MEMBER_WRITE",
    "MEMBER_READ_MEDICAL",
    "MEMBER_WRITE_MEDICAL",
    "MEMBER_READ_CONTACT",
    "MEMBER_DELETE",
    "EVENT_READ",
    "EVENT_CREATE",
    "EVENT_WRITE",
    "EVENT_DELETE",
    "EVENT_MANAGE_ATTENDANCE",
    "ADVANCEMENT_READ",
    "ADVANCEMENT_RECORD",
    "ADVANCEMENT_APPROVE",
    "FINANCE_READ",
    "FINANCE_WRITE",
    "ROLE_ASSIGN",
    "ROLE_MANAGE",
    "COMMUNICATION_SEND_TROOP",
    "COMMUNICATION_SEND_PATROL",
    "REPORT_READ",
]


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
    # --- Drop the old role tables (children first) -------------------------
    for table in (
        "group_role_rules",
        "member_role_assignments",
        "role_memberships",
        "role_permissions",
        "roles",
    ):
        rls.disable_rls_for(op, table)
        op.drop_table(table)

    permission_enum = postgresql.ENUM(*_PERMISSION_LABELS, name="permission", create_type=False)
    position_scope_enum = sa.Enum("scout", "adult", "any", name="positionscope")

    # --- positions ---------------------------------------------------------
    op.create_table(
        "positions",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("applies_to", position_scope_enum, nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        *_tracked_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_positions_tenant_slug"),
    )
    op.create_index(op.f("ix_positions_slug"), "positions", ["slug"], unique=False)
    _standard_indexes("positions")
    rls.enable_rls_for(op, "positions")

    # --- functional_roles --------------------------------------------------
    op.create_table(
        "functional_roles",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        *_tracked_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_functional_roles_tenant_slug"),
    )
    op.create_index(op.f("ix_functional_roles_slug"), "functional_roles", ["slug"], unique=False)
    _standard_indexes("functional_roles")
    rls.enable_rls_for(op, "functional_roles")

    # --- functional_role_permissions --------------------------------------
    op.create_table(
        "functional_role_permissions",
        sa.Column("functional_role_id", sa.Uuid(), nullable=False),
        sa.Column("permission", permission_enum, nullable=False),
        *_tracked_columns(),
        sa.ForeignKeyConstraint(["functional_role_id"], ["functional_roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "functional_role_id", "permission", name="uq_functional_role_permissions_role_perm"
        ),
    )
    op.create_index(
        op.f("ix_functional_role_permissions_functional_role_id"),
        "functional_role_permissions",
        ["functional_role_id"],
        unique=False,
    )
    _standard_indexes("functional_role_permissions")
    rls.enable_rls_for(op, "functional_role_permissions")

    # --- position_functional_roles ----------------------------------------
    op.create_table(
        "position_functional_roles",
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("functional_role_id", sa.Uuid(), nullable=False),
        *_tracked_columns(),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.ForeignKeyConstraint(["functional_role_id"], ["functional_roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "position_id", "functional_role_id", name="uq_position_functional_roles"
        ),
    )
    op.create_index(
        op.f("ix_position_functional_roles_position_id"),
        "position_functional_roles",
        ["position_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_position_functional_roles_functional_role_id"),
        "position_functional_roles",
        ["functional_role_id"],
        unique=False,
    )
    _standard_indexes("position_functional_roles")
    rls.enable_rls_for(op, "position_functional_roles")

    # --- member_position_assignments --------------------------------------
    op.create_table(
        "member_position_assignments",
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("position_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by_id", sa.Uuid(), nullable=True),
        *_tracked_columns(),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["position_id"], ["positions.id"]),
        sa.ForeignKeyConstraint(["assigned_by_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "member_id", "position_id", name="uq_member_position_assignments"
        ),
    )
    op.create_index(
        op.f("ix_member_position_assignments_member_id"),
        "member_position_assignments",
        ["member_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_member_position_assignments_position_id"),
        "member_position_assignments",
        ["position_id"],
        unique=False,
    )
    _standard_indexes("member_position_assignments")
    rls.enable_rls_for(op, "member_position_assignments")

    # --- group_position_rules ---------------------------------------------
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


def downgrade() -> None:
    # --- Drop the new tables (children first) ------------------------------
    for table in (
        "group_position_rules",
        "member_position_assignments",
        "position_functional_roles",
        "functional_role_permissions",
        "functional_roles",
        "positions",
    ):
        rls.disable_rls_for(op, table)
        op.drop_table(table)

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="positionscope").drop(bind, checkfirst=True)

    permission_enum = postgresql.ENUM(*_PERMISSION_LABELS, name="permission", create_type=False)

    # --- Recreate the old role tables --------------------------------------
    op.create_table(
        "roles",
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), nullable=False),
        *_tracked_columns(),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "slug", name="uq_roles_tenant_slug"),
    )
    op.create_index(op.f("ix_roles_slug"), "roles", ["slug"], unique=False)
    _standard_indexes("roles")
    rls.enable_rls_for(op, "roles")

    op.create_table(
        "role_permissions",
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("permission", permission_enum, nullable=False),
        *_tracked_columns(),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("role_id", "permission", name="uq_role_permissions_role_perm"),
    )
    op.create_index(
        op.f("ix_role_permissions_role_id"), "role_permissions", ["role_id"], unique=False
    )
    _standard_indexes("role_permissions")
    rls.enable_rls_for(op, "role_permissions")

    op.create_table(
        "role_memberships",
        sa.Column("group_role_id", sa.Uuid(), nullable=False),
        sa.Column("member_role_id", sa.Uuid(), nullable=False),
        *_tracked_columns(),
        sa.ForeignKeyConstraint(["group_role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["member_role_id"], ["roles.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "group_role_id", "member_role_id", name="uq_role_memberships_group_member"
        ),
    )
    op.create_index(
        op.f("ix_role_memberships_group_role_id"), "role_memberships", ["group_role_id"], unique=False
    )
    op.create_index(
        op.f("ix_role_memberships_member_role_id"),
        "role_memberships",
        ["member_role_id"],
        unique=False,
    )
    _standard_indexes("role_memberships")
    rls.enable_rls_for(op, "role_memberships")

    op.create_table(
        "member_role_assignments",
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        sa.Column("assigned_by_id", sa.Uuid(), nullable=True),
        *_tracked_columns(),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["role_id"], ["roles.id"]),
        sa.ForeignKeyConstraint(["assigned_by_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "member_id", "role_id", name="uq_member_role_assignments_member_role"
        ),
    )
    op.create_index(
        op.f("ix_member_role_assignments_member_id"),
        "member_role_assignments",
        ["member_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_member_role_assignments_role_id"),
        "member_role_assignments",
        ["role_id"],
        unique=False,
    )
    _standard_indexes("member_role_assignments")
    rls.enable_rls_for(op, "member_role_assignments")

    op.create_table(
        "group_role_rules",
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("role_id", sa.Uuid(), nullable=False),
        *_tracked_columns(),
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
    _standard_indexes("group_role_rules")
    rls.enable_rls_for(op, "group_role_rules")
