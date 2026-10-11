"""Кэш показателей и обращение к 1С (контракт, 2.2).

Правила сервиса:

* свежий снимок из ``kpi_snapshots`` отдаётся без обращения к 1С;
* устаревший снимок обновляется, а при недоступности 1С отдаётся как есть
  с ``stale: true`` — дашборд не должен оставаться пустым (AGENT.md, п. 15);
* ``503 kpi_unavailable`` — только когда снимка нет вовсе.
"""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any, Final, Protocol

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.core.errors import KpiUnavailableError
from app.core.logging import get_logger
from app.db.types import isoformat_utc, utcnow
from app.integrations.one_c import OneCClient, OneCError, OneCUnauthorized, OneCUnavailable
from app.models.kpi_snapshot import (
    KIND_DEBTORS,
    KIND_DYNAMICS,
    KIND_ORGANIZATIONS,
    KIND_SUMMARY,
    SOURCE_CACHE,
    SOURCE_ONE_C,
    KpiSnapshot,
)

logger = get_logger(__name__)

#: Справочник организаций меняется редко, поэтому кэшируется на час.
ORGANIZATIONS_CACHE_TTL_SECONDS: Final = 3600


class SupportsOneC(Protocol):
    """Минимальный интерфейс клиента 1С, нужный сервису (удобно подменять в тестах)."""

    async def health(self) -> dict[str, Any]: ...

    async def organizations(self) -> list[dict[str, Any]]: ...

    async def kpi(
        self,
        date: str | None = None,
        period: str | None = None,
        organization: str | None = None,
    ) -> dict[str, Any]: ...

    async def dynamics(
        self,
        months: int | None = None,
        date: str | None = None,
        organization: str | None = None,
    ) -> dict[str, Any]: ...

    async def debtors(
        self,
        kind: str | None = None,
        limit: int | None = None,
        date: str | None = None,
        organization: str | None = None,
    ) -> dict[str, Any]: ...


def build_cache_key(kind: str, params: dict[str, Any]) -> tuple[str, dict[str, Any], str]:
    """Ключ снимка: вид запроса, нормализованные параметры и их хеш."""
    normalized = {
        str(key): value for key, value in sorted(params.items(), key=lambda item: str(item[0]))
    }
    raw = json.dumps([kind, normalized], ensure_ascii=False, sort_keys=True, default=str)
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return digest, normalized, digest[:16]


def age_seconds(fetched_at: datetime, *, now: datetime | None = None) -> int:
    """Возраст данных в секундах (не меньше нуля)."""
    moment = now or utcnow()
    reference = fetched_at if fetched_at.tzinfo else fetched_at.replace(tzinfo=UTC)
    return max(0, int((moment - reference).total_seconds()))


def build_meta(
    *,
    fetched_at: datetime,
    cached: bool,
    ttl_seconds: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Блок ``meta``: откуда данные, когда получены, насколько устарели."""
    age = age_seconds(fetched_at, now=now)
    return {
        "source": SOURCE_CACHE if cached else SOURCE_ONE_C,
        "fetchedAt": isoformat_utc(fetched_at),
        "ageSeconds": age,
        "stale": age > ttl_seconds,
        "cached": cached,
    }


async def _load_snapshot(session: AsyncSession, kind: str, params_hash: str) -> KpiSnapshot | None:
    """Последний снимок по ключу (свежий или устаревший)."""
    result = await session.execute(
        select(KpiSnapshot)
        .where(KpiSnapshot.kind == kind, KpiSnapshot.params_hash == params_hash)
        .order_by(KpiSnapshot.fetched_at.desc(), KpiSnapshot.id.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def _store_snapshot(
    session: AsyncSession,
    *,
    kind: str,
    params: dict[str, Any],
    params_hash: str,
    payload: dict[str, Any],
    previous: KpiSnapshot | None = None,
) -> datetime:
    """Сохранить снимок. Возвращает момент получения данных.

    Если 1С вернула ровно то же, что уже лежит в базе, снимок не перезаписывается:
    обновляется только ``fetched_at`` — данные свежие, но не изменились.
    """
    moment = utcnow()
    if previous is not None and previous.payload == payload:
        previous.fetched_at = moment
        previous.source = SOURCE_ONE_C
        await session.commit()
        return moment

    if previous is not None:
        await session.delete(previous)
        await session.flush()

    session.add(
        KpiSnapshot(
            kind=kind,
            params_hash=params_hash,
            params=params,
            payload=payload,
            fetched_at=moment,
            source=SOURCE_ONE_C,
        )
    )
    await session.commit()
    return moment


def _unavailable(exc: OneCError) -> KpiUnavailableError:
    """Ошибка 1С → ошибка контракта (503 ``kpi_unavailable``)."""
    if isinstance(exc, OneCUnauthorized):
        logger.error("1С отклонила учётные данные: %s", exc)
        return KpiUnavailableError(f"Данные 1С недоступны: {exc}")
    if isinstance(exc, OneCUnavailable):
        logger.warning("1С недоступна: %s", exc)
        return KpiUnavailableError(f"Данные 1С недоступны: {exc}")
    logger.warning("1С вернула ошибку запроса: %s", exc)
    return KpiUnavailableError(str(exc))


async def _get_block(
    session: AsyncSession,
    client: SupportsOneC,
    settings_obj: Settings,
    *,
    kind: str,
    params: dict[str, Any],
    force: bool = False,
) -> dict[str, Any]:
    """Общая логика «кэш → 1С → снимок → устаревшие данные»."""
    params_hash, normalized_params, _ = build_cache_key(kind, params)
    snapshot = await _load_snapshot(session, kind, params_hash)
    ttl = settings_obj.kpi_cache_ttl_seconds

    if snapshot is not None and not force:
        age = age_seconds(snapshot.fetched_at)
        if age <= ttl:
            logger.debug("Кэш: %s (%s) свежий, возраст %s с", kind, params_hash, age)
            return {
                "payload": dict(snapshot.payload or {}),
                "meta": build_meta(fetched_at=snapshot.fetched_at, cached=True, ttl_seconds=ttl),
            }

    try:
        payload = await _fetch(client, kind, params)
    except OneCError as exc:
        if snapshot is not None:
            logger.warning(
                "1С недоступна (%s), отдаю устаревший снимок %s от %s",
                exc,
                params_hash,
                isoformat_utc(snapshot.fetched_at),
            )
            return {
                "payload": dict(snapshot.payload or {}),
                "meta": build_meta(fetched_at=snapshot.fetched_at, cached=True, ttl_seconds=ttl),
            }
        raise _unavailable(exc) from exc

    fetched_at = await _store_snapshot(
        session,
        kind=kind,
        params=normalized_params,
        params_hash=params_hash,
        payload=payload,
        previous=snapshot,
    )
    return {
        "payload": payload,
        "meta": build_meta(fetched_at=fetched_at, cached=False, ttl_seconds=ttl),
    }


async def _fetch(client: SupportsOneC, kind: str, params: dict[str, Any]) -> dict[str, Any]:
    """Запросить у 1С нужный блок."""
    if kind == KIND_SUMMARY:
        return await client.kpi(
            date=params.get("date"),
            period=params.get("period"),
            organization=params.get("organization"),
        )
    if kind == KIND_DYNAMICS:
        return await client.dynamics(
            months=params.get("months"),
            date=params.get("date"),
            organization=params.get("organization"),
        )
    if kind == KIND_DEBTORS:
        return await client.debtors(
            kind=params.get("kind"),
            limit=params.get("limit"),
            date=params.get("date"),
            organization=params.get("organization"),
        )
    if kind == KIND_ORGANIZATIONS:
        items = await client.organizations()
        return {"items": items}
    msg = f"Неизвестный вид показателя: {kind}"
    raise ValueError(msg)


async def get_summary(
    session: AsyncSession,
    client: SupportsOneC,
    *,
    date: str | None = None,
    period: str | None = None,
    organization: str | None = None,
    force: bool = False,
    settings_obj: Settings | None = None,
) -> dict[str, Any]:
    """Сводка для главного экрана с блоком ``meta``."""
    result = await _get_block(
        session,
        client,
        settings_obj or default_settings,
        kind=KIND_SUMMARY,
        params={"date": date, "period": period, "organization": organization},
        force=force,
    )
    payload: dict[str, Any] = result["payload"]
    return {**payload, "meta": result["meta"]}


async def get_dynamics(
    session: AsyncSession,
    client: SupportsOneC,
    *,
    months: int | None = None,
    date: str | None = None,
    organization: str | None = None,
    settings_obj: Settings | None = None,
) -> dict[str, Any]:
    """Динамика по месяцам."""
    result = await _get_block(
        session,
        client,
        settings_obj or default_settings,
        kind=KIND_DYNAMICS,
        params={"months": months, "date": date, "organization": organization},
    )
    return result["payload"]


async def get_debtors(
    session: AsyncSession,
    client: SupportsOneC,
    *,
    kind: str | None = None,
    limit: int | None = None,
    date: str | None = None,
    organization: str | None = None,
    settings_obj: Settings | None = None,
) -> dict[str, Any]:
    """Детализация задолженности по контрагентам."""
    result = await _get_block(
        session,
        client,
        settings_obj or default_settings,
        kind=KIND_DEBTORS,
        params={"kind": kind, "limit": limit, "date": date, "organization": organization},
    )
    return result["payload"]


async def get_organizations(
    session: AsyncSession,
    client: SupportsOneC,
    *,
    force: bool = False,
    settings_obj: Settings | None = None,
) -> dict[str, Any]:
    """Список организаций; кэшируется на час, при недоступности 1С отдаётся из базы."""
    settings_used = settings_obj or default_settings
    ttl = max(settings_used.kpi_cache_ttl_seconds, ORGANIZATIONS_CACHE_TTL_SECONDS)
    result = await session.execute(
        select(KpiSnapshot)
        .where(KpiSnapshot.kind == KIND_ORGANIZATIONS)
        .order_by(KpiSnapshot.fetched_at.desc(), KpiSnapshot.id.desc())
        .limit(1)
    )
    snapshot = result.scalar_one_or_none()

    if snapshot is not None and not force and age_seconds(snapshot.fetched_at) <= ttl:
        return dict(snapshot.payload or {})

    try:
        items = await client.organizations()
    except OneCError as exc:
        if snapshot is not None:
            logger.warning("1С недоступна (%s), отдаю справочник организаций из базы", exc)
            return dict(snapshot.payload or {})
        raise _unavailable(exc) from exc

    payload: dict[str, Any] = {"items": items}
    await _store_snapshot(
        session,
        kind=KIND_ORGANIZATIONS,
        params={},
        params_hash=build_cache_key(KIND_ORGANIZATIONS, {})[0],
        payload=payload,
        previous=snapshot,
    )
    return payload


async def refresh_summary(
    session: AsyncSession,
    client: SupportsOneC,
    *,
    date: str | None = None,
    period: str | None = None,
    organization: str | None = None,
    settings_obj: Settings | None = None,
) -> dict[str, Any]:
    """``POST /dashboard/refresh`` — принудительно перечитать сводку из 1С."""
    return await get_summary(
        session,
        client,
        date=date,
        period=period,
        organization=organization,
        force=True,
        settings_obj=settings_obj,
    )


async def count_snapshots(session: AsyncSession) -> int:
    """Сколько снимков лежит в кэше (диагностика)."""
    result = await session.execute(select(func.count()).select_from(KpiSnapshot))
    return int(result.scalar_one())


async def one_c_health(client: SupportsOneC) -> str:
    """``ok`` / ``unavailable`` для ``GET /health``."""
    try:
        await client.health()
    except OneCError as exc:
        logger.info("Проверка 1С: недоступна (%s)", exc)
        return "unavailable"
    except Exception:
        logger.exception("Проверка 1С: неожиданная ошибка")
        return "unavailable"
    return "ok"


def make_client(settings_obj: Settings | None = None) -> OneCClient:
    """Создать клиент 1С (вынесено для читаемости роутеров и CLI)."""
    return OneCClient(settings_obj or default_settings)


__all__ = [
    "ORGANIZATIONS_CACHE_TTL_SECONDS",
    "SupportsOneC",
    "age_seconds",
    "build_cache_key",
    "build_meta",
    "count_snapshots",
    "get_debtors",
    "get_dynamics",
    "get_organizations",
    "get_summary",
    "make_client",
    "one_c_health",
    "refresh_summary",
]
