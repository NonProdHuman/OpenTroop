"""Run one messaging outbox pass (GH-78) — the cron/self-host belt.

Usage: uv run drain-outbox
"""

from __future__ import annotations


def main() -> None:
    from app.core.outbox import run_outbox_pass

    stats = run_outbox_pass()
    print(  # noqa: T201 — CLI output
        f"Outbox pass complete: {stats['tenants']} tenant(s), "
        f"{stats['promoted']} scheduled promoted, {stats['emails_attempted']} emails attempted"
    )


if __name__ == "__main__":
    main()
