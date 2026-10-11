"""Фабрика асинхронных сессий и FastAPI-зависимость."""

from __future__ import annotations

from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.engine import get_engine

_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_session_factory() -> async_sessionmaker[AsyncSession]:
    """Фабрика сессий приложения (создаётся лениво и кэшируется)."""
    global _session_factory
    if _session_factory is None:
        _session_factory = async_sessionmaker(
            bind=get_engine(),
            class_=AsyncSession,
            expire_on_commit=False,
            autoflush=False,
        )
    return _session_factory


def reset_session_factory() -> None:
    """Сбросить фабрику сессий (после подмены движка в тестах)."""
    global _session_factory
    _session_factory = None


def session_scope() -> AsyncSession:
    """Сессия в ручном режиме (CLI, сервисы вне HTTP-запроса)."""
    return get_session_factory()()


async def get_session() -> AsyncIterator[AsyncSession]:
    """FastAPI-зависимость: сессия на время запроса.

    Транзакцию открывает и фиксирует тот, кто пишет (сервис, CLI).
    Чтение идёт без явной транзакции.
    """
    session = get_session_factory()()
    try:
        yield session
    finally:
        await session.close()


__all__ = [
    "get_session",
    "get_session_factory",
    "reset_session_factory",
    "session_scope",
]
