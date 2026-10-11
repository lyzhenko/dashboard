"""Модели SQLAlchemy.

Импорт всех моделей обязателен до запуска Alembic: иначе таблица не попадёт
в метаданные, и автогенерация миграции её не увидит.

В файлах моделей намеренно нет ``from __future__ import annotations``:
SQLAlchemy 2.1 разбирает аннотации ``Mapped[...]`` и с отложенными
аннотациями не может определить типы колонок.
"""

from app.models.kpi_snapshot import KpiSnapshot
from app.models.organization import Organization
from app.models.user import User

__all__ = ["KpiSnapshot", "Organization", "User"]
