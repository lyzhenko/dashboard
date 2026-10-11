"""API авторизации: вход, обновление токена, выход, сведения о пользователе."""

from __future__ import annotations

from httpx import AsyncClient
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from tests.conftest import DEMO_PASSWORD, DEMO_USERNAME

from app.api.v1.auth import REFRESH_COOKIE_NAME
from app.core.config import get_settings
from app.core.security import create_access_token
from app.models.user import User


def test_refresh_cookie_name_matches_settings() -> None:
    """Имя cookie в настройках и в аннотации параметра обязаны совпадать.

    FastAPI ищет cookie по ``alias`` параметра, поэтому расхождение сломает
    обновление токена молча — параметр всегда будет ``None``.
    """
    assert get_settings().refresh_cookie_name == REFRESH_COOKIE_NAME


async def test_login_returns_token_and_sets_refresh_cookie(
    client: AsyncClient, session: AsyncSession, demo_user: AsyncSession
) -> None:
    stored = (await session.execute(select(User))).scalar_one()

    response = await client.post(
        "/api/v1/auth/login",
        json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD},
    )

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accessToken"]
    assert body["expiresIn"] == get_settings().access_token_ttl_seconds
    assert body["user"] == {
        "id": stored.id,
        "username": DEMO_USERNAME,
        "fullName": "Иванов И. И.",
        "roles": ["viewer"],
    }

    assert response.cookies.get(get_settings().refresh_cookie_name)
    set_cookie = response.headers["set-cookie"]
    assert "HttpOnly" in set_cookie
    assert "samesite=lax" in set_cookie.lower()


async def test_login_is_case_insensitive_by_username(
    client: AsyncClient, demo_user: AsyncSession
) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"username": "Rukovoditel", "password": DEMO_PASSWORD}
    )
    assert response.status_code == 200


async def test_login_with_wrong_password_is_unauthorized(
    client: AsyncClient, demo_user: AsyncSession
) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"username": DEMO_USERNAME, "password": "не тот"}
    )

    assert response.status_code == 401
    assert response.json() == {
        "detail": {"code": "unauthorized", "message": "Неверный логин или пароль"}
    }


async def test_login_of_unknown_user_is_unauthorized(client: AsyncClient) -> None:
    response = await client.post(
        "/api/v1/auth/login", json={"username": "нет-такого", "password": "dashboard"}
    )
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"


async def test_disabled_user_cannot_log_in(
    client: AsyncClient, session: AsyncSession, demo_user: AsyncSession
) -> None:
    from app.services import auth_service

    await auth_service.set_active(session, DEMO_USERNAME, is_active=False)

    response = await client.post(
        "/api/v1/auth/login", json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD}
    )
    assert response.status_code == 401
    assert "отключён" in response.json()["detail"]["message"]


async def test_login_validation_error(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/login", json={"username": "", "password": ""})
    assert response.status_code == 422
    assert response.json()["detail"]["code"] == "validation_error"


async def test_refresh_issues_new_access_token(
    client: AsyncClient, demo_user: AsyncSession
) -> None:
    login = await client.post(
        "/api/v1/auth/login", json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD}
    )
    assert login.status_code == 200

    response = await client.post("/api/v1/auth/refresh")

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["accessToken"]
    assert body["expiresIn"] == get_settings().access_token_ttl_seconds
    # Новый access-токен должен работать.
    me = await client.get(
        "/api/v1/auth/me", headers={"Authorization": f"Bearer {body['accessToken']}"}
    )
    assert me.status_code == 200
    assert me.json()["username"] == DEMO_USERNAME


async def test_refresh_without_cookie_is_unauthorized(client: AsyncClient) -> None:
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"


async def test_refresh_with_garbage_token_is_unauthorized(
    client: AsyncClient, demo_user: AsyncSession
) -> None:
    client.cookies.set(get_settings().refresh_cookie_name, "not-a-token")
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401


async def test_access_token_is_not_accepted_as_refresh(
    client: AsyncClient, demo_user: AsyncSession
) -> None:
    login = await client.post(
        "/api/v1/auth/login", json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD}
    )
    client.cookies.set(get_settings().refresh_cookie_name, login.json()["accessToken"], path="/")
    response = await client.post("/api/v1/auth/refresh")
    assert response.status_code == 401
    assert "тип токена" in response.json()["detail"]["message"]


async def test_logout_clears_cookie(client: AsyncClient, demo_user: AsyncSession) -> None:
    await client.post(
        "/api/v1/auth/login", json={"username": DEMO_USERNAME, "password": DEMO_PASSWORD}
    )
    response = await client.post("/api/v1/auth/logout")

    assert response.status_code == 200
    assert response.json() == {"message": "Вы вышли из системы"}
    assert "max-age=0" in response.headers["set-cookie"].lower()


async def test_me_returns_current_user(
    client: AsyncClient, demo_user: AsyncSession, auth_headers: dict[str, str]
) -> None:
    response = await client.get("/api/v1/auth/me", headers=auth_headers)

    assert response.status_code == 200
    assert response.json()["username"] == DEMO_USERNAME
    assert response.json()["roles"] == ["viewer"]


async def test_me_without_token_is_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"


async def test_me_with_broken_token_is_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-token"})
    assert response.status_code == 401


async def test_me_with_wrong_scheme_is_unauthorized(client: AsyncClient) -> None:
    response = await client.get("/api/v1/auth/me", headers={"Authorization": "Basic 1234"})
    assert response.status_code == 401


async def test_token_of_deleted_user_is_rejected(
    client: AsyncClient, session: AsyncSession, demo_user: AsyncSession
) -> None:
    token = create_access_token("999999")
    await session.execute(delete(User).where(User.username == DEMO_USERNAME))
    await session.commit()

    response = await client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "не найден" in response.json()["detail"]["message"]
