"""Логирование приложения.

Формат подчинён одной задаче: по строке лога должно быть видно, что произошло
с обменом данными с 1С — метод, длительность, результат.
"""

from __future__ import annotations

import logging
import sys
from typing import Final

LOG_FORMAT: Final = "%(asctime)s %(levelname)-8s %(name)s: %(message)s"
DATE_FORMAT: Final = "%Y-%m-%d %H:%M:%S"
ACCESS_LOGGER: Final = "app.access"

_configured = False


class _HealthcheckFilter(logging.Filter):
    """Убрать из access-лога шум опроса здоровья (его дергают очень часто)."""

    noisy_paths = ("/api/v1/health", "/health")

    def filter(self, record: logging.LogRecord) -> bool:
        message = record.getMessage()
        return not any(path in message for path in self.noisy_paths)


def setup_logging(level: str = "INFO") -> None:
    """Настроить корневой логгер один раз на процесс."""
    global _configured
    root = logging.getLogger()
    numeric_level = logging.getLevelNamesMapping().get(level.upper(), logging.INFO)
    root.setLevel(numeric_level)

    if not _configured:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
        root.addHandler(handler)

        access_logger = logging.getLogger("uvicorn.access")
        access_logger.addFilter(_HealthcheckFilter())

        for noisy in ("httpx", "httpcore", "asyncio"):
            logging.getLogger(noisy).setLevel(logging.WARNING)
        _configured = True

    for handler in root.handlers:
        handler.setLevel(numeric_level)


def get_logger(name: str) -> logging.Logger:
    """Логгер приложения."""
    return logging.getLogger(name)


__all__ = ["ACCESS_LOGGER", "get_logger", "setup_logging"]
