"""Окружение Alembic.

Особенности, без которых миграции ломаются на SQLite:

* ``render_as_batch=True`` — SQLite не умеет ALTER COLUMN, Alembic пересоздаёт таблицу;
* ``render_item`` — собственный тип :class:`UtcDateTime` должен попадать в миграцию
  как ``app.db.types.UtcDateTime()``, иначе автогенерация выдаёт неработающий код.

Строка подключения берётся из ``DATABASE_URL`` (``app.core.config``).
"""

from __future__ import annotations

import asyncio
from logging.config import fileConfig
from typing import TYPE_CHECKING, Any, Literal

from alembic import context

from app.core.config import get_settings
from app.db.base import Base
from app.db.engine import create_engine_for
from app.db.types import UtcDateTime
from app.models import KpiSnapshot, Organization, User  # noqa: F401 - регистрация метаданных

if TYPE_CHECKING:
    from alembic.autogenerate.api import AutogenContext

config = context.config
if config.config_file_name is not None:
    fileConfig(config.config_file_name, disable_existing_loggers=False)

target_metadata = Base.metadata


def get_url() -> str:
    """URL базы для миграций.

    Приоритет: значение, переданное в конфигурации Alembic (используется тестами),
    затем ``DATABASE_URL`` из настроек приложения — единственный источник истины
    в обычной работе.
    """
    configured = config.get_main_option("sqlalchemy.url", None)
    if configured:
        return configured
    return get_settings().database_url


def render_item(type_: str, obj: Any, autogen_context: AutogenContext) -> str | Literal[False]:
    """Отобразить собственный тип в тексте миграции.

    Возврат ``False`` означает «рисуй как обычно» — так работают все типы,
    кроме нашего ``UtcDateTime``. Именно ``False``, а не ``None``: Alembic
    считает любое другое значение готовым текстом (тогда колонка пропадёт).
    """
    if type_ == "type" and isinstance(obj, UtcDateTime):
        autogen_context.imports.add("from app.db.types import UtcDateTime")
        return "UtcDateTime()"
    return False


def include_object(
    obj: Any,  # noqa: ARG001
    name: str | None,
    type_: str,
    reflected: bool,  # noqa: ARG001
    compare_to: Any,  # noqa: ARG001
) -> bool:
    """Не тащить в миграции служебные объекты (например, sqlite_sequence)."""
    return not (type_ == "table" and name in {"sqlite_sequence", "spatial_ref_sys"})


def run_migrations_offline() -> None:
    """Сформировать SQL без подключения к базе (``alembic upgrade --sql``)."""
    context.configure(
        url=get_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
        render_item=render_item,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Any) -> None:
    """Настроить контекст и выполнить миграции на готовом соединении."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        render_as_batch=True,
        render_item=render_item,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Выполнить миграции через async-движок приложения."""
    # Движок создаём тем же кодом, что и приложение: он же заводит каталог
    # для файла SQLite (var/) и включает PRAGMA foreign_keys. URL обязателен
    # явно: в тестах он отличается от DATABASE_URL из .env.
    settings_obj = get_settings().model_copy(update={"database_url": get_url()})
    engine = create_engine_for(settings_obj)
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


def run_migrations_online() -> None:
    """Выполнить миграции с подключением к базе."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
