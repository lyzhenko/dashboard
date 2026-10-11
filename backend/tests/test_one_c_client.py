"""Клиент HTTP-сервиса 1С: разбор ответов и ошибок (без реальной сети)."""

from __future__ import annotations

import httpx
import pytest
import respx
from tests.conftest import JWT_TEST_SECRET, sample_summary

from app.core.config import Settings
from app.integrations.one_c import OneCClient, OneCError, OneCUnauthorized, OneCUnavailable

BASE_URL = "http://one-c.test/dashboard/hs/dashboard"


def make_settings() -> Settings:
    return Settings(
        jwt_secret=JWT_TEST_SECRET,
        one_c_base_url=BASE_URL,
        one_c_user="Пользователь",
        one_c_password="пароль",
        one_c_timeout_seconds=5.0,
        _env_file=None,
    )


@pytest.fixture
def one_c() -> OneCClient:
    return OneCClient(make_settings())


@respx.mock
async def test_health_returns_payload(one_c: OneCClient) -> None:
    respx.get(f"{BASE_URL}/health").mock(
        return_value=httpx.Response(
            200, json={"status": "ok", "service": "D_DashboardApi", "version": "1.0.0"}
        )
    )
    payload = await one_c.health()
    assert payload["status"] == "ok"
    await one_c.aclose()


@respx.mock
async def test_basic_auth_header_is_sent(one_c: OneCClient) -> None:
    route = respx.get(f"{BASE_URL}/health").mock(return_value=httpx.Response(200, json={}))
    await one_c.health()
    request = route.calls[0].request
    assert request.headers["authorization"].startswith("Basic ")
    await one_c.aclose()


@respx.mock
async def test_organizations_returns_items(one_c: OneCClient) -> None:
    respx.get(f"{BASE_URL}/organizations").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "id": "0a1b2c3d-1111-2222-3333-444455556666",
                        "name": "ООО «Ромашка»",
                        "inn": "7701234567",
                        "isDefault": True,
                    }
                ]
            },
        )
    )
    items = await one_c.organizations()
    assert items[0]["inn"] == "7701234567"
    await one_c.aclose()


@respx.mock
async def test_organizations_without_items_gives_empty_list(one_c: OneCClient) -> None:
    respx.get(f"{BASE_URL}/organizations").mock(return_value=httpx.Response(200, json={}))
    assert await one_c.organizations() == []
    await one_c.aclose()


@respx.mock
async def test_kpi_passes_only_present_parameters(one_c: OneCClient) -> None:
    route = respx.get(f"{BASE_URL}/kpi").mock(
        return_value=httpx.Response(200, json=sample_summary())
    )
    payload = await one_c.kpi(date="2026-10-11", period="month")
    assert payload["asOf"] == "2026-10-11"
    request = route.calls[0].request
    assert dict(request.url.params) == {"date": "2026-10-11", "period": "month"}
    await one_c.aclose()


@respx.mock
async def test_dynamics_and_debtors_parameters(one_c: OneCClient) -> None:
    dynamics_route = respx.get(f"{BASE_URL}/dynamics").mock(
        return_value=httpx.Response(200, json={"items": []})
    )
    debtors_route = respx.get(f"{BASE_URL}/debtors").mock(
        return_value=httpx.Response(200, json={"kind": "payable", "items": []})
    )
    await one_c.dynamics(months=6, organization="0a1b2c3d-1111-2222-3333-444455556666")
    await one_c.debtors(kind="payable", limit=5, date="2026-10-11")

    assert dict(dynamics_route.calls[0].request.url.params) == {
        "months": "6",
        "organization": "0a1b2c3d-1111-2222-3333-444455556666",
    }
    assert dict(debtors_route.calls[0].request.url.params) == {
        "kind": "payable",
        "limit": "5",
        "date": "2026-10-11",
    }
    await one_c.aclose()


@respx.mock
async def test_timeout_becomes_unavailable(one_c: OneCClient) -> None:
    respx.get(f"{BASE_URL}/kpi").mock(side_effect=httpx.ReadTimeout("слишком долго"))
    with pytest.raises(OneCUnavailable, match="Не удалось обратиться к 1С"):
        await one_c.kpi()
    await one_c.aclose()


@respx.mock
async def test_connect_error_becomes_unavailable(one_c: OneCClient) -> None:
    respx.get(f"{BASE_URL}/kpi").mock(side_effect=httpx.ConnectError("нет соединения"))
    with pytest.raises(OneCUnavailable):
        await one_c.kpi()
    await one_c.aclose()


@respx.mock
async def test_server_error_uses_message_from_body(one_c: OneCClient) -> None:
    respx.get(f"{BASE_URL}/kpi").mock(
        return_value=httpx.Response(
            500,
            json={"error": {"code": "internal", "message": "Ошибка в запросе регистра"}},
        )
    )
    with pytest.raises(OneCUnavailable, match="Ошибка в запросе регистра"):
        await one_c.kpi()
    await one_c.aclose()


@respx.mock
async def test_unauthorized_is_separate_error(one_c: OneCClient) -> None:
    respx.get(f"{BASE_URL}/kpi").mock(
        return_value=httpx.Response(401, json={"error": {"code": "unauthorized"}})
    )
    with pytest.raises(OneCUnauthorized):
        await one_c.kpi()
    await one_c.aclose()


@respx.mock
async def test_forbidden_is_unauthorized_error(one_c: OneCClient) -> None:
    respx.get(f"{BASE_URL}/kpi").mock(
        return_value=httpx.Response(403, json={"error": {"code": "forbidden"}})
    )
    with pytest.raises(OneCUnauthorized, match="роль"):
        await one_c.kpi()
    await one_c.aclose()


@respx.mock
async def test_bad_request_message_from_body(one_c: OneCClient) -> None:
    respx.get(f"{BASE_URL}/kpi").mock(
        return_value=httpx.Response(
            400,
            json={
                "error": {
                    "code": "bad_request",
                    "message": "Параметр period имеет недопустимое значение: 'decade'",
                }
            },
        )
    )
    with pytest.raises(OneCError, match="period"):
        await one_c.kpi()
    await one_c.aclose()


@respx.mock
async def test_non_json_answer_is_unavailable(one_c: OneCClient) -> None:
    respx.get(f"{BASE_URL}/kpi").mock(
        return_value=httpx.Response(200, text="<html>1С:Предприятие</html>")
    )
    with pytest.raises(OneCUnavailable, match="не JSON"):
        await one_c.kpi()
    await one_c.aclose()


@respx.mock
async def test_json_array_answer_is_unavailable(one_c: OneCClient) -> None:
    respx.get(f"{BASE_URL}/kpi").mock(return_value=httpx.Response(200, json=[1, 2, 3]))
    with pytest.raises(OneCUnavailable, match="не того вида"):
        await one_c.kpi()
    await one_c.aclose()


async def test_client_works_with_injected_transport() -> None:
    """Тесты могут подменить транспорт: реальные запросы не уходят."""

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/health")
        return httpx.Response(200, json={"status": "ok"})

    async with httpx.AsyncClient(
        base_url=BASE_URL, transport=httpx.MockTransport(handler)
    ) as http_client:
        client = OneCClient(make_settings(), client=http_client)
        assert (await client.health())["status"] == "ok"
