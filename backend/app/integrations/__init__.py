"""Клиенты внешних систем."""

from app.integrations.one_c import (
    OneCClient,
    OneCError,
    OneCUnauthorized,
    OneCUnavailable,
    create_one_c_client,
)

__all__ = [
    "OneCClient",
    "OneCError",
    "OneCUnauthorized",
    "OneCUnavailable",
    "create_one_c_client",
]
