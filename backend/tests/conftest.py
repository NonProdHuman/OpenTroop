import uuid
from collections.abc import Generator
from typing import Annotated

import pytest
from fastapi import Header, HTTPException
from fastapi import status as http_status
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import get_current_user
from app.core.database import get_db
from app.core.tenant import get_tenant_id
from app.main import app
from app.models import Base  # registers all models on Base.metadata
from app.models.enums import MemberType, PlatformRole
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

# A second user with no pre-seeded Member — used for claim / onboarding tests.
NEW_USER_ID = uuid.UUID("c0000000-0000-0000-0000-000000000001")

# A platform (global) admin — holds platform_role, no tenant membership.
PLATFORM_ADMIN_USER_ID = uuid.UUID("d0000000-0000-0000-0000-000000000001")

_USERS = {
    str(ADMIN_USER_ID): User(id=ADMIN_USER_ID, email="admin@test.com", display_name="Test Admin"),
    str(NEW_USER_ID): User(id=NEW_USER_ID, email="newuser@test.com", display_name="New User"),
    str(PLATFORM_ADMIN_USER_ID): User(
        id=PLATFORM_ADMIN_USER_ID,
        email="platform@test.com",
        display_name="Platform Admin",
        platform_role=PlatformRole.SUPERADMIN,
    ),
}


async def _simple_tenant_id(x_tenant_id: Annotated[str, Header()]) -> uuid.UUID:
    """Test-only override: read tenant UUID directly from the X-Tenant-ID header.

    Skips the DB Tenant lookup so tests can use arbitrary UUIDs without
    inserting Tenant rows.  Both ``client`` and ``other_client`` send different
    headers, so they still receive different tenant IDs.
    """
    return uuid.UUID(x_tenant_id)


async def _test_current_user(
    x_test_user_id: Annotated[str | None, Header()] = None,
) -> User:
    """Test-only override: select the active user from a per-request header.

    Using a header (rather than a fixed lambda) lets multiple test clients with
    different identities coexist in the same test without conflicting on the
    single ``dependency_overrides`` slot for ``get_current_user``.
    """
    if x_test_user_id is not None and x_test_user_id in _USERS:
        return _USERS[x_test_user_id]
    raise HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


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


def _set_shared_overrides(db_session: Session) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    app.dependency_overrides[get_tenant_id] = _simple_tenant_id
    app.dependency_overrides[get_current_user] = _test_current_user


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
    """TestClient scoped to TENANT_A, authenticated as ADMIN_USER_ID."""
    _seed_admin(db_session, TENANT_A)
    _set_shared_overrides(db_session)
    with TestClient(
        app,
        headers={
            "X-Tenant-ID": str(TENANT_A),
            "X-Test-User-ID": str(ADMIN_USER_ID),
        },
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def other_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient scoped to TENANT_B — same DB session, different tenant."""
    _seed_admin(db_session, TENANT_B)
    _set_shared_overrides(db_session)
    with TestClient(
        app,
        headers={
            "X-Tenant-ID": str(TENANT_B),
            "X-Test-User-ID": str(ADMIN_USER_ID),
        },
    ) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def claim_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient authenticated as NEW_USER_ID with no pre-seeded Member in any tenant.

    Used to test the invite/claim and tenant onboarding flows.  The shared
    ``_test_current_user`` override means this fixture coexists safely with
    ``client`` and ``other_client`` in the same test.
    """
    _set_shared_overrides(db_session)
    with TestClient(app, headers={"X-Test-User-ID": str(NEW_USER_ID)}) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def platform_admin_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient authenticated as a platform (global) admin — no tenant membership.

    Used to test the SaaS control plane (tenant provisioning). Holds
    ``platform_role=SUPERADMIN`` but is deliberately not a Member of any tenant.
    """
    _set_shared_overrides(db_session)
    with TestClient(app, headers={"X-Test-User-ID": str(PLATFORM_ADMIN_USER_ID)}) as c:
        yield c
    app.dependency_overrides.clear()
