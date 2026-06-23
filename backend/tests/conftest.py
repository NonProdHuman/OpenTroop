import uuid
from collections.abc import Generator
from typing import Annotated

import pytest
from fastapi import Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.database import get_db
from app.core.tenant import get_tenant_id
from app.main import app
from app.models import Base  # registers all models on Base.metadata

TENANT_A = uuid.UUID("10000000-0000-0000-0000-000000000001")
TENANT_B = uuid.UUID("20000000-0000-0000-0000-000000000002")


async def _simple_tenant_id(x_tenant_id: Annotated[str, Header()]) -> uuid.UUID:
    """Test-only override: read tenant UUID directly from the X-Tenant-ID header.

    Skips the DB Tenant lookup so tests can use arbitrary UUIDs without
    inserting Tenant rows.  Both ``client`` and ``other_client`` send different
    headers, so they still receive different tenant IDs.
    """
    return uuid.UUID(x_tenant_id)


@pytest.fixture
def db_session() -> Generator[Session, None, None]:
    """In-memory SQLite session with all tables created from the ORM metadata.

    The dialect-agnostic ``Uuid`` column type lets the Postgres-targeted models
    run unmodified against SQLite for fast, isolated schema/relationship tests.
    """
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    Base.metadata.create_all(engine)
    TestingSession = sessionmaker(bind=engine, autoflush=False, future=True)

    session = TestingSession()
    try:
        yield session
    finally:
        session.close()
        Base.metadata.drop_all(engine)
        engine.dispose()


@pytest.fixture
def client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient scoped to TENANT_A, sharing the in-memory SQLite session."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_tenant_id] = _simple_tenant_id
    with TestClient(app, headers={"X-Tenant-ID": str(TENANT_A)}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def other_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient scoped to TENANT_B — same DB session, different tenant."""
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_tenant_id] = _simple_tenant_id
    with TestClient(app, headers={"X-Tenant-ID": str(TENANT_B)}) as c:
        yield c
    app.dependency_overrides.clear()
