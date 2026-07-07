"""Async import job queue behaviour (GH-240): idempotency, lifecycle, worker auth."""

from collections.abc import Callable
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.enums import ImportJobStatus
from app.models.import_job import ImportJob
from tests.conftest import TENANT_A

_FIXTURE = Path(__file__).parent / "fixtures" / "sample_twh_minimal.xml"


def _post(client: TestClient):  # type: ignore[no-untyped-def]
    with open(_FIXTURE, "rb") as f:
        return client.post("/import/twh", files={"file": ("export.xml", f, "application/xml")})


# ---------------------------------------------------------------------------
# 202 + queued job, then lifecycle
# ---------------------------------------------------------------------------


def test_post_returns_202_and_queued_job(client: TestClient) -> None:
    r = _post(client)
    assert r.status_code == 202, r.text
    body = r.json()
    assert body["status"] == "queued"
    assert body["original_filename"] == "export.xml"
    assert body["payload_bytes"] > 0
    assert body["summary"] is None
    assert body["started_at"] is None


def test_job_reaches_succeeded_with_progress(
    client: TestClient, import_worker: Callable[[], dict]
) -> None:
    job_id = _post(client).json()["id"]
    stats = import_worker()
    assert stats == {"queued": 1, "ran": 1}

    body = client.get(f"/import/jobs/{job_id}").json()
    assert body["status"] == "succeeded"
    assert body["stage"] is None  # cleared on success
    # Chunked-commit progress mirrors the final summary once done.
    assert body["progress"]["members"] == 5
    assert body["summary"]["members"] == 5
    assert body["started_at"] is not None
    assert body["finished_at"] is not None


def test_list_jobs_returns_newest_first(client: TestClient, db_session: Session) -> None:
    from datetime import UTC, datetime

    older = ImportJob(
        tenant_id=TENANT_A,
        status=ImportJobStatus.FAILED,
        source_timezone="UTC",
        payload=b"",
        payload_bytes=0,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        updated_at=datetime(2026, 1, 1, tzinfo=UTC),
    )
    newer = ImportJob(
        tenant_id=TENANT_A,
        status=ImportJobStatus.FAILED,
        source_timezone="UTC",
        payload=b"",
        payload_bytes=0,
        created_at=datetime(2026, 6, 1, tzinfo=UTC),
        updated_at=datetime(2026, 6, 1, tzinfo=UTC),
    )
    db_session.add_all([older, newer])
    db_session.commit()

    ids = [j["id"] for j in client.get("/import/jobs").json()]
    assert ids[:2] == [str(newer.id), str(older.id)]


def test_get_unknown_job_404(client: TestClient) -> None:
    import uuid

    r = client.get(f"/import/jobs/{uuid.uuid4()}")
    assert r.status_code == 404


# ---------------------------------------------------------------------------
# Idempotency (GH-240 §4)
# ---------------------------------------------------------------------------


def test_second_import_while_active_is_409(client: TestClient) -> None:
    assert _post(client).status_code == 202
    r = _post(client)
    assert r.status_code == 409
    assert "already in progress" in r.json()["detail"]


def test_reimport_after_success_is_409(
    client: TestClient, import_worker: Callable[[], dict]
) -> None:
    assert _post(client).status_code == 202
    import_worker()
    r = _post(client)
    assert r.status_code == 409
    assert "already contains imported" in r.json()["detail"]


def test_duplicate_key_race_lands_failed_not_500(
    client: TestClient, db_session: Session, import_worker: Callable[[], dict]
) -> None:
    """If duplicate rows slip past the pre-check, the worker fails the job cleanly."""
    from app.models.enums import MemberType
    from app.models.member import Member

    job_id = _post(client).json()["id"]
    # 12345678 is a fixture scout's BSA number; pre-seeding it makes the import hit
    # the partial unique index on (tenant_id, bsa_id) mid-run.
    db_session.add(
        Member(
            tenant_id=TENANT_A,
            first_name="Dup",
            last_name="Licate",
            bsa_id="12345678",
            member_type=MemberType.SCOUT,
        )
    )
    db_session.commit()

    import_worker()
    body = client.get(f"/import/jobs/{job_id}").json()
    assert body["status"] == "failed"
    assert body["error"]  # actionable message, not a raw traceback


# ---------------------------------------------------------------------------
# Worker execute endpoint (Cloud Tasks) — inert under the default backend
# ---------------------------------------------------------------------------


def test_worker_execute_forbidden_under_inprocess_backend(client: TestClient) -> None:
    import uuid

    r = client.post("/import/jobs/execute", json={"job_id": str(uuid.uuid4())})
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# Direct worker unit: atomic claim is single-shot
# ---------------------------------------------------------------------------


def test_process_is_idempotent_under_double_delivery(
    client: TestClient, import_worker: Callable[[], dict], monkeypatch: pytest.MonkeyPatch
) -> None:
    from app.core import import_jobs

    job_id = _post(client).json()["id"]
    import uuid as _uuid

    jid = _uuid.UUID(job_id)
    # First call claims + runs; the second must no-op (already terminal).
    assert import_jobs.process_import_job(jid) is True
    assert import_jobs.process_import_job(jid) is False
    assert client.get(f"/import/jobs/{job_id}").json()["status"] == "succeeded"
