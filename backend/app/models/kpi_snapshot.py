"""Снимок показателей, полученный из 1С.

Кэш показателей: ключ — ``kind`` + ``params_hash`` (хеш нормализованных
параметров запроса), значение — сырой ответ 1С в ``payload``. Хранится много
снимков на один ключ, чтобы при недоступности 1С можно было отдать устаревший.
"""

from datetime import datetime
from typing import Any, Final

from sqlalchemy import JSON, Index, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import PK_BIGINT, UtcDateTime, utcnow

KIND_SUMMARY: Final = "summary"
KIND_DYNAMICS: Final = "dynamics"
KIND_DEBTORS: Final = "debtors"
KIND_ORGANIZATIONS: Final = "organizations"
KINDS: Final[tuple[str, ...]] = (
    KIND_SUMMARY,
    KIND_DYNAMICS,
    KIND_DEBTORS,
    KIND_ORGANIZATIONS,
)

SOURCE_ONE_C: Final = "1c"
SOURCE_CACHE: Final = "cache"


class KpiSnapshot(Base):
    """Сохранённый ответ 1С вместе с параметрами запроса."""

    __tablename__ = "kpi_snapshots"
    __table_args__ = (
        UniqueConstraint("kind", "params_hash", name="uq_kpi_snapshots_kind_params_hash"),
        Index("ix_kpi_snapshots_kind_fetched_at", "kind", "fetched_at"),
    )

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    kind: Mapped[str] = mapped_column(String(32), nullable=False)
    params_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    params: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    fetched_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utcnow)
    source: Mapped[str] = mapped_column(String(16), nullable=False, default=SOURCE_ONE_C)

    def __repr__(self) -> str:
        return (
            f"<KpiSnapshot id={self.id} kind={self.kind!r} "
            f"hash={self.params_hash!r} fetched_at={self.fetched_at!r}>"
        )


__all__ = [
    "KINDS",
    "KIND_DEBTORS",
    "KIND_DYNAMICS",
    "KIND_ORGANIZATIONS",
    "KIND_SUMMARY",
    "SOURCE_CACHE",
    "SOURCE_ONE_C",
    "KpiSnapshot",
]
