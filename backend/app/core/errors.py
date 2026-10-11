"""Ошибки приложения и их отображение в ответы API.

Формат ошибки описан в ``docs/API-КОНТРАКТ.md`` (раздел 2):

    {"detail": {"code": "kpi_unavailable", "message": "..."}}
"""

from __future__ import annotations

from typing import Final

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

ERROR_UNAUTHORIZED: Final = "unauthorized"
ERROR_FORBIDDEN: Final = "forbidden"
ERROR_NOT_FOUND: Final = "not_found"
ERROR_VALIDATION: Final = "validation_error"
ERROR_KPI_UNAVAILABLE: Final = "kpi_unavailable"
ERROR_INTERNAL: Final = "internal_error"

_STATUS_TO_CODE: Final[dict[int, str]] = {
    status.HTTP_400_BAD_REQUEST: ERROR_VALIDATION,
    status.HTTP_401_UNAUTHORIZED: ERROR_UNAUTHORIZED,
    status.HTTP_403_FORBIDDEN: ERROR_FORBIDDEN,
    status.HTTP_404_NOT_FOUND: ERROR_NOT_FOUND,
    status.HTTP_422_UNPROCESSABLE_CONTENT: ERROR_VALIDATION,
    status.HTTP_503_SERVICE_UNAVAILABLE: ERROR_KPI_UNAVAILABLE,
}


class AppError(Exception):
    """Базовая ошибка приложения с кодом контракта."""

    status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR
    code: str = ERROR_INTERNAL

    def __init__(self, message: str, *, code: str | None = None, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        if code is not None:
            self.code = code
        if status_code is not None:
            self.status_code = status_code


class UnauthorizedError(AppError):
    """Нет или истёк токен."""

    status_code = status.HTTP_401_UNAUTHORIZED
    code = ERROR_UNAUTHORIZED

    def __init__(self, message: str = "Требуется авторизация"):
        super().__init__(message)


class ForbiddenError(AppError):
    """Аутентифицирован, но прав не хватает."""

    status_code = status.HTTP_403_FORBIDDEN
    code = ERROR_FORBIDDEN

    def __init__(self, message: str = "Недостаточно прав"):
        super().__init__(message)


class NotFoundError(AppError):
    """Объект не найден."""

    status_code = status.HTTP_404_NOT_FOUND
    code = ERROR_NOT_FOUND

    def __init__(self, message: str = "Не найдено"):
        super().__init__(message)


class InvalidParamsError(AppError):
    """Параметры запроса неверны (422 ``validation_error``)."""

    status_code = status.HTTP_422_UNPROCESSABLE_CONTENT
    code = ERROR_VALIDATION

    def __init__(self, message: str = "Некорректные параметры запроса"):
        super().__init__(message)


class KpiUnavailableError(AppError):
    """Данные 1С недоступны и закэшированных данных нет."""

    status_code = status.HTTP_503_SERVICE_UNAVAILABLE
    code = ERROR_KPI_UNAVAILABLE

    def __init__(self, message: str = "Данные 1С недоступны"):
        super().__init__(message)


def error_body(code: str, message: str) -> dict[str, dict[str, str]]:
    """Тело ошибки по контракту."""
    return {"detail": {"code": code, "message": message}}


def register_exception_handlers(app: FastAPI) -> None:
    """Зарегистрировать обработчики ошибок, приводящие ответы к контракту."""

    @app.exception_handler(AppError)
    async def _app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message),
        )

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _STATUS_TO_CODE.get(exc.status_code, ERROR_INTERNAL)
        message = exc.detail if isinstance(exc.detail, str) else "Ошибка запроса"
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code, message),
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(RequestValidationError)
    async def _validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = "; ".join(
            f"{'.'.join(str(part) for part in error.get('loc', ()) if part != 'body')}: "
            f"{error.get('msg', 'некорректное значение')}"
            for error in exc.errors()
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=error_body(ERROR_VALIDATION, details or "Некорректные параметры запроса"),
        )


__all__ = [
    "ERROR_FORBIDDEN",
    "ERROR_INTERNAL",
    "ERROR_KPI_UNAVAILABLE",
    "ERROR_NOT_FOUND",
    "ERROR_UNAUTHORIZED",
    "ERROR_VALIDATION",
    "AppError",
    "ForbiddenError",
    "InvalidParamsError",
    "KpiUnavailableError",
    "NotFoundError",
    "UnauthorizedError",
    "error_body",
    "register_exception_handlers",
]
