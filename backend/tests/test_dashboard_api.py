"""API дашборда: свежесть данных, пустая база, ошибки 1С, параметры запроса."""

from __future__ import annotations

from datetime import timedelta

from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import FakeOneCClient, empty_summary

from app.db.types import utcnow
from app.integrations.one_c import OneCUnavailable
from app.models.kpi_snapshot import KpiSnapshot

SUMMARY_URL = "/api/v1/dashboard/summary"
REQUIRED_BLOCKS = (
    "meta",
    "asOf",
    "period",
    "organization",
    "money",
    "sales",
    "receivables",
    "payables",
    "stock",
    "orders",
    "topDebtors",
    "topSuppliers",
)


async def test_summary_requires_authorization(client: AsyncClient) -> None:
    response = await client.get(SUMMARY_URL)
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"


async def test_summary_contains_all_blocks_and_fresh_meta(
    client: AsyncClient, demo_user: AsyncSession, auth_headers: dict[str, str]
) -> None:
    response = await client.get(SUMMARY_URL, headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    for block in REQUIRED_BLOCKS:
        assert block in body, f"в ответе нет блока {block}"

    assert body["meta"]["source"] == "1c"
    assert body["meta"]["cached"] is False
    assert body["meta"]["stale"] is False
    assert body["meta"]["ageSeconds"] == 0
    assert "T" in body["meta"]["fetchedAt"]
    assert "+" not in body["meta"]["fetchedAt"], "момент времени отдаётся без пояса"

    assert body["sales"]["revenue"] == 500000.0
    assert body["sales"]["revenueNet"] == 416666.67
    assert body["orders"]["positions"] == 128.5
    assert body["orders"]["paidAmount"] == 600000.0
    assert body["receivables"]["buckets"][0] == {"label": "0–7 дней", "amount": 650000.0}
    assert "advancesToSuppliers" not in body["receivables"]
    assert body["organization"]["name"] == "ООО «Ромашка»"


async def test_second_request_is_served_from_cache(
    client: AsyncClient,
    demo_user: AsyncSession,
    auth_headers: dict[str, str],
    fake_one_c: FakeOneCClient,
) -> None:
    await client.get(SUMMARY_URL, headers=auth_headers)
    response = await client.get(SUMMARY_URL, headers=auth_headers)

    assert fake_one_c.call_count == 1
    assert response.json()["meta"]["cached"] is True
    assert response.json()["meta"]["source"] == "cache"


async def test_organization_filter_is_passed_to_one_c(
    client: AsyncClient,
    demo_user: AsyncSession,
    auth_headers: dict[str, str],
    fake_one_c: FakeOneCClient,
) -> None:
    organization = "0a1b2c3d-1111-2222-3333-444455556666"
    response = await client.get(
        SUMMARY_URL,
        params={"date": "2026-10-11", "period": "quarter", "organization": organization},
        headers=auth_headers,
    )

    assert response.status_code == 200
    assert fake_one_c.calls[0] == (
        "kpi",
        {"date": "2026-10-11", "period": "quarter", "organization": organization},
    )


async def test_summary_without_data_returns_zeros_not_error(
    client: AsyncClient,
    demo_user: AsyncSession,
    auth_headers: dict[str, str],
    fake_one_c: FakeOneCClient,
) -> None:
    fake_one_c.summary = empty_summary()

    response = await client.get(SUMMARY_URL, headers=auth_headers)

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["money"]["total"] == 0.0
    assert body["sales"]["revenueDeltaPct"] == 0.0
    assert body["sales"]["marginPct"] == 0.0
    assert body["receivables"]["overduePct"] == 0.0
    assert body["receivables"]["buckets"] == []
    assert body["topDebtors"] == []
    assert body["orders"]["portfolio"] == 0.0
    assert body["organization"] is None


async def test_unavailable_one_c_without_cache_returns_503(
    client: AsyncClient,
    demo_user: AsyncSession,
    auth_headers: dict[str, str],
    fake_one_c: FakeOneCClient,
) -> None:
    fake_one_c.fail_with = OneCUnavailable("превышено время ожидания")

    response = await client.get(SUMMARY_URL, headers=auth_headers)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "kpi_unavailable"
    assert "Данные 1С недоступны" in response.json()["detail"]["message"]


async def test_stale_cache_is_returned_with_stale_flag(
    client: AsyncClient,
    session: AsyncSession,
    demo_user: AsyncSession,
    auth_headers: dict[str, str],
    fake_one_c: FakeOneCClient,
) -> None:
    first = await client.get(SUMMARY_URL, headers=auth_headers)
    assert first.status_code == 200

    snapshot = (await session.execute(select(KpiSnapshot))).scalar_one()
    snapshot.fetched_at = utcnow() - timedelta(seconds=4000)
    await session.commit()

    fake_one_c.fail_with = OneCUnavailable("таймаут")
    response = await client.get(SUMMARY_URL, headers=auth_headers)

    assert response.status_code == 200, "устаревшие данные лучше пустого дашборда"
    body = response.json()
    assert body["meta"]["stale"] is True
    assert body["meta"]["cached"] is True
    assert body["meta"]["ageSeconds"] >= 4000
    assert body["sales"]["revenue"] == 500000.0


async def test_refresh_forces_new_request(
    client: AsyncClient,
    demo_user: AsyncSession,
    auth_headers: dict[str, str],
    fake_one_c: FakeOneCClient,
) -> None:
    await client.get(SUMMARY_URL, headers=auth_headers)
    response = await client.post("/api/v1/dashboard/refresh", headers=auth_headers)

    assert response.status_code == 200
    assert fake_one_c.call_count == 2
    assert response.json()["meta"]["cached"] is False


async def test_summary_rejects_bad_parameters(
    client: AsyncClient, demo_user: AsyncSession, auth_headers: dict[str, str]
) -> None:
    bad_date = await client.get(SUMMARY_URL, params={"date": "11.10.2026"}, headers=auth_headers)
    assert bad_date.status_code == 422
    assert bad_date.json()["detail"]["code"] == "validation_error"

    bad_period = await client.get(SUMMARY_URL, params={"period": "decade"}, headers=auth_headers)
    assert bad_period.status_code == 422

    bad_org = await client.get(
        SUMMARY_URL, params={"organization": "не-uuid"}, headers=auth_headers
    )
    assert bad_org.status_code == 422
    assert "организации" in bad_org.json()["detail"]["message"]


async def test_dynamics_returns_items(
    client: AsyncClient,
    demo_user: AsyncSession,
    auth_headers: dict[str, str],
    fake_one_c: FakeOneCClient,
) -> None:
    response = await client.get(
        "/api/v1/dashboard/dynamics", params={"months": 6}, headers=auth_headers
    )

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["month"] == "2026-09"
    assert item["marginPct"] == 23.33
    assert fake_one_c.calls[0][1]["months"] == 6


async def test_dynamics_months_are_limited(
    client: AsyncClient, demo_user: AsyncSession, auth_headers: dict[str, str]
) -> None:
    too_many = await client.get(
        "/api/v1/dashboard/dynamics", params={"months": 100}, headers=auth_headers
    )
    assert too_many.status_code == 422


async def test_debtors_returns_counterparties(
    client: AsyncClient,
    demo_user: AsyncSession,
    auth_headers: dict[str, str],
    fake_one_c: FakeOneCClient,
) -> None:
    response = await client.get(
        "/api/v1/dashboard/debtors",
        params={"kind": "payable", "limit": 3},
        headers=auth_headers,
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["kind"] == "receivable"  # так ответила «1С» — бэкенд не переписывает данные
    assert body["items"][0]["buckets"][0]["label"] == "0–7 дней"
    assert fake_one_c.calls[0][1] == {
        "kind": "payable",
        "limit": 3,
        "date": None,
        "organization": None,
    }


async def test_debtors_reject_bad_kind(
    client: AsyncClient, demo_user: AsyncSession, auth_headers: dict[str, str]
) -> None:
    response = await client.get(
        "/api/v1/dashboard/debtors", params={"kind": "unknown"}, headers=auth_headers
    )
    assert response.status_code == 422


async def test_organizations_endpoint(
    client: AsyncClient,
    demo_user: AsyncSession,
    auth_headers: dict[str, str],
    fake_one_c: FakeOneCClient,
) -> None:
    response = await client.get("/api/v1/dashboard/organizations", headers=auth_headers)

    assert response.status_code == 200
    item = response.json()["items"][0]
    assert item["id"] == "0a1b2c3d-1111-2222-3333-444455556666"
    assert item["isDefault"] is False


async def test_organizations_are_unavailable_only_without_cache(
    client: AsyncClient,
    demo_user: AsyncSession,
    auth_headers: dict[str, str],
    fake_one_c: FakeOneCClient,
) -> None:
    fake_one_c.fail_with = OneCUnavailable("таймаут")

    response = await client.get("/api/v1/dashboard/organizations", headers=auth_headers)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "kpi_unavailable"


async def test_unexpected_one_c_shape_gives_503_not_500(
    client: AsyncClient,
    demo_user: AsyncSession,
    auth_headers: dict[str, str],
    fake_one_c: FakeOneCClient,
) -> None:
    fake_one_c.summary = {"sales": "это не блок, а строка"}

    response = await client.get(SUMMARY_URL, headers=auth_headers)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "kpi_unavailable"


async def test_all_dashboard_endpoints_require_token(client: AsyncClient) -> None:
    for method, url in (
        ("get", SUMMARY_URL),
        ("get", "/api/v1/dashboard/dynamics"),
        ("get", "/api/v1/dashboard/debtors"),
        ("get", "/api/v1/dashboard/organizations"),
        ("post", "/api/v1/dashboard/refresh"),
    ):
        response = await getattr(client, method)(url)
        assert response.status_code == 401, f"{url} доступен без токена"
