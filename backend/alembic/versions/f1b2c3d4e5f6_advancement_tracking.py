"""Advancement tracking: rank progress, requirement completions, merit badge records.

Pillar 4 Phase 2 (GH-92 / GH-169):

1. Three tenant-scoped tables (TrackedBase + SourceTracked, RLS enforced):
   ``member_rank_progress`` (per-rank version election + BOR/awarded dates),
   ``member_requirement_completions`` (report → approve workflow rows, leaves
   only), ``member_merit_badges`` (badge records incl. in-progress partials).
   Each carries a partial unique index (active rows only — soft delete is
   revocation and must not block later re-entry) and a tenant-leading
   ``(tenant_id, member_id)`` index for the member progress view.
2. ``tenants.advancement_mode`` — the per-tenant workflow switch
   (disabled / chair_entry / scout_reported), default ``chair_entry``.

Revision ID: f1b2c3d4e5f6
Revises: f0a1b2c3d4e5
Create Date: 2026-07-04

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

from app.core import rls

revision: str = "f1b2c3d4e5f6"
down_revision: Union[str, None] = "f0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# create_type=False: created/dropped explicitly so repeated use can't re-CREATE TYPE.
_completion_status = postgresql.ENUM(
    "reported", "approved", "rejected", name="completionstatus", create_type=False
)
_recorded_via = postgresql.ENUM(
    "manual", "auto", "import", "remap", name="recordedvia", create_type=False
)
_advancement_mode = postgresql.ENUM(
    "disabled", "chair_entry", "scout_reported", name="advancementmode", create_type=False
)


def _status_col() -> sa.Column:
    return sa.Column("status", _completion_status, nullable=False)


def _tracked_columns() -> list[sa.Column]:
    return [
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("tenant_id", sa.Uuid(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("is_deleted", sa.Boolean(), nullable=False),
        sa.Column("source_system", sa.String(length=32), nullable=True),
        sa.Column("source_id", sa.String(length=64), nullable=True),
        sa.Column("source_updated_at", sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _completion_status.create(bind, checkfirst=True)
        _recorded_via.create(bind, checkfirst=True)
        _advancement_mode.create(bind, checkfirst=True)

    op.create_table(
        "member_rank_progress",
        *_tracked_columns(),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("rank_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_set_id", sa.Uuid(), nullable=False),
        sa.Column("completed_date", sa.Date(), nullable=True),
        sa.Column("awarded_date", sa.Date(), nullable=True),
        sa.Column("synced_to_scoutbook_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["rank_id"], ["ranks.id"]),
        sa.ForeignKeyConstraint(["requirement_set_id"], ["requirement_sets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_member_rank_progress_tenant_id"), "member_rank_progress", ["tenant_id"]
    )
    op.create_index(
        op.f("ix_member_rank_progress_is_deleted"), "member_rank_progress", ["is_deleted"]
    )
    op.create_index(
        op.f("ix_member_rank_progress_member_id"), "member_rank_progress", ["member_id"]
    )
    op.create_index(
        op.f("ix_member_rank_progress_source_id"), "member_rank_progress", ["source_id"]
    )
    op.create_index(
        "ix_member_rank_progress_tenant_member",
        "member_rank_progress",
        ["tenant_id", "member_id"],
    )
    op.create_index(
        "uix_member_rank_progress_member_rank",
        "member_rank_progress",
        ["tenant_id", "member_id", "rank_id"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted"),
        sqlite_where=sa.text("is_deleted = 0"),
    )
    rls.enable_rls_for(op, "member_rank_progress")

    op.create_table(
        "member_requirement_completions",
        *_tracked_columns(),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("requirement_id", sa.Uuid(), nullable=False),
        sa.Column("date_completed", sa.Date(), nullable=False),
        _status_col(),
        sa.Column("reported_by_id", sa.Uuid(), nullable=True),
        sa.Column("approved_by_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("recorded_via", _recorded_via, nullable=False),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("synced_to_scoutbook_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["requirement_id"], ["requirements.id"]),
        sa.ForeignKeyConstraint(["reported_by_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["approved_by_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_member_requirement_completions_tenant_id"),
        "member_requirement_completions",
        ["tenant_id"],
    )
    op.create_index(
        op.f("ix_member_requirement_completions_is_deleted"),
        "member_requirement_completions",
        ["is_deleted"],
    )
    op.create_index(
        op.f("ix_member_requirement_completions_member_id"),
        "member_requirement_completions",
        ["member_id"],
    )
    op.create_index(
        op.f("ix_member_requirement_completions_requirement_id"),
        "member_requirement_completions",
        ["requirement_id"],
    )
    op.create_index(
        op.f("ix_member_requirement_completions_source_id"),
        "member_requirement_completions",
        ["source_id"],
    )
    op.create_index(
        "ix_member_req_completions_tenant_member",
        "member_requirement_completions",
        ["tenant_id", "member_id"],
    )
    op.create_index(
        "uix_member_req_completions_member_req",
        "member_requirement_completions",
        ["tenant_id", "member_id", "requirement_id"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted"),
        sqlite_where=sa.text("is_deleted = 0"),
    )
    rls.enable_rls_for(op, "member_requirement_completions")

    op.create_table(
        "member_merit_badges",
        *_tracked_columns(),
        sa.Column("member_id", sa.Uuid(), nullable=False),
        sa.Column("merit_badge_id", sa.Uuid(), nullable=False),
        sa.Column("date_started", sa.Date(), nullable=True),
        sa.Column("date_completed", sa.Date(), nullable=True),
        sa.Column("counselor_name", sa.String(length=255), nullable=True),
        _status_col(),
        sa.Column("reported_by_id", sa.Uuid(), nullable=True),
        sa.Column("approved_by_id", sa.Uuid(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("synced_to_scoutbook_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["member_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["merit_badge_id"], ["merit_badges.id"]),
        sa.ForeignKeyConstraint(["reported_by_id"], ["members.id"]),
        sa.ForeignKeyConstraint(["approved_by_id"], ["members.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_member_merit_badges_tenant_id"), "member_merit_badges", ["tenant_id"]
    )
    op.create_index(
        op.f("ix_member_merit_badges_is_deleted"), "member_merit_badges", ["is_deleted"]
    )
    op.create_index(
        op.f("ix_member_merit_badges_member_id"), "member_merit_badges", ["member_id"]
    )
    op.create_index(
        op.f("ix_member_merit_badges_source_id"), "member_merit_badges", ["source_id"]
    )
    op.create_index(
        "ix_member_merit_badges_tenant_member", "member_merit_badges", ["tenant_id", "member_id"]
    )
    op.create_index(
        "uix_member_merit_badges_member_badge",
        "member_merit_badges",
        ["tenant_id", "member_id", "merit_badge_id"],
        unique=True,
        postgresql_where=sa.text("NOT is_deleted"),
        sqlite_where=sa.text("is_deleted = 0"),
    )
    rls.enable_rls_for(op, "member_merit_badges")

    op.add_column(
        "tenants",
        sa.Column(
            "advancement_mode",
            _advancement_mode,
            nullable=False,
            server_default="chair_entry",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "advancement_mode")
    for table in (
        "member_merit_badges",
        "member_requirement_completions",
        "member_rank_progress",
    ):
        rls.disable_rls_for(op, table)
        op.drop_table(table)
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        _advancement_mode.drop(bind, checkfirst=True)
        _recorded_via.drop(bind, checkfirst=True)
        _completion_status.drop(bind, checkfirst=True)
