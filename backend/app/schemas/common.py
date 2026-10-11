"""Общие схемы: периоды, деньги, ошибки, служебные ответы."""

from __future__ import annotations

from enum import StrEnum
from typing import Annotated

from pydantic import BaseModel, Field


class PeriodKind(StrEnum):
    """Период оборота продаж (контракт, 1.3)."""

    day = "day"
    week = "week"
    month = "month"
    quarter = "quarter"
    year = "year"


class DebtorKind(StrEnum):
    """Вид задолженности (контракт, 1.5)."""

    receivable = "receivable"
    payable = "payable"


class ErrorDetail(BaseModel):
    """Тело ошибки API бэкенда."""

    code: str = Field(description="Машиночитаемый код ошибки", examples=["kpi_unavailable"])
    message: str = Field(
        description="Текст ошибки для пользователя",
        examples=["Данные 1С недоступны: превышено время ожидания"],
    )


class ErrorResponse(BaseModel):
    """Ответ с ошибкой: ``{"detail": {...}}``."""

    detail: ErrorDetail


class HealthResponse(BaseModel):
    """``GET /health`` — служебная проверка (контракт, 2.3)."""

    status: str = Field(default="ok", description="Состояние сервиса", examples=["ok"])
    database: str = Field(default="ok", description="Состояние базы данных", examples=["ok"])
    oneC: str = Field(
        default="unavailable",
        description="Доступность HTTP-сервиса 1С",
        examples=["ok", "unavailable"],
    )


class MessageResponse(BaseModel):
    """Простой ответ с текстом (например, выход из системы)."""

    message: str = Field(description="Текст результата")


class Bucket(BaseModel):
    """Корзина возраста долга (контракт, 1.3).

    Интервалы как в типовой УНФ: 0–7, 8–14, 15–30, 31–60, свыше 60 дней.
    Числовых границ в ответе нет — интервал однозначно задан подписью.
    """

    label: str = Field(default="", description="Подпись интервала", examples=["8–14 дней"])
    amount: float = Field(default=0.0, description="Сумма в рублях с копейками")


class Counterparty(BaseModel):
    """Контрагент в списках топ-должников и топ-поставщиков."""

    name: str = Field(default="", description="Наименование контрагента")
    amount: float = Field(default=0.0, description="Сумма задолженности, рубли")
    overdue: float = Field(default=0.0, description="Просроченная часть, рубли")
    maxOverdueDays: int = Field(default=0, description="Максимальное число дней просрочки")


Money = Annotated[float, Field(description="Сумма в рублях с копейками")]


__all__ = [
    "Bucket",
    "Counterparty",
    "DebtorKind",
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "MessageResponse",
    "Money",
    "PeriodKind",
]
