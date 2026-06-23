"""add_platform_identity_tables

Revision ID: b4c5d6e7f8a9
Revises: 476948db06f4
Create Date: 2026-06-23 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "b4c5d6e7f8a9"
down_revision: Union[str, None] = "476948db06f4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tenants",
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=80), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("slug", name="uq_tenants_slug"),
    )
    op.create_index(op.f("ix_tenants_is_deleted"), "tenants", ["is_deleted"], unique=False)
    op.create_index(op.f("ix_tenants_slug"), "tenants", ["slug"], unique=False)

    op.create_table(
        "users",
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("display_name", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_users_email"), "users", ["email"], unique=False)
    op.create_index(op.f("ix_users_is_deleted"), "users", ["is_deleted"], unique=False)

    op.create_table(
        "identities",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("issuer", sa.String(length=255), nullable=False),
        sa.Column("provider_sub", sa.String(length=255), nullable=False),
        sa.Column("email", sa.String(length=255), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("issuer", "provider_sub", name="uq_identities_issuer_sub"),
    )
    op.create_index(
        op.f("ix_identities_is_deleted"), "identities", ["is_deleted"], unique=False
    )
    op.create_index(op.f("ix_identities_issuer"), "identities", ["issuer"], unique=False)
    op.create_index(
        op.f("ix_identities_user_id"), "identities", ["user_id"], unique=False
    )

    op.add_column("members", sa.Column("user_id", sa.Uuid(), nullable=True))
    op.create_index(op.f("ix_members_user_id"), "members", ["user_id"], unique=False)
    op.create_foreign_key(
        "fk_members_user_id_users", "members", "users", ["user_id"], ["id"]
    )


def downgrade() -> None:
    op.drop_constraint("fk_members_user_id_users", "members", type_="foreignkey")
    op.drop_index(op.f("ix_members_user_id"), table_name="members")
    op.drop_column("members", "user_id")

    op.drop_index(op.f("ix_identities_user_id"), table_name="identities")
    op.drop_index(op.f("ix_identities_issuer"), table_name="identities")
    op.drop_index(op.f("ix_identities_is_deleted"), table_name="identities")
    op.drop_table("identities")

    op.drop_index(op.f("ix_users_is_deleted"), table_name="users")
    op.drop_index(op.f("ix_users_email"), table_name="users")
    op.drop_table("users")

    op.drop_index(op.f("ix_tenants_slug"), table_name="tenants")
    op.drop_index(op.f("ix_tenants_is_deleted"), table_name="tenants")
    op.drop_table("tenants")
