"""Run one import-queue drain pass (GH-240) — the cron/self-host belt.

Processes every queued TWH import job once. Pairs with the in-process loop
(``IMPORT_LOOP_ENABLED``) the same way ``drain-outbox`` pairs with the outbox loop.

Usage: uv run drain-import-jobs
"""

from __future__ import annotations


def main() -> None:
    from app.core.import_jobs import run_import_pass

    stats = run_import_pass()
    print(  # noqa: T201 — CLI output
        f"Import pass complete: {stats['queued']} queued, {stats['ran']} run"
    )


if __name__ == "__main__":
    main()
