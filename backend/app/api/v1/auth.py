"""Авторизация: вход, обновление токена, выход, сведения о пользователе."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Response, status

from app.api.deps import CurrentUser, SessionDep, SettingsDep
from app.core.config import Settings
from app.core.errors import UnauthorizedError
from app.core.security import TokenError, create_access_token, create_refresh_token
from app.models.user import User
from app.schemas.auth import (
    LoginRequest,
    LoginResponse,
    LogoutResponse,
    RefreshResponse,
    UserInfo,
)
from app.schemas.common import ErrorResponse
from app.services.auth_service import (
    UserInactiveError,
    UserNotFoundError,
    authenticate,
    user_from_refresh_token,
)

router = APIRouter(prefix="/auth", tags=["Авторизация"])

#: Имя cookie с refresh-токеном. Задано литералом (а не `settings.refresh_cookie_name`),
#: потому что аннотация параметра в `refresh` вычисляется один раз при импорте модуля.
REFRESH_COOKIE_NAME = "dashboard_refresh"

ERROR_RESPONSES: dict[int | str, dict[str, object]] = {
    status.HTTP_401_UNAUTHORIZED: {
        "model": ErrorResponse,
        "description": "Неверный логин или пароль, либо истёкший токен",
    }
}


def _user_info(user: User) -> UserInfo:
    """Представление пользователя для API."""
    return UserInfo(
        id=user.id,
        username=user.username,
        fullName=user.full_name,
        roles=user.role_list(),
    )


def _set_refresh_cookie(response: Response, token: str, settings: Settings) -> None:
    """Положить refresh-токен в ``httpOnly`` cookie."""
    response.set_cookie(
        key=settings.refresh_cookie_name,
        value=token,
        max_age=settings.refresh_token_ttl_seconds,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )


def _clear_refresh_cookie(response: Response, settings: Settings) -> None:
    """Удалить cookie с refresh-токеном."""
    response.delete_cookie(
        key=settings.refresh_cookie_name,
        httponly=True,
        secure=settings.cookie_secure,
        samesite=settings.cookie_samesite,
        domain=settings.cookie_domain,
        path="/",
    )


@router.post(
    "/login",
    response_model=LoginResponse,
    summary="Вход в дашборд",
    description=(
        "Проверяет логин и пароль. Access-токен возвращается в теле ответа "
        "(фронтенд хранит его в памяти), refresh-токен — в httpOnly cookie."
    ),
    responses=ERROR_RESPONSES,
)
async def login(
    payload: LoginRequest,
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
) -> LoginResponse:
    """Войти в систему."""
    try:
        user = await authenticate(session, payload.username, payload.password)
    except (UserNotFoundError, UserInactiveError) as exc:
        raise UnauthorizedError(str(exc)) from exc

    access_token = create_access_token(user.subject)
    _set_refresh_cookie(response, create_refresh_token(user.subject), settings)
    return LoginResponse(
        accessToken=access_token,
        expiresIn=settings.access_token_ttl_seconds,
        user=_user_info(user),
    )


@router.post(
    "/refresh",
    response_model=RefreshResponse,
    summary="Обновить access-токен",
    description=(
        "Читает refresh-токен из httpOnly cookie и выдаёт новый access-токен. "
        "Тело запроса не требуется."
    ),
    responses=ERROR_RESPONSES,
)
async def refresh(
    response: Response,
    session: SessionDep,
    settings: SettingsDep,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE_NAME)] = None,
) -> RefreshResponse:
    """Обновить access-токен по refresh-cookie.

    ``alias`` обязателен: FastAPI ищет cookie по имени параметра, а имя cookie —
    это ``REFRESH_COOKIE_NAME`` (настройка ``REFRESH_COOKIE_NAME``).
    """
    cookie_name = settings.refresh_cookie_name
    token = refresh_cookie
    if token is None:
        raise UnauthorizedError(f"Cookie {cookie_name} отсутствует")
    try:
        user = await user_from_refresh_token(session, token)
    except TokenError as exc:
        _clear_refresh_cookie(response, settings)
        raise UnauthorizedError(str(exc)) from exc

    access_token = create_access_token(user.subject)
    # Продлеваем refresh-токен: пользователь активно работает — пусть сессия живёт.
    _set_refresh_cookie(response, create_refresh_token(user.subject), settings)
    return RefreshResponse(
        accessToken=access_token,
        expiresIn=settings.access_token_ttl_seconds,
    )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Выход из дашборда",
    description="Удаляет cookie с refresh-токеном. Access-токен фронтенд забывает сам.",
)
async def logout(response: Response, settings: SettingsDep) -> LogoutResponse:
    """Выйти из системы."""
    _clear_refresh_cookie(response, settings)
    return LogoutResponse(message="Вы вышли из системы")


@router.get(
    "/me",
    response_model=UserInfo,
    summary="Текущий пользователь",
    description="Отдаёт сведения о пользователе по access-токену.",
    responses={
        status.HTTP_401_UNAUTHORIZED: {
            "model": ErrorResponse,
            "description": "Токен отсутствует или недействителен",
        }
    },
)
async def me(user: CurrentUser) -> UserInfo:
    """Сведения о текущем пользователе."""
    return _user_info(user)


__all__ = ["REFRESH_COOKIE_NAME", "router"]
