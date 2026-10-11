"""Клиент HTTP-сервиса расширения 1С (``D_DashboardApi``).

Контракт — ``docs/API-КОНТРАКТ.md``, раздел 1. Только чтение, только GET,
базовая аутентификация 1С. Любая проблема с 1С превращается в понятное
исключение (:class:`OneCUnavailable` / :class:`OneCUnauthorized`), а не в 500.
"""

from __future__ import annotations

import time
from types import TracebackType
from typing import Any, Final

import httpx

from app.core.config import Settings
from app.core.config import settings as default_settings
from app.core.logging import get_logger

logger = get_logger(__name__)

NETWORK_ERRORS: Final = (httpx.TimeoutException, httpx.NetworkError, httpx.ProtocolError)

_JSON_OBJECT_EXAMPLE: Final = '{"error": {"code": "...", "message": "..."}}'


class OneCError(Exception):
    """Базовая ошибка обмена с 1С."""


class OneCUnavailable(OneCError):  # noqa: N818 - имя читается как «1С недоступна»
    """1С не ответила, ответила ошибкой сервера или недоступна по сети."""


class OneCUnauthorized(OneCError):  # noqa: N818 - имя читается как «1С отклонила доступ»
    """1С отклонила учётные данные (401)."""


def _message_from_body(response: httpx.Response) -> str | None:
    """Текст ошибки из тела ``{"error": {"message": ...}}``, если оно такое."""
    try:
        body = response.json()
    except ValueError:
        return None

    if isinstance(body, dict):
        error = body.get("error")
        if isinstance(error, dict):
            message = error.get("message")
            if isinstance(message, str) and message:
                return message
        if isinstance(error, str) and error:
            return error
    return None


def _short_body(response: httpx.Response, limit: int = 300) -> str:
    text = response.text.strip().replace("\n", " ")
    return text[:limit] if text else "<пустой ответ>"


class OneCClient:
    """Асинхронный клиент HTTP-сервиса расширения 1С."""

    def __init__(
        self,
        settings_obj: Settings | None = None,
        *,
        transport: httpx.AsyncBaseTransport | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._settings = settings_obj or default_settings
        self._base_url = self._settings.one_c_base_url.rstrip("/")
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            base_url=self._base_url,
            auth=httpx.BasicAuth(self._settings.one_c_user, self._settings.one_c_password),
            timeout=httpx.Timeout(self._settings.one_c_timeout_seconds),
            headers={"Accept": "application/json"},
            transport=transport,
            follow_redirects=True,
            # Прокси из системных настроек Windows обошёл бы локальную публикацию 1С
            # и вернул 503 от себя. См. комментарий к one_c_trust_env в config.py.
            trust_env=self._settings.one_c_trust_env,
        )

    @property
    def base_url(self) -> str:
        return self._base_url

    async def __aenter__(self) -> OneCClient:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        await self.aclose()

    async def aclose(self) -> None:
        """Закрыть соединения, если клиент создавал их сам."""
        if self._owns_client:
            await self._client.aclose()

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        """GET с логированием длительности и разбором ошибок 1С."""
        clean_params = {key: value for key, value in (params or {}).items() if value is not None}
        url = f"{self._base_url}{path}"
        started = time.perf_counter()

        try:
            response = await self._client.get(path, params=clean_params)
        except NETWORK_ERRORS as exc:
            elapsed = time.perf_counter() - started
            logger.warning(
                "1С недоступна: GET %s params=%s за %.3f с (%s: %s)",
                url,
                clean_params,
                elapsed,
                type(exc).__name__,
                exc,
            )
            msg = f"Не удалось обратиться к 1С ({type(exc).__name__}): {exc}"
            raise OneCUnavailable(msg) from exc

        elapsed = time.perf_counter() - started
        logger.info(
            "1С: GET %s params=%s → %s за %.3f с",
            url,
            clean_params,
            response.status_code,
            elapsed,
        )

        if response.status_code == httpx.codes.UNAUTHORIZED:
            msg = "1С отклонила учётные данные (проверьте ONE_C_USER и ONE_C_PASSWORD)"
            raise OneCUnauthorized(msg)
        if response.status_code == httpx.codes.FORBIDDEN:
            msg = "У пользователя 1С нет прав на метод дашборда (роль D_ОсновнаяРоль)"
            raise OneCUnauthorized(msg)
        if response.status_code >= httpx.codes.INTERNAL_SERVER_ERROR:
            detail = _message_from_body(response) or _short_body(response)
            msg = f"1С ответила ошибкой {response.status_code}: {detail}"
            raise OneCUnavailable(msg)

        if response.status_code >= httpx.codes.BAD_REQUEST:
            detail = _message_from_body(response) or _short_body(response)
            logger.warning("1С вернула %s: %s", response.status_code, detail)
            msg = f"1С отклонила запрос ({response.status_code}): {detail}"
            raise OneCError(msg)

        try:
            payload = response.json()
        except ValueError as exc:
            msg = f"1С вернула не JSON (ожидался объект вида {_JSON_OBJECT_EXAMPLE})"
            raise OneCUnavailable(msg) from exc

        if not isinstance(payload, dict):
            msg = "1С вернула JSON не того вида: ожидался объект"
            raise OneCUnavailable(msg)
        return payload

    # --- Методы контракта (раздел 1) ---

    async def health(self) -> dict[str, Any]:
        """``GET /health`` — проверка доступности расширения."""
        return await self._get("/health")

    async def organizations(self) -> list[dict[str, Any]]:
        """``GET /organizations`` — список организаций."""
        payload = await self._get("/organizations")
        items = payload.get("items")
        if not isinstance(items, list):
            return []
        return [item for item in items if isinstance(item, dict)]

    async def kpi(
        self,
        date: str | None = None,
        period: str | None = None,
        organization: str | None = None,
    ) -> dict[str, Any]:
        """``GET /kpi`` — сводка для главного экрана."""
        return await self._get(
            "/kpi", {"date": date, "period": period, "organization": organization}
        )

    async def dynamics(
        self,
        months: int | None = None,
        date: str | None = None,
        organization: str | None = None,
    ) -> dict[str, Any]:
        """``GET /dynamics`` — выручка и прибыль по месяцам."""
        return await self._get(
            "/dynamics", {"months": months, "date": date, "organization": organization}
        )

    async def debtors(
        self,
        kind: str | None = None,
        limit: int | None = None,
        date: str | None = None,
        organization: str | None = None,
    ) -> dict[str, Any]:
        """``GET /debtors`` — детализация задолженности по контрагентам."""
        return await self._get(
            "/debtors",
            {"kind": kind, "limit": limit, "date": date, "organization": organization},
        )


def create_one_c_client(settings_obj: Settings | None = None) -> OneCClient:
    """Создать клиент 1С по настройкам."""
    return OneCClient(settings_obj)


__all__ = [
    "OneCClient",
    "OneCError",
    "OneCUnauthorized",
    "OneCUnavailable",
    "create_one_c_client",
]
