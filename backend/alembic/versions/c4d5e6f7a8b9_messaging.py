"""Messaging: announcements, group targets, and inbox/outbox rows (GH-146).

Revision ID: c4d5e6f7a8b9
Revises: b3c4d5e6f7a8
Create Date: 2026-07-05
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

from app.core import rls

# revision identifiers, used by Alembic.
revision: str = "c4d5e6f7a8b9"
down_revision: Union[str, None] = "b3c4d5e6f7a8"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

message_status = sa.Enum("draft", "scheduled", "sending", "sent", name="messagestatus")
audience_type = sa.Enum(
    "members", "members_and_parents", "parents_only", name="audiencetype"
)
email_state = sa.Enum(
    "pending",
    "sent",
    "failed",
    "skipped_opt_out",
    "skipped_bounced",
    "skipped_no_email",
    name="emailstate",
)
push_state = sa.Enum("sent", "no_devices", "failed", name="pushstate")


def upgrade() -> None:
    op.execute("CREATE SEQUENCE IF NOT EXISTS sync_seq")

    op.create_table(
        "messages",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column(
            "sync_seq",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("nextval('sync_seq')"),
        ),
        sa.Column("subject", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("status", message_status, nullable=False),
        sa.Column("send_push", sa.Boolean(), nullable=False),
        sa.Column("send_email", sa.Boolean(), nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("sent_by_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["sent_by_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_messages_is_deleted", "messages", ["is_deleted"])
    op.create_index("ix_messages_tenant_id", "messages", ["tenant_id"])
    op.create_index("ix_messages_tenant_sync_seq", "messages", ["tenant_id", "sync_seq"])
    rls.enable_rls_for(op, "messages")

    op.create_table(
        "message_groups",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("group_id", sa.Uuid(), nullable=False),
        sa.Column("audience_type", audience_type, nullable=False),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["group_id"], ["groups.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "message_id", "group_id", name="uq_message_groups_target"),
    )
    op.create_index("ix_message_groups_is_deleted", "message_groups", ["is_deleted"])
    op.create_index("ix_message_groups_tenant_id", "message_groups", ["tenant_id"])
    op.create_index("ix_message_groups_message_id", "message_groups", ["message_id"])
    rls.enable_rls_for(op, "message_groups")

    op.create_table(
        "message_recipients",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column(
            "sync_seq",
            sa.BigInteger(),
            nullable=False,
            server_default=sa.text("nextval('sync_seq')"),
        ),
        sa.Column("message_id", sa.Uuid(), nullable=False),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("email_state", email_state, nullable=False),
        sa.Column("push_state", push_state, nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_error", sa.String(length=500), nullable=True),
        sa.ForeignKeyConstraint(["message_id"], ["messages.id"]),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "tenant_id", "message_id", "member_id", name="uq_message_recipients_entry"
        ),
    )
    op.create_index("ix_message_recipients_is_deleted", "message_recipients", ["is_deleted"])
    op.create_index("ix_message_recipients_tenant_id", "message_recipients", ["tenant_id"])
    op.create_index("ix_message_recipients_message_id", "message_recipients", ["message_id"])
    op.create_index(
        "ix_message_recipients_tenant_member", "message_recipients", ["tenant_id", "member_id"]
    )
    op.create_index(
        "ix_message_recipients_tenant_sync_seq", "message_recipients", ["tenant_id", "sync_seq"]
    )
    op.create_index(
        "ix_message_recipients_email_queue",
        "message_recipients",
        ["email_state", "next_attempt_at"],
    )
    rls.enable_rls_for(op, "message_recipients")


def downgrade() -> None:
    rls.disable_rls_for(op, "message_recipients")
    op.drop_table("message_recipients")
    rls.disable_rls_for(op, "message_groups")
    op.drop_table("message_groups")
    rls.disable_rls_for(op, "messages")
    op.drop_table("messages")
    for enum in (push_state, email_state, audience_type, message_status):
        enum.drop(op.get_bind(), checkfirst=True)
