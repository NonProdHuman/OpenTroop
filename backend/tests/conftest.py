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

from app.core.auth import get_current_user, get_optional_current_user
from app.core.database import get_admin_db, get_db
from app.core.tenant import get_tenant_id
from app.main import app
from app.models import Base  # registers all models on Base.metadata
from app.models.enums import MemberType, PlatformRole, PositionScope
from app.models.member import Member
from app.models.rbac import (
    FunctionalRole,
    MemberPositionAssignment,
    Position,
    PositionFunctionalRole,
)
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
# A platform admin with a non-superadmin role — used to test the superadmin boundary.
PLATFORM_SUPPORT_USER_ID = uuid.UUID("d0000000-0000-0000-0000-000000000002")

# Seeded users carry email_verified=True — they stand in for accounts whose OIDC
# provider verified the address; email-based matching paths require it.
_USERS = {
    str(ADMIN_USER_ID): User(
        id=ADMIN_USER_ID, email="admin@test.com", email_verified=True, display_name="Test Admin"
    ),
    str(NEW_USER_ID): User(
        id=NEW_USER_ID, email="newuser@test.com", email_verified=True, display_name="New User"
    ),
    str(PLATFORM_ADMIN_USER_ID): User(
        id=PLATFORM_ADMIN_USER_ID,
        email="platform@test.com",
        email_verified=True,
        display_name="Platform Admin",
        platform_role=PlatformRole.SUPERADMIN,
    ),
    str(PLATFORM_SUPPORT_USER_ID): User(
        id=PLATFORM_SUPPORT_USER_ID,
        email="support@test.com",
        email_verified=True,
        display_name="Support Admin",
        platform_role=PlatformRole.SUPPORT,
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


async def _test_optional_user(
    x_test_user_id: Annotated[str | None, Header()] = None,
) -> User | None:
    """Test-only override for ``get_optional_current_user``.

    Mirrors ``_test_current_user`` but returns ``None`` when no ``X-Test-User-ID``
    header is present (the anonymous case the public-demo carve-out keys off), while
    still 401ing an explicit-but-unknown user id (a bad credential, not absence).
    """
    if x_test_user_id is None:
        return None
    if x_test_user_id in _USERS:
        return _USERS[x_test_user_id]
    raise HTTPException(
        status_code=http_status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated",
        headers={"WWW-Authenticate": "Bearer"},
    )


def _seed_admin(session: Session, tenant_id: uuid.UUID) -> None:
    """Seed an admin User + Member + Administrator position for the tenant (idempotent).

    Ensures requests made via the test client pass the require() permission check —
    the seeded member holds the Administrator position, which maps to the
    is_admin Administrators functional role, bypassing all individual checks.
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
        functional_role = FunctionalRole(
            tenant_id=tenant_id,
            name="Administrators",
            slug="administrators",
            is_admin=True,
            is_system=True,
        )
        session.add(functional_role)
        session.flush()
        position = Position(
            tenant_id=tenant_id,
            name="Administrator",
            slug="administrator",
            applies_to=PositionScope.ADULT,
            is_system=True,
        )
        session.add(position)
        session.flush()
        session.add(
            PositionFunctionalRole(
                tenant_id=tenant_id,
                position_id=position.id,
                functional_role_id=functional_role.id,
            )
        )
        session.add(
            MemberPositionAssignment(
                tenant_id=tenant_id, member_id=member_id, position_id=position.id
            )
        )
        position_member = Position(
            tenant_id=tenant_id,
            name="Member",
            slug="member",
            applies_to=PositionScope.ANY,
            is_system=True,
            is_default=True,
        )
        session.add(position_member)
        session.flush()


def _set_shared_overrides(db_session: Session) -> None:
    app.dependency_overrides[get_db] = lambda: db_session
    # Platform routes use AdminDbDep; wire the same test session so platform
    # tests work without DATABASE_URL_ADMIN being set (self-hosted / test mode).
    app.dependency_overrides[get_admin_db] = lambda: db_session
    app.dependency_overrides[get_tenant_id] = _simple_tenant_id
    app.dependency_overrides[get_current_user] = _test_current_user
    app.dependency_overrides[get_optional_current_user] = _test_optional_user


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
def import_worker(db_session: Session, monkeypatch: pytest.MonkeyPatch):  # type: ignore[no-untyped-def]
    """Bind the async import worker's SessionLocal to the test engine; return a drainer.

    The worker (app/core/import_jobs.py) runs on its own SessionLocal rather than the
    request session. Pointing it at the same in-memory engine lets a test drive the
    full POST → drain → poll flow synchronously. Returns ``run_import_pass``.
    """
    from sqlalchemy.orm import sessionmaker as _sessionmaker

    worker_session = _sessionmaker(bind=db_session.get_bind(), autoflush=False, future=True)
    monkeypatch.setattr("app.core.import_jobs.SessionLocal", worker_session)
    from app.core.import_jobs import run_import_pass

    return run_import_pass


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


@pytest.fixture
def support_client(db_session: Session) -> Generator[TestClient, None, None]:
    """TestClient authenticated as a non-superadmin platform admin (``support`` role).

    Used to verify superadmin-only actions reject lower-tier platform roles.
    """
    _set_shared_overrides(db_session)
    with TestClient(app, headers={"X-Test-User-ID": str(PLATFORM_SUPPORT_USER_ID)}) as c:
        yield c
    app.dependency_overrides.clear()
