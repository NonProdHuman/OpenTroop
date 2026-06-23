import uuid
from collections.abc import Generator
from typing import Annotated

import pytest
from fastapi import Header
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.tenant import get_tenant_id
from app.main import app
from app.models import Base  # registers all models on Base.metadata
from app.models.enums import MemberType
from app.models.member import Member
from app.models.role import MemberRoleAssignment, Role
from app.models.user import User

TENANT_A = uuid.UUID("10000000-0000-0000-0000-000000000001")
TENANT_B = uuid.UUID("20000000-0000-0000-0000-000000000002")

# Fixed IDs for the seeded admin user/member/role so tests can reference them.
ADMIN_USER_ID = uuid.UUID("a0000000-0000-0000-0000-000000000001")
_ADMIN_MEMBER_IDS: dict[uuid.UUID, uuid.UUID] = {
    TENANT_A: uuid.UUID("a0000000-0000-0000-0000-000000000010"),
    TENANT_B: uuid.UUID("b0000000-0000-0000-0000-000000000020"),
}


async def _simple_tenant_id(x_tenant_id: Annotated[str, Header()]) -> uuid.UUID:
    """Test-only override: read tenant UUID directly from the X-Tenant-ID header.

    Skips the DB Tenant lookup so tests can use arbitrary UUIDs without
    inserting Tenant rows.  Both ``client`` and ``other_client`` send different
    headers, so they still receive different tenant IDs.
    """
    return uuid.UUID(x_tenant_id)


async def _fake_current_user() -> User:
    """Test-only override: return a fixed User without JWT validation."""
    return User(id=ADMIN_USER_ID, email="admin@test.com", display_name="Test Admin")


def _seed_admin(session: Session, tenant_id: uuid.UUID) -> None:
    """Seed an admin User + Member + Role for the given tenant (idempotent).

    Ensures that requests made via the test client pass the require() permission
    check — the seeded member holds the administrators role (is_admin=True), which
    bypasses all individual permission checks.
    """
    if session.get(User, ADMIN_USER_ID) is None:
        session.add(User(id=ADMIN_USER_ID, email="admin@test.com", display_name="Test Admin"))
        session.flush()
    member_id = _ADMIN_MEMBER_IDS[tenant_id]
    if session.get(Member, member_id) is None:
        session.add(
            Member(
                id=member_id,
                tenant_id=tenant_id,
                user_id=ADMIN_USER_ID,
                first_name="Admin",
                last_name="User",
                member_type=MemberType.ADULT,
            )
        )
        session.flush()
        role = Role(
            tenant_id=tenant_id,
            name="Administrators",
            slug="administrators",
            is_admin=True,
            is_system=True,
        )
        session.add(role)
        session.flush()
        session.add(MemberRoleAssignment(tenant_id=tenant_id, member_id=member_id, role_id=role.id))
        session.flush()


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
    _seed_admin(db_session, TENANT_A)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_tenant_id] = _simple_tenant_id
    app.dependency_overrides[get_current_user] = _fake_current_user
    with TestClient(app, headers={"X-Tenant-ID": str(TENANT_A)}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def other_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient scoped to TENANT_B — same DB session, different tenant."""
    _seed_admin(db_session, TENANT_B)
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_tenant_id] = _simple_tenant_id
    app.dependency_overrides[get_current_user] = _fake_current_user
    with TestClient(app, headers={"X-Tenant-ID": str(TENANT_B)}) as c:
        yield c
    app.dependency_overrides.clear()
