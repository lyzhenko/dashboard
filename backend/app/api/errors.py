"""Подключение обработчиков ошибок к приложению.

Сами обработчики живут в ``app/core/errors.py`` — здесь только точка входа,
чтобы сборка приложения не знала деталей.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from app.core.errors import (
    AppError,
    ForbiddenError,
    InvalidParamsError,
    KpiUnavailableError,
    NotFoundError,
    UnauthorizedError,
    error_body,
    register_exception_handlers,
)

if TYPE_CHECKING:
    from fastapi import FastAPI

__all__ = [
    "AppError",
    "ForbiddenError",
    "InvalidParamsError",
    "KpiUnavailableError",
    "NotFoundError",
    "UnauthorizedError",
    "error_body",
    "setup_error_handlers",
]


def setup_error_handlers(app: FastAPI) -> None:
    """Зарегистрировать обработчики ошибок в приложении."""
    register_exception_handlers(app)
