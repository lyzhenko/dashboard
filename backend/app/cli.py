"""Управление пользователями дашборда из командной строки.

Примеры (из каталога ``backend/``)::

    uv run python -m app.cli create-user --username ivanov --password secret \\
        --full-name "Иванов И. И." --role viewer
    uv run python -m app.cli list-users
    uv run python -m app.cli reset-password --username ivanov --password newsecret
    uv run python -m app.cli seed-demo

``seed-demo`` — только для разработки: создаёт пользователя ``rukovoditel``
с паролем ``dashboard`` и ролью ``viewer``.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from collections.abc import Awaitable, Callable, Sequence
from typing import TYPE_CHECKING

from app.core.logging import setup_logging
from app.db.engine import dispose_engine
from app.db.session import session_scope
from app.models.user import DEFAULT_ROLE, KNOWN_ROLES
from app.services import auth_service

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from app.models.user import User

DEMO_USERNAME = "rukovoditel"
DEMO_PASSWORD = "dashboard"  # noqa: S105 - пароль демо-пользователя, только для разработки
DEMO_FULL_NAME = "Иванов И. И."
DEMO_ROLE = "viewer"


#: Обработчик команды: сессия и разобранные аргументы → код возврата.
CommandHandler = Callable[["AsyncSession", argparse.Namespace], Awaitable[int]]


def _describe(user: User) -> str:
    roles = ", ".join(user.role_list()) or "—"
    state = "активен" if user.is_active else "отключён"
    return f"{user.id:>4}  {user.username:<20} {user.full_name or '—':<28} {roles:<20} {state}"


async def _with_session(handler: CommandHandler, args: argparse.Namespace) -> int:
    """Открыть сессию, выполнить обработчик, закрыть соединения."""
    session: AsyncSession = session_scope()
    try:
        return await handler(session, args)
    finally:
        await session.close()
        await dispose_engine()


async def _cmd_create_user(session: AsyncSession, args: argparse.Namespace) -> int:
    roles = list(args.role or [DEFAULT_ROLE])
    unknown = [role for role in roles if role not in KNOWN_ROLES]
    if unknown:
        print(
            f"Неизвестные роли: {', '.join(unknown)}. Допустимые: {', '.join(KNOWN_ROLES)}",
            file=sys.stderr,
        )
        return 2
    try:
        user = await auth_service.create_user(
            session,
            username=args.username,
            password=args.password,
            full_name=args.full_name or "",
            roles=roles,
        )
    except auth_service.UsernameTakenError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Пользователь создан: {_describe(user)}")
    return 0


async def _cmd_list_users(session: AsyncSession, args: argparse.Namespace) -> int:  # noqa: ARG001
    users = await auth_service.list_users(session)
    if not users:
        print("Пользователей нет.")
        return 0
    print(f"{'id':>4}  {'логин':<20} {'ФИО':<28} {'роли':<20} состояние")
    for user in users:
        print(_describe(user))
    return 0


async def _cmd_reset_password(session: AsyncSession, args: argparse.Namespace) -> int:
    try:
        user = await auth_service.reset_password(session, args.username, args.password)
    except auth_service.UserNotFoundError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Пароль изменён: {_describe(user)}")
    return 0


async def _cmd_seed_demo(session: AsyncSession, args: argparse.Namespace) -> int:  # noqa: ARG001
    existing = await auth_service.get_user_by_username(session, DEMO_USERNAME)
    user = await auth_service.seed_demo_user(session)
    if existing is not None:
        print(f"Демо-пользователь уже есть: {_describe(user)}")
    else:
        print(f"Демо-пользователь создан: {_describe(user)}")
    print(f"Логин: {DEMO_USERNAME}, пароль: {DEMO_PASSWORD}, роль: {DEMO_ROLE}")
    print("Это данные для разработки — на стенде пользователя создавать вручную.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Собрать парсер аргументов командной строки."""
    parser = argparse.ArgumentParser(
        prog="app.cli",
        description="Управление пользователями дашборда руководителя",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    create = subparsers.add_parser("create-user", help="создать пользователя")
    create.add_argument("--username", required=True, help="логин")
    create.add_argument("--password", required=True, help="пароль")
    create.add_argument("--full-name", default="", help="ФИО для отображения")
    create.add_argument(
        "--role",
        action="append",
        choices=list(KNOWN_ROLES),
        help=f"роль (можно указать несколько раз), по умолчанию {DEFAULT_ROLE}",
    )
    create.set_defaults(handler=_cmd_create_user)

    listing = subparsers.add_parser("list-users", help="список пользователей")
    listing.set_defaults(handler=_cmd_list_users)

    reset = subparsers.add_parser("reset-password", help="сменить пароль пользователя")
    reset.add_argument("--username", required=True, help="логин")
    reset.add_argument("--password", required=True, help="новый пароль")
    reset.set_defaults(handler=_cmd_reset_password)

    seed = subparsers.add_parser("seed-demo", help="создать демо-пользователя (разработка)")
    seed.set_defaults(handler=_cmd_seed_demo)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    """Точка входа ``python -m app.cli``."""
    setup_logging("WARNING")
    parser = build_parser()
    args = parser.parse_args(argv)
    return asyncio.run(_with_session(args.handler, args))


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["build_parser", "main"]
