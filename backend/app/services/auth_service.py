"""Пользователи дашборда: вход, проверка токенов, служебные операции."""

from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import func, select

from app.core.security import (
    TokenError,
    TokenType,
    decode_token,
    hash_password,
    verify_password,
)
from app.models.user import User, new_user

if TYPE_CHECKING:
    from collections.abc import Sequence

    from sqlalchemy.ext.asyncio import AsyncSession


class UserNotFoundError(Exception):
    """Пользователь не найден."""


class UserInactiveError(Exception):
    """Пользователь отключён."""


class UsernameTakenError(Exception):
    """Логин уже занят."""


async def get_user_by_id(session: AsyncSession, user_id: int) -> User | None:
    """Найти пользователя по идентификатору."""
    return await session.get(User, user_id)


async def get_user_by_username(session: AsyncSession, username: str) -> User | None:
    """Найти пользователя по логину (без учёта регистра)."""
    result = await session.execute(
        select(User).where(func.lower(User.username) == username.strip().lower())
    )
    return result.scalar_one_or_none()


async def list_users(session: AsyncSession) -> Sequence[User]:
    """Все пользователи по алфавиту."""
    result = await session.execute(select(User).order_by(func.lower(User.username)))
    return list(result.scalars().all())


async def authenticate(session: AsyncSession, username: str, password: str) -> User:
    """Проверить логин и пароль. Бросает :class:`UserNotFoundError` / :class:`UserInactiveError`."""
    user = await get_user_by_username(session, username)
    if user is None or not verify_password(password, user.password_hash):
        raise UserNotFoundError("Неверный логин или пароль")
    if not user.is_active:
        raise UserInactiveError("Пользователь отключён")
    return user


async def _user_from_token(session: AsyncSession, token: str, token_type: TokenType) -> User:
    """Пользователь по токену указанного вида. Бросает :class:`TokenError`."""
    payload = decode_token(token, token_type)
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise TokenError("Некорректный субъект токена") from exc
    user = await get_user_by_id(session, user_id)
    if user is None:
        raise TokenError("Пользователь не найден")
    if not user.is_active:
        raise TokenError("Пользователь отключён")
    return user


async def user_from_access_token(session: AsyncSession, token: str) -> User:
    """Пользователь по access-токену. Бросает :class:`TokenError`."""
    return await _user_from_token(session, token, "access")


async def user_from_refresh_token(session: AsyncSession, token: str) -> User:
    """Пользователь по refresh-токену. Бросает :class:`TokenError`."""
    return await _user_from_token(session, token, "refresh")


async def create_user(
    session: AsyncSession,
    *,
    username: str,
    password: str,
    full_name: str = "",
    roles: Sequence[str] | None = None,
) -> User:
    """Создать пользователя. Бросает :class:`UsernameTakenError`."""
    clean_username = username.strip()
    if not clean_username:
        msg = "Логин не может быть пустым"
        raise ValueError(msg)
    if await get_user_by_username(session, clean_username) is not None:
        raise UsernameTakenError(f"Пользователь {clean_username!r} уже существует")

    user = new_user(
        username=clean_username,
        password_hash=hash_password(password),
        full_name=full_name.strip(),
        roles=list(roles) if roles else None,
    )
    session.add(user)
    await session.commit()
    await session.refresh(user)
    return user


async def reset_password(session: AsyncSession, username: str, password: str) -> User:
    """Сменить пароль пользователя."""
    user = await get_user_by_username(session, username)
    if user is None:
        raise UserNotFoundError(f"Пользователь {username!r} не найден")
    user.password_hash = hash_password(password)
    await session.commit()
    await session.refresh(user)
    return user


async def set_active(session: AsyncSession, username: str, *, is_active: bool) -> User:
    """Включить или отключить пользователя."""
    user = await get_user_by_username(session, username)
    if user is None:
        raise UserNotFoundError(f"Пользователь {username!r} не найден")
    user.is_active = is_active
    await session.commit()
    await session.refresh(user)
    return user


async def seed_demo_user(session: AsyncSession) -> User:
    """Демонстрационный пользователь ``rukovoditel`` / ``dashboard`` (только разработка)."""
    existing = await get_user_by_username(session, "rukovoditel")
    if existing is not None:
        return existing
    return await create_user(
        session,
        username="rukovoditel",
        password="dashboard",  # noqa: S106 - демо-пароль, только для разработки
        full_name="Иванов И. И.",
        roles=["viewer"],
    )


__all__ = [
    "UserInactiveError",
    "UserNotFoundError",
    "UsernameTakenError",
    "authenticate",
    "create_user",
    "get_user_by_id",
    "get_user_by_username",
    "list_users",
    "reset_password",
    "seed_demo_user",
    "set_active",
    "user_from_access_token",
    "user_from_refresh_token",
]
