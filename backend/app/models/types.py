"""Dialect-agnostic SQLAlchemy column types.

The test suite runs on SQLite while production uses PostgreSQL. These custom
types abstract over dialect differences so the same ORM model works on both.
"""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import Text, TypeDecorator
from sqlalchemy.types import JSON


class JsonList(TypeDecorator[list[str] | None]):
    """A JSON list stored as native JSON on Postgres and TEXT on SQLite.

    SQLite's built-in JSON support is unreliable across versions, so we
    serialize to a TEXT column there. On Postgres we use the native JSON type
    for index and query support.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:  # noqa: ANN401
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSON())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: list[str] | None, dialect: Any) -> str | None:  # noqa: ANN401
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value  # type: ignore[return-value]  # native JSON handles it
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect: Any) -> list[str] | None:  # noqa: ANN401
        if value is None:
            return None
        if isinstance(value, list):
            return value
        return json.loads(value)  # type: ignore[no-any-return]
