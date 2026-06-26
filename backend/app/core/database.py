from collections.abc import Generator
from typing import Any

from sqlalchemy import create_engine, event
from sqlalchemy.orm import ORMExecuteState, Session, sessionmaker, with_loader_criteria

from app.core.config import settings
from app.core.tenant_context import bypass_active, current_tenant
from app.models.base import TrackedBase

engine = create_engine(settings.database_url, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)


@event.listens_for(Session, "do_orm_execute")
def _apply_tenant_filter(state: ORMExecuteState) -> None:
    """Scope every ORM SELECT touching a TrackedBase entity to the current tenant.

    Applies a ``tenant_id == current_tenant()`` criterion to top-level selects *and*
    relationship loads (``include_aliases=True``), so route code no longer carries the
    predicate. PlatformBase entities have no ``tenant_id`` and are untouched. Skipped
    inside :func:`app.core.tenant_context.unscoped` and when no tenant is set (e.g.
    platform requests, fixture setup) — see ``docs/spec/tenant-data-access.md``.
    """
    if bypass_active() or not state.is_select:
        return
    tid = current_tenant()
    if tid is None:
        return
    state.statement = state.statement.options(
        with_loader_criteria(
            TrackedBase,
            lambda cls: cls.tenant_id == tid,
            include_aliases=True,
        )
    )


@event.listens_for(Session, "before_flush")
def _stamp_tenant(session: Session, flush_context: Any, instances: Any) -> None:
    """Stamp ``tenant_id`` onto new TrackedBase rows that don't already carry one.

    The write-side complement to :func:`_apply_tenant_filter`: removes ``tenant_id=...``
    from create paths and prevents writing a row into the wrong tenant. No-op under
    :func:`app.core.tenant_context.unscoped` or when no tenant is set.
    """
    if bypass_active():
        return
    tid = current_tenant()
    if tid is None:
        return
    for obj in session.new:
        if isinstance(obj, TrackedBase) and obj.tenant_id is None:
            obj.tenant_id = tid


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a scoped database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
