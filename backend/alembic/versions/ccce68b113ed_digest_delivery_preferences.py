"""Digest batching + member notification preferences (GH-218).

Adds:
- ``messages.delivery`` — MessageDelivery (immediate | digest). Immediate is
  today's behavior; digest holds the email copy for the tenant's weekly newsletter.
- ``members.announcement_email_mode`` — AnnouncementEmailMode (every | digest | none),
  the member-facing preference centre knob.
- ``tenants.digest_day`` / ``digest_hour_utc`` / ``last_digest_at`` — per-tenant
  digest cadence (day follows date.weekday(): 0 = Monday … 6 = Sunday).
- ``held_digest`` label on the existing ``emailstate`` Postgres enum (the state a
  withheld digest email lands in until assembly delivers it).

All are column/enum additions on existing tables — no new tables, so no RLS wiring.

Revision ID: ccce68b113ed
Revises: 574389ed3d16
Create Date: 2026-07-07
"""

from typing import Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "ccce68b113ed"
down_revision: Union[str, None] = "574389ed3d16"
branch_labels: Union[str, None] = None
depends_on: Union[str, None] = None

message_delivery = sa.Enum("immediate", "digest", name="messagedelivery")
announcement_email_mode = sa.Enum("every", "digest", "none", name="announcementemailmode")


def upgrade() -> None:
    bind = op.get_bind()
    is_pg = bind.dialect.name == "postgresql"
    if is_pg:
        # Extend the native emailstate enum with the withheld-digest state. ADD VALUE
        # is legal in a transaction on PG >= 12 as long as the new label isn't *used*
        # here. The two new enum types must be created before their columns —
        # ``op.add_column`` (unlike ``create_table``) does not emit CREATE TYPE.
        op.execute(sa.text("ALTER TYPE emailstate ADD VALUE IF NOT EXISTS 'held_digest'"))
        message_delivery.create(bind, checkfirst=True)
        announcement_email_mode.create(bind, checkfirst=True)

    op.add_column(
        "messages",
        sa.Column(
            "delivery",
            message_delivery,
            nullable=False,
            server_default="immediate",
        ),
    )
    op.add_column(
        "members",
        sa.Column(
            "announcement_email_mode",
            announcement_email_mode,
            nullable=False,
            server_default="every",
        ),
    )
    op.add_column(
        "tenants",
        sa.Column("digest_day", sa.Integer(), nullable=False, server_default="6"),
    )
    op.add_column(
        "tenants",
        sa.Column("digest_hour_utc", sa.Integer(), nullable=False, server_default="16"),
    )
    op.add_column(
        "tenants",
        sa.Column("last_digest_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("tenants", "last_digest_at")
    op.drop_column("tenants", "digest_hour_utc")
    op.drop_column("tenants", "digest_day")
    op.drop_column("members", "announcement_email_mode")
    op.drop_column("messages", "delivery")
    bind = op.get_bind()
    announcement_email_mode.drop(bind, checkfirst=True)
    message_delivery.drop(bind, checkfirst=True)
    # Postgres cannot drop the added `held_digest` enum label; leaving it is harmless.
