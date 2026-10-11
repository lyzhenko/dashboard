"""Служебные проверки и схема OpenAPI."""

from __future__ import annotations

import json

from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import FakeOneCClient

from app.integrations.one_c import OneCUnavailable
from app.main import create_app
from app.openapi import PROJECT_ROOT


async def test_health_reports_ok_and_one_c_status(
    client: AsyncClient, fake_one_c: FakeOneCClient
) -> None:
    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "oneC": "ok"}


async def test_health_does_not_fail_when_one_c_is_down(
    client: AsyncClient, fake_one_c: FakeOneCClient
) -> None:
    fake_one_c.fail_with = OneCUnavailable("нет соединения")

    response = await client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "database": "ok", "oneC": "unavailable"}


async def test_health_is_available_without_authorization(
    client: AsyncClient, demo_user: AsyncSession
) -> None:
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


def test_openapi_contains_all_contract_endpoints() -> None:
    schema = create_app().openapi()
    paths = schema["paths"]

    expected = {
        "/api/v1/health",
        "/api/v1/auth/login",
        "/api/v1/auth/refresh",
        "/api/v1/auth/logout",
        "/api/v1/auth/me",
        "/api/v1/dashboard/summary",
        "/api/v1/dashboard/dynamics",
        "/api/v1/dashboard/debtors",
        "/api/v1/dashboard/organizations",
        "/api/v1/dashboard/refresh",
    }
    assert expected <= set(paths), f"в схеме нет: {expected - set(paths)}"


def test_openapi_has_tags_descriptions_and_examples() -> None:
    schema = create_app().openapi()

    assert {tag["name"] for tag in schema["tags"]} == {"Служебное", "Авторизация", "Дашборд"}
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            assert operation.get("tags"), f"{method} {path} без тега"
            assert operation.get("summary"), f"{method} {path} без описания"

    login_schema = schema["components"]["schemas"]["LoginRequest"]
    assert login_schema["example"] == {"username": "rukovoditel", "password": "dashboard"}


def test_openapi_summary_schema_matches_contract() -> None:
    schema = create_app().openapi()
    summary = schema["components"]["schemas"]["SummaryResponse"]["properties"]

    for block in (
        "meta",
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
        "asOf",
        "generatedAt",
    ):
        assert block in summary, f"в SummaryResponse нет блока {block}"

    sales = schema["components"]["schemas"]["SalesBlock"]["properties"]
    assert "revenueNet" in sales
    assert "revenueWithVat" not in sales

    orders = schema["components"]["schemas"]["OrdersBlock"]["properties"]
    for field in (
        "portfolio",
        "count",
        "positions",
        "overdueCount",
        "overdueAmount",
        "dueThisWeek",
        "orderedAmount",
        "paidAmount",
    ):
        assert field in orders, f"в OrdersBlock нет поля {field}"

    buckets = schema["components"]["schemas"]["Bucket"]["properties"]
    assert set(buckets) == {"label", "amount"}, "в корзине долга только подпись и сумма"

    assert (
        schema["components"]["schemas"]["ReceivablesBlock"]["properties"].get("advancesToSuppliers")
        is None
    )


def test_openapi_output_path_points_to_project_root() -> None:
    """Проектная команда ``python -m app.openapi`` кладёт файл в корень репозитория."""
    assert (PROJECT_ROOT / "backend" / "pyproject.toml").is_file()
    assert (PROJECT_ROOT / "STACK-BRIEF.md").is_file()
    assert (PROJECT_ROOT / "docs" / "API-КОНТРАКТ.md").is_file()


def test_openapi_schema_is_json_serializable() -> None:
    schema = create_app().openapi()
    assert json.loads(json.dumps(schema, ensure_ascii=False))["info"]["title"]
