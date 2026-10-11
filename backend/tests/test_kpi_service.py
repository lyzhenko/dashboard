"""Кэш показателей: свежесть, устаревшие данные, недоступность 1С."""

from __future__ import annotations

from datetime import timedelta
from typing import Any

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import (
    JWT_TEST_SECRET,
    FakeOneCClient,
    sample_summary,
)

from app.core.config import Settings
from app.core.errors import KpiUnavailableError
from app.db.types import utcnow
from app.integrations.one_c import OneCUnavailable
from app.models.kpi_snapshot import KIND_SUMMARY, KpiSnapshot
from app.services import kpi_service


def make_settings(ttl: int = 300) -> Settings:
    return Settings(jwt_secret=JWT_TEST_SECRET, kpi_cache_ttl_seconds=ttl, _env_file=None)


async def test_cache_key_is_stable_and_param_order_independent() -> None:
    first = kpi_service.build_cache_key("kpi", {"date": "2026-10-11", "period": "month"})
    second = kpi_service.build_cache_key("kpi", {"period": "month", "date": "2026-10-11"})
    other = kpi_service.build_cache_key("kpi", {"date": "2026-10-12", "period": "month"})
    assert first[0] == second[0]
    assert first[0] != other[0]
    assert len(first[0]) == 64


async def test_first_call_goes_to_one_c_and_saves_snapshot(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    payload = await kpi_service.get_summary(
        session, fake_one_c, date="2026-10-11", settings_obj=make_settings()
    )

    assert fake_one_c.call_count == 1
    assert payload["meta"]["source"] == "1c"
    assert payload["meta"]["cached"] is False
    assert payload["meta"]["stale"] is False
    assert payload["meta"]["ageSeconds"] == 0
    assert payload["sales"]["revenue"] == 500000.0

    stored = (await session.execute(select(KpiSnapshot))).scalars().all()
    assert len(stored) == 1
    assert stored[0].kind == KIND_SUMMARY
    assert stored[0].payload["sales"]["revenue"] == 500000.0


async def test_second_call_is_served_from_cache(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    settings = make_settings()
    await kpi_service.get_summary(session, fake_one_c, date="2026-10-11", settings_obj=settings)
    payload = await kpi_service.get_summary(
        session, fake_one_c, date="2026-10-11", settings_obj=settings
    )

    assert fake_one_c.call_count == 1, "второй запрос не должен идти в 1С"
    assert payload["meta"]["cached"] is True
    assert payload["meta"]["source"] == "cache"
    assert payload["sales"]["revenue"] == 500000.0


async def test_different_parameters_use_different_cache_entries(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    settings = make_settings()
    await kpi_service.get_summary(session, fake_one_c, date="2026-10-11", settings_obj=settings)
    await kpi_service.get_summary(
        session, fake_one_c, date="2026-10-10", period="week", settings_obj=settings
    )

    assert fake_one_c.call_count == 2
    assert len((await session.execute(select(KpiSnapshot))).scalars().all()) == 2


async def test_expired_snapshot_is_refreshed(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    settings = make_settings(ttl=300)
    await kpi_service.get_summary(session, fake_one_c, date="2026-10-11", settings_obj=settings)

    snapshot = (await session.execute(select(KpiSnapshot))).scalar_one()
    snapshot.fetched_at = utcnow() - timedelta(seconds=400)
    await session.commit()

    payload = await kpi_service.get_summary(
        session, fake_one_c, date="2026-10-11", settings_obj=settings
    )

    assert fake_one_c.call_count == 2, "устаревший снимок должен обновляться"
    assert payload["meta"]["cached"] is False
    assert payload["meta"]["stale"] is False


async def test_stale_snapshot_is_returned_when_one_c_is_down(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    settings = make_settings(ttl=300)
    await kpi_service.get_summary(session, fake_one_c, date="2026-10-11", settings_obj=settings)

    snapshot = (await session.execute(select(KpiSnapshot))).scalar_one()
    snapshot.fetched_at = utcnow() - timedelta(seconds=3600)
    await session.commit()

    fake_one_c.fail_with = OneCUnavailable("превышено время ожидания")
    payload = await kpi_service.get_summary(
        session, fake_one_c, date="2026-10-11", settings_obj=settings
    )

    assert payload["meta"]["stale"] is True
    assert payload["meta"]["cached"] is True
    assert payload["meta"]["ageSeconds"] >= 3600
    assert payload["sales"]["revenue"] == 500000.0, "дашборд не должен остаться пустым"


async def test_unavailable_without_snapshot_gives_503(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    fake_one_c.fail_with = OneCUnavailable("нет соединения")

    with pytest.raises(KpiUnavailableError, match="Данные 1С недоступны"):
        await kpi_service.get_summary(session, fake_one_c, date="2026-10-11")


async def test_unauthorized_in_one_c_gives_503_not_401(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    from app.integrations.one_c import OneCUnauthorized

    fake_one_c.fail_with = OneCUnauthorized("1С отклонила учётные данные")

    with pytest.raises(KpiUnavailableError, match="учётные данные"):
        await kpi_service.get_summary(session, fake_one_c)


async def test_refresh_ignores_fresh_cache(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    settings = make_settings()
    await kpi_service.get_summary(session, fake_one_c, date="2026-10-11", settings_obj=settings)
    payload = await kpi_service.refresh_summary(
        session, fake_one_c, date="2026-10-11", settings_obj=settings
    )

    assert fake_one_c.call_count == 2
    assert payload["meta"]["cached"] is False

    stored = (await session.execute(select(KpiSnapshot))).scalars().all()
    assert len(stored) == 1, "снимок обновляется, а не дублируется"


async def test_unchanged_payload_updates_timestamp_without_new_row(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    settings = make_settings()
    await kpi_service.get_summary(session, fake_one_c, date="2026-10-11", settings_obj=settings)
    first = (await session.execute(select(KpiSnapshot))).scalar_one()
    first_time = first.fetched_at

    await kpi_service.refresh_summary(session, fake_one_c, date="2026-10-11", settings_obj=settings)
    session.expire_all()
    stored = (await session.execute(select(KpiSnapshot))).scalars().all()

    assert len(stored) == 1
    assert stored[0].fetched_at >= first_time


async def test_changed_payload_replaces_snapshot(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    settings = make_settings()
    await kpi_service.get_summary(session, fake_one_c, date="2026-10-11", settings_obj=settings)
    fake_one_c.summary = sample_summary(revenue=777000.0)
    payload = await kpi_service.refresh_summary(
        session, fake_one_c, date="2026-10-11", settings_obj=settings
    )

    stored = (await session.execute(select(KpiSnapshot))).scalars().all()
    assert len(stored) == 1
    assert stored[0].payload["sales"]["revenue"] == 777000.0
    assert payload["sales"]["revenue"] == 777000.0


async def test_empty_one_c_answer_is_not_an_error(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    from tests.conftest import empty_summary

    fake_one_c.summary = empty_summary()
    payload = await kpi_service.get_summary(session, fake_one_c, settings_obj=make_settings())

    assert payload["asOf"] == "2026-10-11"
    assert payload["period"]["kind"] == "month"
    assert "money" not in payload, "сервис не выдумывает блоки — их заполняет схема ответа"


async def test_dynamics_are_cached_separately(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    settings = make_settings()
    await kpi_service.get_dynamics(session, fake_one_c, months=6, settings_obj=settings)
    await kpi_service.get_dynamics(session, fake_one_c, months=6, settings_obj=settings)
    await kpi_service.get_dynamics(session, fake_one_c, months=12, settings_obj=settings)

    assert fake_one_c.call_count == 2
    stored = (await session.execute(select(KpiSnapshot))).scalars().all()
    assert {row.kind for row in stored} == {"dynamics"}


async def test_debtors_payload_is_cached(session: AsyncSession, fake_one_c: FakeOneCClient) -> None:
    settings = make_settings()
    payload = await kpi_service.get_debtors(
        session, fake_one_c, kind="receivable", limit=5, settings_obj=settings
    )
    assert payload["kind"] == "receivable"
    assert payload["items"][0]["name"] == "ООО «Василёк»"
    assert fake_one_c.calls[0][1]["limit"] == 5


async def test_organizations_cached_and_fallback_on_failure(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    settings = make_settings()
    first = await kpi_service.get_organizations(session, fake_one_c, settings_obj=settings)
    assert first["items"][0]["inn"] == "7701234567"

    # Справочник в кэше на час: второй вызов не идёт в 1С.
    second = await kpi_service.get_organizations(session, fake_one_c, settings_obj=settings)
    assert fake_one_c.call_count == 1
    assert second == first

    # Принудительное обновление при недоступной 1С отдаёт последний известный справочник.
    fake_one_c.fail_with = OneCUnavailable("таймаут")
    third = await kpi_service.get_organizations(
        session, fake_one_c, force=True, settings_obj=settings
    )
    assert third == first


async def test_organizations_without_cache_and_without_one_c_raises(
    session: AsyncSession, fake_one_c: FakeOneCClient
) -> None:
    fake_one_c.fail_with = OneCUnavailable("таймаут")
    with pytest.raises(KpiUnavailableError):
        await kpi_service.get_organizations(session, fake_one_c)


async def test_one_c_health_reports_unavailable(fake_one_c: FakeOneCClient) -> None:
    assert await kpi_service.one_c_health(fake_one_c) == "ok"
    fake_one_c.fail_with = OneCUnavailable("таймаут")
    assert await kpi_service.one_c_health(fake_one_c) == "unavailable"


async def test_meta_marks_stale_by_age() -> None:
    old = utcnow() - timedelta(seconds=600)
    meta: dict[str, Any] = kpi_service.build_meta(fetched_at=old, cached=True, ttl_seconds=300)
    assert meta["stale"] is True
    assert meta["source"] == "cache"
    assert meta["ageSeconds"] >= 600


async def test_fetch_rejects_unknown_kind(fake_one_c: FakeOneCClient) -> None:
    with pytest.raises(ValueError, match="Неизвестный вид показателя"):
        await kpi_service._fetch(fake_one_c, "unknown", {})
