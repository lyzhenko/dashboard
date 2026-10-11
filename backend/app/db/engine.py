"""Асинхронный движок SQLAlchemy.

Диалект выбирается по ``DATABASE_URL``: локально SQLite (``aiosqlite``),
на стенде PostgreSQL 17 (``psycopg``). ``PRAGMA foreign_keys=ON`` включается
только для SQLite — иначе внешние ключи там молча не проверяются.
"""

from __future__ import annotations

import re
from collections.abc import AsyncIterator, Iterator
from pathlib import Path
from typing import Any, Final
from urllib.parse import parse_qs, urlsplit

from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

from app.core.config import Settings, settings

SQLITE_PREFIX: Final = "sqlite+aiosqlite:///"
_BUSY_TIMEOUT_MS: Final = 5000
ENGINE_FACTORY_KEY: Final = "app_engine"

_engine: AsyncEngine | None = None


def _sqlite_connect_args(database_url: str) -> tuple[dict[str, Any], str | None]:
    """Аргументы подключения и путь к файлу БД для SQLite."""
    query = parse_qs(urlsplit(database_url).query)
    timeout_seconds = float(query.get("timeout", ["5"])[0])
    connect_args: dict[str, Any] = {"timeout": timeout_seconds}

    raw_path = database_url.split("///", 1)[-1]
    file_path: str | None = raw_path or None
    if file_path is not None and ":memory:" not in file_path:
        # Каталог var/ может отсутствовать (свежий клон репозитория).
        Path(file_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
    return connect_args, file_path


def _attach_sqlite_pragmas(async_engine: AsyncEngine) -> None:
    """Включить внешние ключи и таймаут блокировки для SQLite.

    Прагмы выставляются на каждое соединение: SQLite не хранит их в файле базы,
    а ``PRAGMA foreign_keys`` действует только в пределах соединения.
    """

    @event.listens_for(async_engine.sync_engine, "connect")
    def _on_connect(dbapi_connection: Any, _record: Any) -> None:
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute(f"PRAGMA busy_timeout={_BUSY_TIMEOUT_MS}")
        finally:
            cursor.close()


def create_engine_for(settings_obj: Settings) -> AsyncEngine:
    """Создать движок по настройкам."""
    url = settings_obj.database_url
    kwargs: dict[str, Any] = {
        "echo": settings_obj.db_echo,
        "pool_pre_ping": not url.startswith("sqlite"),
    }

    if url.startswith("sqlite"):
        connect_args, _ = _sqlite_connect_args(url)
        kwargs["connect_args"] = connect_args

    engine = create_async_engine(url, **kwargs)
    if url.startswith("sqlite"):
        _attach_sqlite_pragmas(engine)
    return engine


def get_engine() -> AsyncEngine:
    """Движок приложения (создаётся лениво)."""
    global _engine
    if _engine is None:
        _engine = create_engine_for(settings)
    return _engine


def set_engine(engine: AsyncEngine | None) -> None:
    """Подменить движок (тесты) или сбросить его."""
    global _engine
    _engine = engine


async def dispose_engine() -> None:
    """Закрыть пул соединений."""
    global _engine
    if _engine is not None:
        await _engine.dispose()
        _engine = None


def is_sqlite_url(url: str) -> bool:
    """Похоже ли на SQLite."""
    return bool(re.match(r"^sqlite", url))


async def check_database(
    engine: AsyncEngine | AsyncConnection | None = None,
) -> None:
    """Проверить доступность базы: ``SELECT 1``. Бросает исключение драйвера.

    Принимает и ``AsyncEngine``, и ``AsyncConnection`` — то, что вернул
    ``session.bind``: проверке нужен любой источник соединения.
    """
    if isinstance(engine, AsyncConnection):
        await engine.execute(text("SELECT 1"))
        return
    target = engine if isinstance(engine, AsyncEngine) else get_engine()
    async with target.connect() as connection:
        await connection.execute(text("SELECT 1"))


def iter_tables_metadata() -> Iterator[str]:
    """Имена таблиц приложения (для отладки и тестов)."""
    from app.db.base import Base

    yield from Base.metadata.tables


async def session_scope_engine() -> AsyncIterator[AsyncEngine]:
    """Вспомогательный генератор: движок с гарантированным закрытием."""
    engine = get_engine()
    try:
        yield engine
    finally:
        await engine.dispose()


__all__ = [
    "check_database",
    "create_engine_for",
    "dispose_engine",
    "get_engine",
    "is_sqlite_url",
    "iter_tables_metadata",
    "session_scope_engine",
    "set_engine",
]
