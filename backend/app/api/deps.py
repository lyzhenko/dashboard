"""FastAPI-зависимости: текущий пользователь, клиент 1С, настройки."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, get_settings
from app.core.errors import ForbiddenError, UnauthorizedError
from app.core.security import TokenError
from app.db.session import get_session
from app.integrations.one_c import OneCClient
from app.models.user import User
from app.services.auth_service import user_from_access_token

#: ``auto_error=False`` — иначе FastAPI ответит своей схемой ошибки, а не контрактной.
bearer_scheme = HTTPBearer(auto_error=False, scheme_name="Bearer", description="JWT access-токен")

SessionDep = Annotated[AsyncSession, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    session: SessionDep,
) -> User:
    """Пользователь по access-токену из заголовка ``Authorization: Bearer``."""
    if credentials is None or not credentials.credentials:
        raise UnauthorizedError("Требуется авторизация")
    try:
        return await user_from_access_token(session, credentials.credentials)
    except TokenError as exc:
        raise UnauthorizedError(str(exc)) from exc


CurrentUser = Annotated[User, Depends(get_current_user)]


def get_one_c_client(request: Request) -> OneCClient:
    """Общий клиент 1С из состояния приложения (создаётся в lifespan)."""
    client: OneCClient | None = getattr(request.app.state, "one_c_client", None)
    if client is None:
        # Приложение собрано без lifespan (тесты, отдельные сценарии) — создаём клиент на месте.
        client = OneCClient()
        request.app.state.one_c_client = client
    return client


OneCClientDep = Annotated[OneCClient, Depends(get_one_c_client)]


def require_roles(*roles: str):
    """Зависимость-проверка роли (на будущее: разделение прав)."""

    async def _checker(user: CurrentUser) -> User:
        if roles and not any(user.has_role(role) for role in roles):
            raise ForbiddenError(f"Требуется роль: {', '.join(roles)}")
        return user

    return _checker


__all__ = [
    "CurrentUser",
    "OneCClientDep",
    "SessionDep",
    "SettingsDep",
    "bearer_scheme",
    "get_current_user",
    "get_one_c_client",
    "require_roles",
]
