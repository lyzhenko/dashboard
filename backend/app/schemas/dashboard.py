"""Схемы дашборда: сводка, динамика, задолженность, организации, метаданные кэша.

Источник данных — HTTP-сервис расширения 1С (``docs/API-КОНТРАКТ.md``, раздел 1).
Схемы намеренно «мягкие»: у всех блоков есть значения по умолчанию, поэтому
пустой ответ 1С (база только что развёрнута) превращается в нули и пустые
массивы, а не в ошибку валидации.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.schemas.common import Bucket, Counterparty, PeriodKind

__all__ = [
    "DebtorItem",
    "DebtorsResponse",
    "DynamicsItem",
    "DynamicsResponse",
    "KpiMeta",
    "MoneyBlock",
    "OrdersBlock",
    "OrganizationItem",
    "OrganizationRef",
    "OrganizationsResponse",
    "PayablesBlock",
    "PeriodBlock",
    "ReceivablesBlock",
    "SalesBlock",
    "StockBlock",
    "SummaryResponse",
]


class KpiMeta(BaseModel):
    """Блок ``meta`` — свежесть данных (контракт, 2.2)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "source": "1c",
                "fetchedAt": "2026-10-11T07:40:03",
                "ageSeconds": 42,
                "stale": False,
                "cached": True,
            }
        }
    )

    source: str = Field(
        default="1c",
        description="Откуда взяты данные: `1c` — свежий ответ 1С, `cache` — снимок из кэша",
        examples=["1c", "cache"],
    )
    fetchedAt: datetime = Field(description="Момент получения данных от 1С")
    ageSeconds: int = Field(description="Возраст данных в секундах")
    stale: bool = Field(
        description="Данные старше `KPI_CACHE_TTL_SECONDS` — нужна кнопка обновления"
    )
    cached: bool = Field(description="Ответ отдан из кэша, а не из свежего запроса")


class PeriodBlock(BaseModel):
    """Период, за который посчитаны обороты (контракт, 1.3)."""

    model_config = ConfigDict(populate_by_name=True)

    kind: PeriodKind = Field(default=PeriodKind.month, description="Вид периода")
    from_: str = Field(default="", alias="from", description="Начало периода, YYYY-MM-DD")
    to: str = Field(default="", description="Конец периода, YYYY-MM-DD")
    prevFrom: str = Field(default="", description="Начало предыдущего периода")
    prevTo: str = Field(default="", description="Конец предыдущего периода")


class OrganizationRef(BaseModel):
    """Организация, по которой посчитана сводка."""

    id: str | None = Field(default=None, description="UUID организации из 1С")
    name: str = Field(default="", description="Наименование организации")


class MoneyBlock(BaseModel):
    """Денежные средства (контракт, 1.3)."""

    total: float = Field(default=0.0, description="Всего денег, рубли")
    accounts: float = Field(default=0.0, description="На расчётных счетах, рубли")
    cash: float = Field(default=0.0, description="В кассе, рубли")
    currency: str = Field(default="RUB", description="Валюта показателя")


class SalesBlock(BaseModel):
    """Продажи за период и сравнение с предыдущим (контракт, 1.3)."""

    revenue: float = Field(default=0.0, description="Выручка с НДС, как считает УНФ, рубли")
    revenuePrev: float = Field(default=0.0, description="Выручка предыдущего периода")
    revenueDeltaPct: float = Field(
        default=0.0, description="Прирост выручки, % (0 при нулевой прошлой выручке)"
    )
    revenueNet: float = Field(default=0.0, description="Выручка без НДС, рубли")
    grossProfit: float = Field(default=0.0, description="Валовая прибыль за период")
    grossProfitPrev: float = Field(default=0.0, description="Валовая прибыль периода ранее")
    marginPct: float = Field(default=0.0, description="Рентабельность, % (0 при нулевой выручке)")
    documents: int = Field(default=0, description="Количество документов продажи за период")
    avgTicket: float = Field(default=0.0, description="Средний чек, рубли")


class ReceivablesBlock(BaseModel):
    """Дебиторская задолженность (контракт, 1.3)."""

    total: float = Field(default=0.0, description="Всего к получению, рубли")
    overdue: float = Field(default=0.0, description="Просроченная часть, рубли")
    overduePct: float = Field(default=0.0, description="Доля просрочки, % (0 при нулевом итоге)")
    buckets: list[Bucket] = Field(default_factory=list, description="Возраст долга по корзинам")


class PayablesBlock(BaseModel):
    """Кредиторская задолженность (контракт, 1.3)."""

    total: float = Field(default=0.0, description="Всего к оплате, рубли")
    overdue: float = Field(default=0.0, description="Просроченная часть, рубли")
    overduePct: float = Field(default=0.0, description="Доля просрочки, % (0 при нулевом итоге)")
    buckets: list[Bucket] = Field(default_factory=list, description="Возраст долга по корзинам")


class StockBlock(BaseModel):
    """Запасы на складах (контракт, 1.3)."""

    total: float = Field(default=0.0, description="Стоимость запасов, рубли")
    skuCount: int = Field(default=0, description="Номенклатура с ненулевым остатком")
    negativeCount: int = Field(default=0, description="Номенклатура с отрицательным остатком")


class OrdersBlock(BaseModel):
    """Портфель заказов покупателей (контракт, 1.3)."""

    portfolio: float = Field(default=0.0, description="Сумма открытых заказов, рубли")
    count: int = Field(default=0, description="Количество открытых заказов")
    positions: float = Field(default=0.0, description="Количество единиц к отгрузке")
    overdueCount: int = Field(default=0, description="Заказы с просроченной датой отгрузки")
    overdueAmount: float = Field(default=0.0, description="Сумма просроченных заказов")
    dueThisWeek: float = Field(default=0.0, description="К отгрузке в ближайшие 7 дней")
    orderedAmount: float = Field(default=0.0, description="Заказы, оформленные за период")
    paidAmount: float = Field(default=0.0, description="Оплаты по заказам за период")


class SummaryResponse(BaseModel):
    """``GET /dashboard/summary`` — сводка плюс блок свежести данных."""

    model_config = ConfigDict(populate_by_name=True)

    meta: KpiMeta = Field(description="Свежесть данных")
    generatedAt: str = Field(default="", description="Момент расчёта на стороне 1С")
    asOf: str = Field(default="", description="Дата, на которую считались остатки")
    period: PeriodBlock = Field(default_factory=PeriodBlock, description="Период оборотов")
    organization: OrganizationRef | None = Field(
        default=None, description="Организация (null — сводка по всем)"
    )
    money: MoneyBlock = Field(default_factory=MoneyBlock)
    sales: SalesBlock = Field(default_factory=SalesBlock)
    receivables: ReceivablesBlock = Field(default_factory=ReceivablesBlock)
    payables: PayablesBlock = Field(default_factory=PayablesBlock)
    stock: StockBlock = Field(default_factory=StockBlock)
    orders: OrdersBlock = Field(default_factory=OrdersBlock)
    topDebtors: list[Counterparty] = Field(
        default_factory=list, description="Топ-5 дебиторов по сумме"
    )
    topSuppliers: list[Counterparty] = Field(
        default_factory=list, description="Топ-5 поставщиков по сумме"
    )


class DynamicsItem(BaseModel):
    """Один месяц динамики (контракт, 1.4)."""

    month: str = Field(default="", description="Месяц в формате YYYY-MM", examples=["2025-11"])
    revenue: float = Field(default=0.0, description="Выручка месяца, рубли")
    grossProfit: float = Field(default=0.0, description="Валовая прибыль месяца")
    marginPct: float = Field(default=0.0, description="Рентабельность, %")


class DynamicsResponse(BaseModel):
    """``GET /dashboard/dynamics`` — выручка и прибыль по месяцам."""

    items: list[DynamicsItem] = Field(default_factory=list, description="Месяцы по возрастанию")


class DebtorItem(BaseModel):
    """Контрагент в детализации задолженности (контракт, 1.5)."""

    name: str = Field(default="", description="Наименование контрагента")
    amount: float = Field(default=0.0, description="Сумма задолженности, рубли")
    overdue: float = Field(default=0.0, description="Просроченная часть, рубли")
    maxOverdueDays: int = Field(default=0, description="Максимальная просрочка, дней")
    buckets: list[Bucket] = Field(default_factory=list, description="Разбивка по срокам")


class DebtorsResponse(BaseModel):
    """``GET /dashboard/debtors`` — детализация по контрагентам."""

    kind: str = Field(default="receivable", description="Вид задолженности")
    asOf: str = Field(default="", description="Дата остатков")
    total: float = Field(default=0.0, description="Всего, рубли")
    overdue: float = Field(default=0.0, description="Просрочено, рубли")
    items: list[DebtorItem] = Field(
        default_factory=list, description="Контрагенты по убыванию суммы"
    )


class OrganizationItem(BaseModel):
    """Организация в списке для выбора (контракт, 1.2)."""

    id: str = Field(description="UUID организации из 1С")
    name: str = Field(default="", description="Наименование")
    inn: str = Field(default="", description="ИНН")
    isDefault: bool = Field(default=False, description="Основная организация")

    @field_validator("id", mode="before")
    @classmethod
    def _stringify_id(cls, value: Any) -> Any:
        """UUID из 1С приходит строкой, но приведём и «сырое» значение."""
        return str(value) if value is not None else value


class OrganizationsResponse(BaseModel):
    """``GET /dashboard/organizations`` — список организаций."""

    items: list[OrganizationItem] = Field(default_factory=list, description="Организации базы 1С")
