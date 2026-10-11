"""Безопасность: пароли (argon2) и токены (JWT, HS256)."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any, Final, Literal

import jwt
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import settings

ACCESS_TOKEN_TYPE: Final = "access"  # noqa: S105 - это тип токена, а не пароль
REFRESH_TOKEN_TYPE: Final = "refresh"  # noqa: S105 - это тип токена, а не пароль
TokenType = Literal["access", "refresh"]

_password_hash = PasswordHash.recommended()


class TokenError(Exception):
    """Токен отсутствует, просрочен, повреждён или не того типа."""


def hash_password(password: str) -> str:
    """Хешировать пароль (argon2id)."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Проверить пароль по хешу. Повреждённый хеш — это просто неудачная проверка."""
    try:
        return _password_hash.verify(password, password_hash)
    except UnknownHashError, ValueError:
        return False


def _create_token(subject: str, token_type: TokenType, ttl_seconds: int) -> str:
    issued_at = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "type": token_type,
        "iat": int(issued_at.timestamp()),
        "exp": int((issued_at + timedelta(seconds=ttl_seconds)).timestamp()),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def create_access_token(subject: str) -> str:
    """Создать access-токен (живёт ``ACCESS_TOKEN_TTL_SECONDS``)."""
    return _create_token(subject, ACCESS_TOKEN_TYPE, settings.access_token_ttl_seconds)


def create_refresh_token(subject: str) -> str:
    """Создать refresh-токен (живёт ``REFRESH_TOKEN_TTL_SECONDS``)."""
    return _create_token(subject, REFRESH_TOKEN_TYPE, settings.refresh_token_ttl_seconds)


def decode_token(token: str, expected_type: TokenType) -> dict[str, Any]:
    """Разобрать и проверить токен. Бросает :class:`TokenError`."""
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
    except jwt.ExpiredSignatureError as exc:
        raise TokenError("Срок действия токена истёк") from exc
    except jwt.InvalidTokenError as exc:
        raise TokenError("Некорректный токен") from exc

    if payload.get("type") != expected_type:
        raise TokenError("Неверный тип токена")
    if not payload.get("sub"):
        raise TokenError("В токене нет субъекта")
    return payload


__all__ = [
    "ACCESS_TOKEN_TYPE",
    "REFRESH_TOKEN_TYPE",
    "TokenError",
    "TokenType",
    "create_access_token",
    "create_refresh_token",
    "decode_token",
    "hash_password",
    "verify_password",
]
