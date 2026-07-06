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


class JsonDict(TypeDecorator[dict[str, Any] | None]):
    """A JSON object — native JSON on Postgres, serialized TEXT on SQLite.

    Same dialect strategy as :class:`JsonList`; used for free-form structured
    blobs such as an import job's per-entity progress counts and final summary.
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:  # noqa: ANN401
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSON())
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value: dict[str, Any] | None, dialect: Any) -> str | None:  # noqa: ANN401
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value  # type: ignore[return-value]  # native JSON handles it
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect: Any) -> dict[str, Any] | None:  # noqa: ANN401
        if value is None:
            return None
        if isinstance(value, dict):
            return value
        return json.loads(value)  # type: ignore[no-any-return]


class JsonObjectList(TypeDecorator[list[dict[str, Any]] | None]):
    """A JSON list of objects — native JSON on Postgres, serialized TEXT on SQLite.

    Same dialect strategy as :class:`JsonList`; used for structured condition
    lists such as ``Requirement.metrics`` (see ``docs`` in GH-92).
    """

    impl = Text
    cache_ok = True

    def load_dialect_impl(self, dialect: Any) -> Any:  # noqa: ANN401
        if dialect.name == "postgresql":
            return dialect.type_descriptor(JSON())
        return dialect.type_descriptor(Text())

    def process_bind_param(
        self,
        value: list[dict[str, Any]] | None,
        dialect: Any,  # noqa: ANN401
    ) -> str | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            return value  # type: ignore[return-value]  # native JSON handles it
        return json.dumps(value)

    def process_result_value(self, value: Any, dialect: Any) -> list[dict[str, Any]] | None:  # noqa: ANN401
        if value is None:
            return None
        if isinstance(value, list):
            return value
        return json.loads(value)  # type: ignore[no-any-return]
