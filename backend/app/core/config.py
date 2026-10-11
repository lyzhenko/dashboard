"""Настройки приложения.

Значения читаются из переменных окружения и файла ``.env`` (``backend/.env``).
Секреты в репозиторий не попадают: в git попадает только ``.env.example``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

MIN_JWT_SECRET_BYTES = 32


class Settings(BaseSettings):
    """Конфигурация бэкенда дашборда."""

    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
        hide_input_in_errors=True,
        case_sensitive=False,
    )

    # --- Приложение ---
    app_name: str = "Дашборд руководителя предприятия"
    app_version: str = "0.1.0"
    api_prefix: str = "/api/v1"
    debug: bool = False
    log_level: str = "INFO"

    # --- База данных ---
    database_url: str = "sqlite+aiosqlite:///./var/dashboard.db"
    db_echo: bool = False

    # --- Аутентификация ---
    # Значение по умолчанию годится только для локального запуска: на стенде
    # JWT_SECRET задаётся в .env. Длину проверяет валидатор ниже.
    jwt_secret: str = "dev-only-secret-change-me-0123456789abcdef"  # noqa: S105
    jwt_algorithm: str = "HS256"
    access_token_ttl_seconds: int = 900
    refresh_token_ttl_seconds: int = 1209600
    refresh_cookie_name: str = "dashboard_refresh"
    cookie_secure: bool = False
    cookie_samesite: Literal["lax", "strict", "none"] = "lax"
    cookie_domain: str | None = None

    # --- 1С: HTTP-сервис расширения ---
    one_c_base_url: str = "http://localhost:8090/unf/hs/dashboard"
    one_c_user: str = ""
    one_c_password: str = ""
    one_c_timeout_seconds: float = 20.0
    # Учитывать системные настройки прокси при обращении к 1С.
    #
    # По умолчанию выключено, и это важно: на Windows httpx берёт прокси не только
    # из переменных окружения, но и из системных настроек (реестра). Если в системе
    # настроен прокси, запрос к локальной публикации 1С уйдёт через него, и вместо
    # данных вернётся 503 без заголовка Server — то есть ответит не 1С, а прокси.
    one_c_trust_env: bool = False

    # --- Кэш показателей ---
    kpi_cache_ttl_seconds: int = 300

    @field_validator("jwt_secret")
    @classmethod
    def _validate_jwt_secret(cls, value: str) -> str:
        if len(value.encode("utf-8")) < MIN_JWT_SECRET_BYTES:
            msg = (
                f"JWT_SECRET слишком короткий: нужно не менее "
                f"{MIN_JWT_SECRET_BYTES} байт, получено {len(value.encode('utf-8'))}. "
                f'Задайте JWT_SECRET в .env (например: python -c "import secrets;'
                f' print(secrets.token_urlsafe(48))").'
            )
            raise ValueError(msg)
        return value

    @field_validator("one_c_base_url")
    @classmethod
    def _validate_one_c_base_url(cls, value: str) -> str:
        cleaned = value.strip().rstrip("/")
        if not cleaned:
            msg = "ONE_C_BASE_URL не задан: укажите адрес HTTP-сервиса расширения 1С."
            raise ValueError(msg)
        return cleaned

    @property
    def one_c_configured(self) -> bool:
        """Заданы ли учётные данные 1С (без них обращение к 1С бессмысленно)."""
        return bool(self.one_c_base_url and self.one_c_user)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    """Вернуть настройки (единственный экземпляр на процесс)."""
    return Settings()


def refresh_settings() -> Settings:
    """Перечитать настройки и обновить модульную ссылку ``settings``.

    Обновление идёт «на месте»: модули, импортировавшие ``settings`` по имени,
    продолжают видеть актуальный объект. Используется в тестах, где окружение
    меняется после импорта приложения.
    """
    global settings
    get_settings.cache_clear()
    settings = get_settings()
    return settings


settings: Settings = get_settings()

__all__ = ["MIN_JWT_SECRET_BYTES", "Settings", "get_settings", "refresh_settings", "settings"]
