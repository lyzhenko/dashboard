"""Собственные типы SQLAlchemy.

``UtcDateTime`` хранит момент времени в UTC и всегда возвращает его
осведомлённым (``tzinfo=UTC``). Это скрывает разницу между СУБД:

* SQLite не умеет хранить часовой пояс — значение приходит «наивным»;
* PostgreSQL с ``TIMESTAMP WITH TIME ZONE`` возвращает осведомлённое значение,
  приведённое к часовому поясу сессии.

Наружу (в JSON) такие значения уходят как ISO 8601 без пояса — как того
требует контракт.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy.engine import Dialect
from sqlalchemy.types import TypeDecorator

#: Первичный ключ-счётчик: ``BIGINT`` на PostgreSQL, ``INTEGER`` на SQLite.
#:
#: SQLite делает автоинкремент только для ``INTEGER PRIMARY KEY`` (алиас rowid);
#: ``BIGINT PRIMARY KEY`` там остаётся обычной колонкой и требует явного значения.
#: SQLAlchemy 2.1 больше не подменяет тип автоматически, поэтому подмена задана
#: явно через ``with_variant``.
PK_BIGINT = BigInteger().with_variant(Integer(), "sqlite")


def utcnow() -> datetime:
    """Текущий момент времени в UTC."""
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    """Привести момент времени к UTC, наивное значение считать UTC."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def isoformat_utc(value: datetime | None) -> str | None:
    """Строка ISO 8601 без часового пояса — формат контракта."""
    if value is None:
        return None
    return ensure_utc(value).replace(tzinfo=None).isoformat(timespec="seconds")


class UtcDateTime(TypeDecorator[datetime]):
    """Момент времени в UTC, независимо от диалекта СУБД."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Dialect) -> datetime | None:  # noqa: ARG002
        if value is None:
            return None
        if not isinstance(value, datetime):
            msg = f"UtcDateTime ожидает datetime, получено {type(value).__name__}"
            raise TypeError(msg)
        return ensure_utc(value)

    def process_result_value(self, value: Any, dialect: Dialect) -> datetime | None:  # noqa: ARG002
        if value is None:
            return None
        if not isinstance(value, datetime):
            msg = f"Из базы получено {type(value).__name__} вместо datetime"
            raise TypeError(msg)
        return ensure_utc(value)


__all__ = ["PK_BIGINT", "UtcDateTime", "ensure_utc", "isoformat_utc", "utcnow"]
