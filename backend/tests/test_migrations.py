"""Схема базы: миграции не должны расходиться с моделями.

Этот тест ловит две ошибки, которые иначе проявляются только на стенде:

* модель изменена, а миграция не создана;
* хук ``render_item`` в ``migrations/env.py`` возвращает не ``False``, и Alembic
  считает результат готовым текстом — тогда колонки молча пропадают из миграции.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import create_engine
from tests.conftest import TEST_DB_URL

from app.db.base import Base


@pytest.fixture
def migrated_database() -> Iterator[str]:
    """URL уже мигрированной тестовой базы (её поднимает ``test_database``)."""
    assert Path(TEST_DB_URL.split("///", 1)[1]).exists(), "тестовая база не создана"
    yield TEST_DB_URL


def test_migrations_match_models(migrated_database: str) -> None:
    sync_url = migrated_database.replace("+aiosqlite", "")
    engine = create_engine(sync_url)
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(
                connection,
                opts={"compare_type": True, "compare_server_default": True},
            )
            diffs = compare_metadata(context, Base.metadata)
    finally:
        engine.dispose()

    assert diffs == [], f"модели и миграции расходятся: {diffs}"


def test_migrations_create_all_tables(migrated_database: str) -> None:
    from sqlalchemy import inspect

    engine = create_engine(migrated_database.replace("+aiosqlite", ""))
    try:
        tables = set(inspect(engine).get_table_names())
    finally:
        engine.dispose()

    expected = {"users", "kpi_snapshots", "organizations", "alembic_version"}
    assert expected <= tables, f"нет таблиц: {expected - tables}"


async def test_sqlite_foreign_keys_are_enabled() -> None:
    """PRAGMA foreign_keys=ON выставляется на каждом соединении SQLite."""
    from sqlalchemy import text

    from app.core.config import get_settings
    from app.db.engine import create_engine_for

    settings = get_settings()
    assert settings.is_sqlite, "тесты идут на SQLite"

    engine = create_engine_for(settings)
    try:
        async with engine.connect() as connection:
            value = (await connection.execute(text("PRAGMA foreign_keys"))).scalar()
    finally:
        await engine.dispose()
    assert value == 1


def test_variant_primary_key_is_rendered_as_integer_in_sqlite(migrated_database: str) -> None:
    """В SQLite первичный ключ обязан быть INTEGER, иначе нет автоинкремента."""
    from sqlalchemy import text

    engine = create_engine(migrated_database.replace("+aiosqlite", ""))
    try:
        with engine.connect() as connection:
            ddl = connection.execute(
                text("SELECT sql FROM sqlite_master WHERE name = 'users'")
            ).scalar_one()
    finally:
        engine.dispose()

    normalized = " ".join(str(ddl).lower().split())
    assert "id integer" in normalized, ddl
