"""Consent ledger — ToS / COPPA / media / SMS consent records (#223).

Revision ID: e6f7a8b9c0d1
Revises: d5e6f7a8b9c0
Create Date: 2026-07-06
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

from app.core import rls

# revision identifiers, used by Alembic.
revision: str = "e6f7a8b9c0d1"
down_revision: Union[str, None] = "d5e6f7a8b9c0"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

consent_scope = sa.Enum("tos", "account", "media", "sms", name="consentscope")
consent_method = sa.Enum("self", "parent_portal", "sms", "signed_form", "kba", name="consentmethod")


def upgrade() -> None:
    op.create_table(
        "consent_records",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("subject_member_id", sa.Uuid(), nullable=False),
        sa.Column("consented_by_member_id", sa.Uuid(), nullable=True),
        sa.Column("consented_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("scope", consent_scope, nullable=False),
        sa.Column("method", consent_method, nullable=False),
        sa.Column("granted_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("policy_version", sa.String(length=64), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(["subject_member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["consented_by_member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["consented_by_user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_consent_records_is_deleted", "consent_records", ["is_deleted"])
    op.create_index("ix_consent_records_tenant_id", "consent_records", ["tenant_id"])
    op.create_index(
        "ix_consent_records_tenant_subject",
        "consent_records",
        ["tenant_id", "subject_member_id"],
    )
    rls.enable_rls_for(op, "consent_records")


def downgrade() -> None:
    rls.disable_rls_for(op, "consent_records")
    op.drop_index("ix_consent_records_tenant_subject", table_name="consent_records")
    op.drop_index("ix_consent_records_tenant_id", table_name="consent_records")
    op.drop_index("ix_consent_records_is_deleted", table_name="consent_records")
    op.drop_table("consent_records")
    bind = op.get_bind()
    consent_scope.drop(bind, checkfirst=True)
    consent_method.drop(bind, checkfirst=True)
