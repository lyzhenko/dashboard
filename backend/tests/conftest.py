"""Общие фикстуры тестов.

База поднимается настоящими миграциями (как на стенде), сеть не используется
вовсе: клиент 1С подменяется фейком, а HTTP-тесты клиента 1С работают через
``httpx.MockTransport`` / ``respx``.
"""

from __future__ import annotations

import os
import sys
from collections.abc import AsyncIterator, Iterator
from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pytest
import pytest_asyncio
from alembic import command
from alembic.config import Config
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import create_engine, text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

#: Тестовый секрет: не короче 32 байт, иначе PyJWT предупреждает о слабом ключе,
#: а настройки приложения отказываются стартовать.
JWT_TEST_SECRET = "test-secret-0123456789-0123456789-0123456789"

# Секрет задаём в окружении ДО импорта приложения: модуль app.core.config создаёт
# объект настроек при импорте, и тесты не должны зависеть от backend/.env разработчика.
_previous_jwt_secret = os.environ.get("JWT_SECRET")
os.environ["JWT_SECRET"] = JWT_TEST_SECRET

from app.api.deps import get_one_c_client  # noqa: E402
from app.core.config import refresh_settings  # noqa: E402
from app.db.engine import set_engine  # noqa: E402
from app.db.session import reset_session_factory  # noqa: E402
from app.integrations.one_c import OneCError  # noqa: E402
from app.main import app as application  # noqa: E402
from app.models import KpiSnapshot, Organization, User  # noqa: E402,F401

TEST_DB_DIR = BACKEND_DIR / "var" / "pytest"
TEST_DB_PATH = TEST_DB_DIR / "test.db"
TEST_DB_URL = f"sqlite+aiosqlite:///{TEST_DB_PATH.as_posix()}"

DEMO_USERNAME = "rukovoditel"
DEMO_PASSWORD = "dashboard"


def sample_summary(
    *,
    as_of: str = "2026-10-11",
    revenue: float = 500000.0,
    organization_name: str = "ООО «Ромашка»",
) -> dict[str, Any]:
    """Правдоподобный ответ 1С ``GET /kpi`` (по контракту, раздел 1.3)."""
    return {
        "generatedAt": f"{as_of}T07:40:00",
        "asOf": as_of,
        "period": {
            "kind": "month",
            "from": "2026-10-01",
            "to": as_of,
            "prevFrom": "2026-09-01",
            "prevTo": "2026-09-11",
        },
        "organization": {"id": "0a1b2c3d-1111-2222-3333-444455556666", "name": organization_name},
        "money": {"total": 1234567.89, "accounts": 1000000.0, "cash": 234567.89, "currency": "RUB"},
        "sales": {
            "revenue": revenue,
            "revenuePrev": 450000.0,
            "revenueDeltaPct": 11.11,
            "revenueNet": 416666.67,
            "grossProfit": 120000.0,
            "grossProfitPrev": 90000.0,
            "marginPct": 24.0,
            "documents": 42,
            "avgTicket": 11904.76,
        },
        "receivables": {
            "total": 800000.0,
            "overdue": 150000.0,
            "overduePct": 18.75,
            "buckets": [
                {"label": "0–7 дней", "amount": 650000.0},
                {"label": "8–14 дней", "amount": 0.0},
                {"label": "15–30 дней", "amount": 0.0},
                {"label": "31–60 дней", "amount": 140000.0},
                {"label": "Свыше 60 дней", "amount": 10000.0},
            ],
        },
        "payables": {
            "total": 500000.0,
            "overdue": 70000.0,
            "overduePct": 14.0,
            "buckets": [
                {"label": "0–7 дней", "amount": 490000.0},
                {"label": "8–14 дней", "amount": 0.0},
                {"label": "15–30 дней", "amount": 0.0},
                {"label": "31–60 дней", "amount": 0.0},
                {"label": "Свыше 60 дней", "amount": 10000.0},
            ],
        },
        "stock": {"total": 3000000.0, "skuCount": 1520, "negativeCount": 0},
        "orders": {
            "portfolio": 900000.0,
            "count": 37,
            "positions": 128.5,
            "overdueCount": 4,
            "overdueAmount": 120000.0,
            "dueThisWeek": 250000.0,
            "orderedAmount": 900000.0,
            "paidAmount": 600000.0,
        },
        "topDebtors": [
            {"name": "ООО «Василёк»", "amount": 300000.0, "overdue": 100000.0, "maxOverdueDays": 45}
        ],
        "topSuppliers": [
            {"name": "ООО «Поставщик»", "amount": 200000.0, "overdue": 0.0, "maxOverdueDays": 0}
        ],
    }


def empty_summary() -> dict[str, Any]:
    """Ответ 1С по пустой базе: только ``asOf`` и период (контракт, правило 3).

    В ответах расширения ``null`` нет — отсутствие данных это нули и пустые массивы.
    """
    return {
        "asOf": "2026-10-11",
        "period": {
            "kind": "month",
            "from": "2026-10-01",
            "to": "2026-10-11",
            "prevFrom": "2026-09-01",
            "prevTo": "2026-09-11",
        },
    }


class FakeOneCClient:
    """Подмена клиента 1С: тесты не выходят в сеть."""

    def __init__(self) -> None:
        self.summary: dict[str, Any] = sample_summary()
        self.dynamics_items: list[dict[str, Any]] = [
            {"month": "2026-09", "revenue": 420000.0, "grossProfit": 98000.0, "marginPct": 23.33},
            {"month": "2026-10", "revenue": 500000.0, "grossProfit": 120000.0, "marginPct": 24.0},
        ]
        self.debtors_payload: dict[str, Any] = {
            "kind": "receivable",
            "asOf": "2026-10-11",
            "total": 800000.0,
            "overdue": 150000.0,
            "items": [
                {
                    "name": "ООО «Василёк»",
                    "amount": 300000.0,
                    "overdue": 100000.0,
                    "maxOverdueDays": 45,
                    "buckets": [{"label": "0–7 дней", "amount": 200000.0}],
                }
            ],
        }
        self.organizations_items: list[dict[str, Any]] = [
            {
                "id": "0a1b2c3d-1111-2222-3333-444455556666",
                "name": "ООО «Ромашка»",
                "inn": "7701234567",
                "isDefault": False,
            }
        ]
        self.fail_with: OneCError | None = None
        self.calls: list[tuple[str, dict[str, Any]]] = []

    def _check(self, method: str, params: dict[str, Any]) -> None:
        self.calls.append((method, params))
        if self.fail_with is not None:
            raise self.fail_with

    @property
    def call_count(self) -> int:
        return len(self.calls)

    async def health(self) -> dict[str, Any]:
        self._check("health", {})
        return {"status": "ok", "service": "D_DashboardApi", "version": "1.0.0"}

    async def organizations(self) -> list[dict[str, Any]]:
        self._check("organizations", {})
        return list(self.organizations_items)

    async def kpi(
        self,
        date: str | None = None,
        period: str | None = None,
        organization: str | None = None,
    ) -> dict[str, Any]:
        self._check("kpi", {"date": date, "period": period, "organization": organization})
        return dict(self.summary)

    async def dynamics(
        self,
        months: int | None = None,
        date: str | None = None,
        organization: str | None = None,
    ) -> dict[str, Any]:
        self._check("dynamics", {"months": months, "date": date, "organization": organization})
        return {"items": [dict(item) for item in self.dynamics_items]}

    async def debtors(
        self,
        kind: str | None = None,
        limit: int | None = None,
        date: str | None = None,
        organization: str | None = None,
    ) -> dict[str, Any]:
        self._check(
            "debtors",
            {"kind": kind, "limit": limit, "date": date, "organization": organization},
        )
        return dict(self.debtors_payload)


@pytest.fixture(scope="session", autouse=True)
def test_environment() -> Iterator[None]:
    """Тестовые настройки: свой JWT_SECRET, никаких данных проекта."""
    os.environ["JWT_SECRET"] = JWT_TEST_SECRET
    refresh_settings()
    try:
        yield
    finally:
        if _previous_jwt_secret is None:
            os.environ.pop("JWT_SECRET", None)
        else:
            os.environ["JWT_SECRET"] = _previous_jwt_secret
        refresh_settings()


@pytest.fixture(scope="session")
def project_root() -> Path:
    """Корень проекта (там лежит ``openapi.json``)."""
    return BACKEND_DIR.parent


@pytest.fixture(scope="session")
def test_database() -> Iterator[str]:
    """Файл тестовой базы, поднятый настоящими миграциями (один раз на сессию)."""
    TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()

    config = Config(str(BACKEND_DIR / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_DIR / "migrations"))
    config.set_main_option("sqlalchemy.url", TEST_DB_URL)

    command.upgrade(config, "head")

    assert TEST_DB_PATH.exists(), "миграции не создали файл тестовой базы"
    yield TEST_DB_URL


@pytest.fixture(autouse=True)
def clean_database(test_database: str) -> Iterator[None]:
    """Очистить таблицы перед каждым тестом (схема остаётся от миграций)."""
    sync_engine = create_engine(test_database.replace("+aiosqlite", ""))
    with sync_engine.begin() as connection:
        names = [
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type = 'table'")
            )
            if row[0] != "sqlite_sequence"
        ]
        for name in names:
            # Пустая таблица удаляется без записи в журнал — это быстро.
            connection.execute(text(f'DELETE FROM "{name}"'))
        if "sqlite_sequence" in {
            row[0] for row in connection.execute(text("SELECT name FROM sqlite_master"))
        }:
            connection.execute(text("DELETE FROM sqlite_sequence"))
    sync_engine.dispose()
    yield


@pytest_asyncio.fixture
async def session(test_database: str) -> AsyncIterator[AsyncSession]:
    """Сессия к тестовой базе (для сервисных тестов)."""
    engine = create_async_engine(test_database, future=True)
    factory = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as active_session:
        yield active_session
    await engine.dispose()


@pytest.fixture
def fake_one_c() -> FakeOneCClient:
    """Фейковый клиент 1С."""
    return FakeOneCClient()


@pytest_asyncio.fixture
async def api_app(test_database: str, fake_one_c: FakeOneCClient) -> AsyncIterator[FastAPI]:
    """Приложение с тестовой базой и подменённым клиентом 1С."""
    engine = create_async_engine(test_database, future=True)
    set_engine(engine)
    reset_session_factory()

    application.dependency_overrides[get_one_c_client] = lambda: fake_one_c
    try:
        yield application
    finally:
        application.dependency_overrides.clear()
        await engine.dispose()
        set_engine(None)
        reset_session_factory()


@pytest_asyncio.fixture
async def client(api_app: FastAPI) -> AsyncIterator[AsyncClient]:
    """HTTP-клиент к приложению (без реального сервера и без сети)."""
    transport = ASGITransport(app=api_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as http_client:
        yield http_client


@pytest_asyncio.fixture
async def demo_user(session: AsyncSession) -> AsyncSession:
    """Пользователь ``rukovoditel`` / ``dashboard`` для тестов авторизации."""
    from app.services import auth_service

    await auth_service.create_user(
        session,
        username=DEMO_USERNAME,
        password=DEMO_PASSWORD,
        full_name="Иванов И. И.",
        roles=["viewer"],
    )
    return session


@pytest_asyncio.fixture
async def auth_headers(client: AsyncClient, demo_user: AsyncSession) -> dict[str, str]:
    """Заголовок ``Authorization`` с рабочим access-токеном."""
    response = await client.post(
        "/api/v1/auth/login",
        json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD},
    )
    assert response.status_code == 200, response.text
    return {"Authorization": f"Bearer {response.json()['accessToken']}"}


@pytest.fixture
def today() -> str:
    """Текущая дата в формате контракта."""
    return date.today().isoformat()


@pytest.fixture
def yesterday() -> str:
    """Вчерашняя дата в формате контракта."""
    return (date.today() - timedelta(days=1)).isoformat()
