"""Пользователь дашборда."""

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import JSON, Boolean, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import PK_BIGINT, UtcDateTime, utcnow

if TYPE_CHECKING:
    from collections.abc import Sequence

DEFAULT_ROLE = "viewer"
KNOWN_ROLES = ("admin", "viewer")


class User(Base):
    """Учётная запись дашборда (не путать с пользователем 1С)."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(PK_BIGINT, primary_key=True, autoincrement=True)
    username: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    full_name: Mapped[str] = mapped_column(String(255), nullable=False, default="")
    roles: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(UtcDateTime, nullable=False, default=utcnow)

    @property
    def subject(self) -> str:
        """Субъект JWT — первичный ключ в виде строки."""
        return str(self.id)

    def has_role(self, role: str) -> bool:
        """Есть ли у пользователя роль."""
        return role in (self.roles or [])

    def role_list(self) -> list[str]:
        """Роли списком (JSON-колонка может вернуть ``None``)."""
        return list(self.roles or [])

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username!r} roles={self.roles!r}>"


def new_user(
    *,
    username: str,
    password_hash: str,
    full_name: str = "",
    roles: Sequence[str] | None = None,
    is_active: bool = True,
) -> User:
    """Собрать нового пользователя (id присвоит база)."""
    user = User()
    user.username = username
    user.password_hash = password_hash
    user.full_name = full_name
    user.roles = list(roles) if roles else [DEFAULT_ROLE]
    user.is_active = is_active
    user.created_at = utcnow()
    return user


__all__ = ["DEFAULT_ROLE", "KNOWN_ROLES", "User", "new_user"]
