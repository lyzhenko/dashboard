"""Схемы авторизации (контракт, 2.1).

Access-токен уходит в теле ответа (фронтенд держит его в памяти),
refresh-токен — только в ``httpOnly`` cookie.
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.common import MessageResponse

__all__ = [
    "LoginRequest",
    "LoginResponse",
    "LogoutResponse",
    "RefreshResponse",
    "TokenResponse",
    "UserInfo",
]


class LoginRequest(BaseModel):
    """Тело ``POST /auth/login``."""

    model_config = ConfigDict(
        json_schema_extra={"example": {"username": "rukovoditel", "password": "dashboard"}}
    )

    username: str = Field(min_length=1, max_length=64, description="Логин дашборда")
    password: str = Field(min_length=1, max_length=256, description="Пароль")


class UserInfo(BaseModel):
    """Сведения о пользователе (``GET /auth/me``)."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "id": 1,
                "username": "rukovoditel",
                "fullName": "Иванов И. И.",
                "roles": ["viewer"],
            }
        }
    )

    id: int = Field(description="Идентификатор пользователя")
    username: str = Field(description="Логин")
    fullName: str = Field(description="ФИО для отображения")
    roles: list[str] = Field(default_factory=list, description="Роли пользователя")


class TokenResponse(BaseModel):
    """Пара токенов: access в теле, refresh — в cookie."""

    accessToken: str = Field(description="JWT access-токен (HS256)")
    expiresIn: int = Field(description="Время жизни access-токена, секунды")


class LoginResponse(TokenResponse):
    """Ответ ``POST /auth/login``."""

    user: UserInfo = Field(description="Пользователь, вошедший в систему")


class RefreshResponse(TokenResponse):
    """Ответ ``POST /auth/refresh``."""


class LogoutResponse(MessageResponse):
    """Ответ ``POST /auth/logout``."""
