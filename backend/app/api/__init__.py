"""HTTP-слой приложения."""

from app.api.errors import setup_error_handlers
from app.api.v1 import api_router

__all__ = ["api_router", "setup_error_handlers"]
