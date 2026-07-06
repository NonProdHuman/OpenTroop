"""Deploy-path guardrails for the global advancement catalog (GH-241).

A deployed environment that never runs ``seed-advancement`` has no ``Rank`` rows,
so the TWH importer silently skips every advancement record. These tests cover the
two guards that make that state loud: the startup WARNING, and the Dockerfile CMD
that seeds on release. The importer-side skip-warning behaviour lives in
``test_import_twh_advancement.py``.
"""

import logging
from pathlib import Path

from sqlalchemy.orm import Session, sessionmaker

from app import main
from app.core.advancement_catalog import catalog_is_empty, load_catalog


def test_catalog_is_empty_true_when_unseeded(db_session: Session) -> None:
    assert catalog_is_empty(db_session) is True


def test_catalog_is_empty_false_after_seed(db_session: Session) -> None:
    load_catalog(db_session)
    db_session.commit()
    assert catalog_is_empty(db_session) is False


def test_startup_warns_when_catalog_empty(db_session: Session, caplog, monkeypatch) -> None:
    testing_session = sessionmaker(bind=db_session.get_bind(), future=True)
    monkeypatch.setattr("app.core.database.SessionLocal", testing_session)
    with caplog.at_level(logging.WARNING, logger="app.startup"):
        main._warn_if_advancement_catalog_empty()
    assert any("Advancement catalog is empty" in r.message for r in caplog.records)


def test_startup_silent_when_catalog_seeded(db_session: Session, caplog, monkeypatch) -> None:
    load_catalog(db_session)
    db_session.commit()
    testing_session = sessionmaker(bind=db_session.get_bind(), future=True)
    monkeypatch.setattr("app.core.database.SessionLocal", testing_session)
    with caplog.at_level(logging.WARNING, logger="app.startup"):
        main._warn_if_advancement_catalog_empty()
    assert not any("Advancement catalog is empty" in r.message for r in caplog.records)


def test_dockerfile_seeds_advancement_on_release() -> None:
    """The release entrypoint must seed the catalog after migrations, before uvicorn."""
    dockerfile = (Path(__file__).resolve().parents[1] / "Dockerfile").read_text()
    cmd = next(line for line in dockerfile.splitlines() if line.startswith("CMD"))
    assert "alembic upgrade head" in cmd
    assert "seed-advancement" in cmd
    assert cmd.index("alembic upgrade head") < cmd.index("seed-advancement") < cmd.index("uvicorn")
