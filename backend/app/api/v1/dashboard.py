"""Показатели дашборда: сводка, динамика, задолженность, организации, обновление.

Роутер не содержит бизнес-логики: разбор параметров, вызов сервиса,
приведение ответа к схеме контракта.
"""

from __future__ import annotations

import uuid
from datetime import date as date_type
from typing import Annotated

from fastapi import APIRouter, Query, status
from pydantic import ValidationError

from app.api.deps import CurrentUser, OneCClientDep, SessionDep, SettingsDep
from app.core.errors import InvalidParamsError, KpiUnavailableError
from app.core.logging import get_logger
from app.schemas.common import DebtorKind, ErrorResponse, PeriodKind
from app.schemas.dashboard import (
    DebtorsResponse,
    DynamicsResponse,
    OrganizationsResponse,
    SummaryResponse,
)
from app.services import kpi_service

logger = get_logger(__name__)

router = APIRouter(prefix="/dashboard", tags=["Дашборд"])

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    status.HTTP_401_UNAUTHORIZED: {"model": ErrorResponse, "description": "Нет доступа"},
    status.HTTP_422_UNPROCESSABLE_CONTENT: {
        "model": ErrorResponse,
        "description": "Некорректные параметры",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "model": ErrorResponse,
        "description": "1С недоступна и закэшированных данных нет",
    },
}

DateQuery = Annotated[
    str | None,
    Query(
        description="Дата, на которую считаются остатки (YYYY-MM-DD). По умолчанию — сегодня.",
        pattern=r"^\d{4}-\d{2}-\d{2}$",
        examples=["2026-10-11"],
    ),
]
OrganizationQuery = Annotated[
    str | None,
    Query(
        description="UUID организации из 1С. Без параметра — сводка по всем организациям.",
        examples=["0a1b2c3d-1111-2222-3333-444455556666"],
    ),
]


def _parse_date(value: str | None) -> str | None:
    """Проверить дату и вернуть её в формате ``YYYY-MM-DD``."""
    if value is None:
        return None
    try:
        return date_type.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise InvalidParamsError(f"Некорректная дата: {value!r} (ожидается YYYY-MM-DD)") from exc


def _parse_organization(value: str | None) -> str | None:
    """Проверить UUID организации.

    Значение уходит в 1С как есть, но опечатка в UUID должна отсекаться здесь,
    а не превращаться в непонятную ошибку 1С.
    """
    if value is None:
        return None
    cleaned = value.strip()
    if not cleaned:
        return None
    try:
        uuid.UUID(cleaned)
    except ValueError as exc:
        msg = f"Некорректный идентификатор организации: {value!r}"
        raise InvalidParamsError(msg) from exc
    return cleaned


def _invalid_payload(exc: ValidationError, what: str) -> KpiUnavailableError:
    """Ответ 1С не соответствует контракту."""
    logger.warning("1С вернула неожиданный ответ (%s): %s", what, exc)
    return KpiUnavailableError(f"1С вернула неожиданный ответ ({what})")


@router.get(
    "/summary",
    response_model=SummaryResponse,
    summary="Сводка для главного экрана",
    description=(
        "Все блоки показателей плюс `meta` со свежестью данных. "
        "Данные берутся из кэша, если снимок не старше `KPI_CACHE_TTL_SECONDS`; "
        "при недоступности 1С отдаётся устаревший снимок с `stale: true`."
    ),
    responses=ERROR_RESPONSES,
)
async def summary(
    _: CurrentUser,
    session: SessionDep,
    client: OneCClientDep,
    settings: SettingsDep,
    date: DateQuery = None,
    period: Annotated[PeriodKind, Query(description="Период оборота продаж")] = PeriodKind.month,
    organization: OrganizationQuery = None,
) -> SummaryResponse:
    """Сводка за период и по организации."""
    payload = await kpi_service.get_summary(
        session,
        client,
        date=_parse_date(date),
        period=period.value,
        organization=_parse_organization(organization),
        settings_obj=settings,
    )
    try:
        return SummaryResponse.model_validate(payload)
    except ValidationError as exc:
        raise _invalid_payload(exc, "summary") from exc


@router.get(
    "/dynamics",
    response_model=DynamicsResponse,
    summary="Динамика выручки и прибыли по месяцам",
    description="Последние `months` месяцев (1–36), по возрастанию; последний — текущий, неполный.",
    responses=ERROR_RESPONSES,
)
async def dynamics(
    _: CurrentUser,
    session: SessionDep,
    client: OneCClientDep,
    settings: SettingsDep,
    months: Annotated[int, Query(ge=1, le=36, description="Сколько месяцев вернуть")] = 12,
    date: DateQuery = None,
    organization: OrganizationQuery = None,
) -> DynamicsResponse:
    """Данные для графика по месяцам."""
    payload = await kpi_service.get_dynamics(
        session,
        client,
        months=months,
        date=_parse_date(date),
        organization=_parse_organization(organization),
        settings_obj=settings,
    )
    try:
        return DynamicsResponse.model_validate(payload)
    except ValidationError as exc:
        raise _invalid_payload(exc, "dynamics") from exc


@router.get(
    "/debtors",
    response_model=DebtorsResponse,
    summary="Детализация задолженности по контрагентам",
    description="`receivable` — нам должны, `payable` — мы должны. Сортировка по сумме убыв.",
    responses=ERROR_RESPONSES,
)
async def debtors(
    _: CurrentUser,
    session: SessionDep,
    client: OneCClientDep,
    settings: SettingsDep,
    kind: Annotated[DebtorKind, Query(description="Вид задолженности")] = DebtorKind.receivable,
    limit: Annotated[int, Query(ge=1, le=100, description="Сколько контрагентов вернуть")] = 10,
    date: DateQuery = None,
    organization: OrganizationQuery = None,
) -> DebtorsResponse:
    """Список контрагентов с разбивкой по срокам."""
    payload = await kpi_service.get_debtors(
        session,
        client,
        kind=kind.value,
        limit=limit,
        date=_parse_date(date),
        organization=_parse_organization(organization),
        settings_obj=settings,
    )
    try:
        return DebtorsResponse.model_validate(payload)
    except ValidationError as exc:
        raise _invalid_payload(exc, "debtors") from exc


@router.get(
    "/organizations",
    response_model=OrganizationsResponse,
    summary="Список организаций",
    description=(
        "Организации из 1С для выбора на дашборде. "
        "Справочник кэшируется в базе; при недоступности 1С отдаётся последний известный."
    ),
    responses=ERROR_RESPONSES,
)
async def organizations(
    _: CurrentUser,
    session: SessionDep,
    client: OneCClientDep,
    settings: SettingsDep,
) -> OrganizationsResponse:
    """Организации для выпадающего списка."""
    payload = await kpi_service.get_organizations(session, client, settings_obj=settings)
    try:
        return OrganizationsResponse.model_validate(payload)
    except ValidationError as exc:
        raise _invalid_payload(exc, "organizations") from exc


@router.post(
    "/refresh",
    response_model=SummaryResponse,
    summary="Принудительно обновить сводку",
    description=(
        "Игнорирует кэш и перечитывает данные из 1С. "
        "Если 1С недоступна, но есть снимок — отдаётся он, с `stale: true`."
    ),
    responses=ERROR_RESPONSES,
)
async def refresh(
    _: CurrentUser,
    session: SessionDep,
    client: OneCClientDep,
    settings: SettingsDep,
    date: DateQuery = None,
    period: Annotated[PeriodKind, Query(description="Период оборота продаж")] = PeriodKind.month,
    organization: OrganizationQuery = None,
) -> SummaryResponse:
    """Обновить сводку из 1С (кнопка «обновить» на дашборде)."""
    payload = await kpi_service.refresh_summary(
        session,
        client,
        date=_parse_date(date),
        period=period.value,
        organization=_parse_organization(organization),
        settings_obj=settings,
    )
    try:
        return SummaryResponse.model_validate(payload)
    except ValidationError as exc:
        raise _invalid_payload(exc, "summary") from exc


__all__ = ["router"]
