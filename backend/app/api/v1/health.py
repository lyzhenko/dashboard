"""Служебные методы: проверка живости сервиса."""

from __future__ import annotations

from fastapi import APIRouter, status

from app.api.deps import OneCClientDep, SessionDep
from app.core.logging import get_logger
from app.db.engine import check_database
from app.schemas.common import HealthResponse, MessageResponse
from app.services import kpi_service

logger = get_logger(__name__)

router = APIRouter(tags=["Служебное"])


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Проверка живости",
    description=(
        "Отвечает `ok`, если работает сам сервис. Поле `database` — доступность базы, "
        "поле `oneC` — доступность HTTP-сервиса расширения 1С (`ok` / `unavailable`). "
        "Недоступность 1С не делает ответ ошибочным: дашборд может работать на кэше."
    ),
    responses={
        status.HTTP_503_SERVICE_UNAVAILABLE: {
            "model": MessageResponse,
            "description": "База данных недоступна",
        }
    },
)
async def health(session: SessionDep, client: OneCClientDep) -> HealthResponse:
    """Состояние сервиса, базы и 1С."""
    try:
        # session.bind — движок приложения (в тестах — соединение тестовой базы).
        await check_database(session.bind)
        database = "ok"
    except Exception:
        logger.exception("Проверка базы данных не удалась")
        database = "unavailable"

    one_c = await kpi_service.one_c_health(client)
    return HealthResponse(status="ok", database=database, oneC=one_c)


__all__ = ["router"]
