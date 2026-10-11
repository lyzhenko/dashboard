"""Сборка FastAPI-приложения."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api import api_router, setup_error_handlers
from app.core.config import Settings, get_settings
from app.core.logging import get_logger, setup_logging
from app.db.engine import dispose_engine
from app.integrations.one_c import OneCClient

logger = get_logger(__name__)

TAGS_METADATA: list[dict[str, object]] = [
    {
        "name": "Служебное",
        "description": "Проверка живости сервиса, базы данных и доступности 1С.",
    },
    {
        "name": "Авторизация",
        "description": (
            "Вход в дашборд. Access-токен (JWT, HS256) живёт в памяти фронтенда, "
            "refresh-токен — в httpOnly cookie."
        ),
    },
    {
        "name": "Дашборд",
        "description": (
            "Показатели руководителя. Данные читаются из HTTP-сервиса расширения 1С "
            "и кэшируются в базе; при недоступности 1С отдаётся устаревший снимок."
        ),
    },
]

DESCRIPTION = """
Бэкенд дашборда руководителя предприятия (УНФ 3.0).

* Источник данных — HTTP-сервис расширения 1С (`D_DashboardApi`, только чтение).
* Все показатели кэшируются в базе (`kpi_snapshots`) на `KPI_CACHE_TTL_SECONDS`.
* Ошибки 1С превращаются в `503 kpi_unavailable`, кроме случая, когда есть
  устаревший снимок: тогда данные отдаются с `stale: true`.
* Все `/dashboard/*` требуют заголовок `Authorization: Bearer <accessToken>`.
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None]:
    """Старт и остановка приложения."""
    settings = get_settings()
    setup_logging(settings.log_level)
    app.state.one_c_client = OneCClient(settings)
    logger.info(
        "Бэкенд запущен: база %s, 1С %s",
        settings.database_url,
        settings.one_c_base_url,
    )
    try:
        yield
    finally:
        client: OneCClient | None = getattr(app.state, "one_c_client", None)
        if client is not None:
            await client.aclose()
        await dispose_engine()
        logger.info("Бэкенд остановлен")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Собрать приложение (используется и в тестах)."""
    active_settings = settings or get_settings()
    setup_logging(active_settings.log_level)

    app = FastAPI(
        title=active_settings.app_name,
        version=active_settings.app_version,
        description=DESCRIPTION,
        openapi_tags=TAGS_METADATA,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
        contact={"name": "Дашборд руководителя", "url": "https://example.local/dashboard"},
        license_info={"name": "Proprietary"},
    )

    setup_error_handlers(app)
    app.include_router(api_router, prefix=active_settings.api_prefix)
    return app


app = create_app()


__all__ = ["TAGS_METADATA", "app", "create_app", "lifespan"]
