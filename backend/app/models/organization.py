"""Организация из 1С — для выбора на дашборде.

Справочник кэшируется в своей таблице: он меняется редко, а нужен на каждом
экране. Первичный ключ — UUID, пришедший из 1С.
"""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UtcDateTime, utcnow


class Organization(Base):
    """Организация (одна из нескольких в базе 1С)."""

    __tablename__ = "organizations"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    inn: Mapped[str] = mapped_column(String(12), nullable=False, default="")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    updated_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utcnow)

    def __repr__(self) -> str:
        return f"<Organization id={self.id} name={self.name!r} is_default={self.is_default}>"


__all__ = ["Organization"]
