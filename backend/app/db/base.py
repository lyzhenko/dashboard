"""DeclarativeBase и общие соглашения об именах ограничений.

Имена ограничений заданы явно, иначе Alembic в batch-режиме не может
пересоздать таблицу в SQLite (у безымянных ограничений нет имени).
"""

from __future__ import annotations

from sqlalchemy import MetaData
from sqlalchemy.orm import DeclarativeBase

NAMING_CONVENTION = {
    "ix": "ix_%(table_name)s_%(column_0_N_name)s",
    "uq": "uq_%(table_name)s_%(column_0_N_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_N_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Базовый класс моделей."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)

    def __repr__(self) -> str:
        return f"<{type(self).__name__} id={getattr(self, 'id', None)!r}>"


__all__ = ["NAMING_CONVENTION", "Base"]
