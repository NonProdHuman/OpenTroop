"""Import queue driver abstraction (GH-240), mirroring EMAIL_BACKEND / the outbox.

``enqueue_import_job`` is the single seam the router calls after it persists an
``ImportJob``. ``IMPORT_QUEUE_BACKEND`` selects the driver once:

- ``inprocess`` (default) — a no-op: the in-process drain loop
  (``IMPORT_LOOP_ENABLED``) or the ``drain-import-jobs`` CLI picks the queued job
  up. Right for self-host, dev, and Cloud Run with CPU always allocated.
- ``cloudtasks`` — push the job to a dedicated worker Cloud Run service via a
  Cloud Tasks HTTP task with an OIDC token. The worker's ``POST /import/jobs/execute``
  verifies that token and calls :func:`process_import_job`. Cloud Tasks owns retry,
  rate control, and scale-to-zero; the worker has a long request timeout.

The Cloud Tasks call uses the REST API through the existing ``httpx2`` client and a
metadata-server access token — no extra SDK dependency (ADR 0007).
"""

from __future__ import annotations

import base64
import json
import logging
import uuid

import httpx2 as httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

# A metadata-server URL (returns the instance's access token), not a credential.
_METADATA_TOKEN_URL = "http://metadata.google.internal/computeMetadata/v1/instance/service-accounts/default/token"  # noqa: S105, E501


def enqueue_import_job(job_id: uuid.UUID) -> None:
    """Dispatch a persisted, queued job to the configured worker."""
    backend = settings.import_queue_backend
    if backend == "inprocess":
        # The lifespan loop / drain CLI will pick it up on the next tick.
        return
    if backend == "cloudtasks":
        _enqueue_cloudtasks(job_id)
        return
    raise RuntimeError(f"Unknown IMPORT_QUEUE_BACKEND: {backend!r}")


def _metadata_access_token() -> str:
    resp = httpx.get(
        _METADATA_TOKEN_URL,
        headers={"Metadata-Flavor": "Google"},
        timeout=10.0,
    )
    resp.raise_for_status()
    token: str = resp.json()["access_token"]
    return token


def _enqueue_cloudtasks(job_id: uuid.UUID) -> None:
    """Create a Cloud Tasks HTTP task that POSTs the job to the worker (OIDC-authed)."""
    if not (settings.cloudtasks_queue_path and settings.import_worker_url):
        raise RuntimeError(
            "IMPORT_QUEUE_BACKEND=cloudtasks requires CLOUDTASKS_QUEUE_PATH and "
            "IMPORT_WORKER_URL to be set."
        )
    body = base64.b64encode(json.dumps({"job_id": str(job_id)}).encode()).decode()
    task: dict[str, object] = {
        "httpRequest": {
            "httpMethod": "POST",
            "url": settings.import_worker_url,
            "headers": {"Content-Type": "application/json"},
            "body": body,
            "oidcToken": {
                "serviceAccountEmail": settings.import_worker_service_account,
                "audience": settings.import_worker_url,
            },
        }
    }
    url = f"https://cloudtasks.googleapis.com/v2/{settings.cloudtasks_queue_path}/tasks"
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {_metadata_access_token()}"},
        json={"task": task},
        timeout=30.0,
    )
    resp.raise_for_status()
    logger.info("Enqueued import job %s to Cloud Tasks", job_id.hex)
