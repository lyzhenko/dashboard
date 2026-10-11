"""Безопасность: пароли, токены, настройки."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone

import jwt
import pytest
from sqlalchemy.dialects.postgresql import dialect as postgresql_dialect
from sqlalchemy.dialects.sqlite import dialect as sqlite_dialect
from tests.conftest import JWT_TEST_SECRET

from app.core.config import MIN_JWT_SECRET_BYTES, Settings, get_settings
from app.core.security import (
    TokenError,
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    verify_password,
)
from app.db.types import UtcDateTime, ensure_utc, isoformat_utc, utcnow


def test_password_hash_and_verify() -> None:
    digest = hash_password("dashboard")
    assert digest != "dashboard"
    assert digest.startswith("$argon2")
    assert verify_password("dashboard", digest)
    assert not verify_password("Dashboard", digest)
    assert not verify_password("dashboard", "не-хеш")


def test_access_token_roundtrip() -> None:
    token = create_access_token("42")
    payload = decode_token(token, "access")
    assert payload["sub"] == "42"
    assert payload["type"] == "access"


def test_refresh_token_is_not_access_token() -> None:
    token = create_refresh_token("42")
    assert decode_token(token, "refresh")["type"] == "refresh"
    with pytest.raises(TokenError):
        decode_token(token, "access")


def test_expired_token_is_rejected() -> None:
    expired = jwt.encode(
        {
            "sub": "1",
            "type": "access",
            "exp": int((datetime.now(UTC) - timedelta(minutes=5)).timestamp()),
        },
        get_settings().jwt_secret,
        algorithm="HS256",
    )
    with pytest.raises(TokenError, match="истёк"):
        decode_token(expired, "access")


def test_token_signed_with_other_secret_is_rejected() -> None:
    foreign_secret = "чужой-секрет-для-проверки-подписи-0123456789"
    foreign = jwt.encode({"sub": "1", "type": "access"}, foreign_secret, algorithm="HS256")
    with pytest.raises(TokenError):
        decode_token(foreign, "access")


def test_short_jwt_secret_fails_on_startup() -> None:
    with pytest.raises(ValueError, match="JWT_SECRET слишком короткий"):
        Settings(jwt_secret="короткий", _env_file=None)


def test_secret_of_minimum_length_is_accepted() -> None:
    secret = "a" * MIN_JWT_SECRET_BYTES
    assert Settings(jwt_secret=secret, _env_file=None).jwt_secret == secret


def test_error_message_hides_secret_value() -> None:
    with pytest.raises(ValueError) as exc_info:
        Settings(jwt_secret="top-secret-value", _env_file=None)
    message = str(exc_info.value)
    assert "JWT_SECRET слишком короткий" in message
    assert "top-secret-value" not in message
    assert "32" in message


def test_settings_defaults() -> None:
    settings = Settings(jwt_secret=JWT_TEST_SECRET, _env_file=None)
    assert settings.database_url == "sqlite+aiosqlite:///./var/dashboard.db"
    assert settings.access_token_ttl_seconds == 900
    assert settings.refresh_token_ttl_seconds == 1209600
    assert settings.one_c_timeout_seconds == 20.0
    assert settings.kpi_cache_ttl_seconds == 300
    assert settings.cookie_secure is False
    assert settings.cookie_samesite == "lax"


def test_one_c_base_url_is_normalized() -> None:
    settings = Settings(
        jwt_secret=JWT_TEST_SECRET,
        one_c_base_url="http://localhost:8090/dashboard/hs/dashboard/",
        _env_file=None,
    )
    assert settings.one_c_base_url == "http://localhost:8090/dashboard/hs/dashboard"


def test_utc_datetime_always_returns_aware_value() -> None:
    column_type = UtcDateTime()
    dialect = sqlite_dialect()
    naive = datetime(2026, 10, 11, 7, 40, 0)
    bound = column_type.process_bind_param(naive, dialect)
    assert bound is not None
    assert bound.tzinfo is UTC
    restored = column_type.process_result_value(naive, dialect)
    assert restored is not None
    assert restored.tzinfo is UTC


def test_utc_datetime_normalizes_other_timezone_on_read() -> None:
    """PostgreSQL возвращает осведомлённое значение в поясе сессии."""
    column_type = UtcDateTime()
    dialect = postgresql_dialect()
    moscow = timezone(timedelta(hours=3))
    restored = column_type.process_result_value(
        datetime(2026, 10, 11, 10, 40, 0, tzinfo=moscow), dialect
    )
    assert restored is not None
    assert restored.hour == 7
    assert restored.tzinfo is UTC


def test_isoformat_has_no_timezone_suffix() -> None:
    assert isoformat_utc(datetime(2026, 10, 11, 7, 40, 0, tzinfo=UTC)) == "2026-10-11T07:40:00"
    assert isoformat_utc(None) is None


def test_ensure_utc_converts_other_zones() -> None:
    moscow = timezone(timedelta(hours=3))
    converted = ensure_utc(datetime(2026, 10, 11, 10, 40, 0, tzinfo=moscow))
    assert converted.hour == 7
    assert converted.tzinfo is UTC


def test_utcnow_is_aware() -> None:
    assert utcnow().tzinfo is UTC
