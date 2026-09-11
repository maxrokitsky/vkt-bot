"""Аутентификация и зависимости доступа."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest
from jose import jwt

from vkt_bot.core.models import LoginHistory, LoginToken
from vkt_bot.core.repositories.login_token import LoginTokenRepository
from vkt_bot.webapp.api.auth import create_access_token

from tests.conftest import auth_headers, table_count
from tests.factories import create_chat_user

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkt_bot.config import VktSettings
    from vkt_bot.core.models import ChatUser


async def make_token(
    session: AsyncSession, user_id: str, **kwargs: object
) -> LoginToken:
    """Создать одноразовый токен входа."""
    token = await LoginTokenRepository(session).create_token(user_id)
    for key, value in kwargs.items():
        setattr(token, key, value)
    session.add(token)
    await session.commit()
    return token


class TestCreateAccessToken:
    """``create_access_token``."""

    def test_contains_subject_and_expiry(self, settings: VktSettings) -> None:
        token = create_access_token(data={"sub": "user@example.com"})
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])

        assert payload["sub"] == "user@example.com"
        assert "exp" in payload

    def test_default_expiry_comes_from_settings(self, settings: VktSettings) -> None:
        token = create_access_token(data={"sub": "u"})
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        expires_in = datetime.datetime.fromtimestamp(
            payload["exp"], tz=datetime.UTC
        ) - datetime.datetime.now(datetime.UTC)

        expected = datetime.timedelta(minutes=settings.access_token_expire_minutes)
        assert expected - datetime.timedelta(minutes=1) < expires_in <= expected

    def test_explicit_expiry(self, settings: VktSettings) -> None:
        token = create_access_token(
            data={"sub": "u"}, expires_delta=datetime.timedelta(minutes=5)
        )
        payload = jwt.decode(token, settings.secret_key, algorithms=["HS256"])
        expires_in = datetime.datetime.fromtimestamp(
            payload["exp"], tz=datetime.UTC
        ) - datetime.datetime.now(datetime.UTC)

        assert expires_in <= datetime.timedelta(minutes=5)

    def test_signed_with_other_key_is_rejected(self) -> None:
        token = jwt.encode({"sub": "u"}, "other-key", algorithm="HS256")
        with pytest.raises(Exception, match="[Ss]ignature"):
            jwt.decode(token, "test-secret-key", algorithms=["HS256"])


class TestLogin:
    """``POST /api/auth/login``."""

    async def test_success_returns_bearer_token(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        token = await make_token(session, user.id)

        response = await client.post("/api/auth/login", json={"token": token.token})

        assert response.status_code == 200
        body = response.json()
        assert body["token_type"] == "bearer"
        assert body["access_token"]

    async def test_token_subject_is_the_user(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        user: ChatUser,
        settings: VktSettings,
    ) -> None:
        token = await make_token(session, user.id)
        response = await client.post("/api/auth/login", json={"token": token.token})

        payload = jwt.decode(
            response.json()["access_token"], settings.secret_key, algorithms=["HS256"]
        )
        assert payload["sub"] == user.id

    async def test_token_is_marked_used(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        token = await make_token(session, user.id)
        token_value = token.token
        await client.post("/api/auth/login", json={"token": token_value})

        await session.refresh(token)
        assert (await LoginTokenRepository(session).get_by_token(token_value)).used

    async def test_login_is_recorded_in_history(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        token = await make_token(session, user.id)
        await client.post(
            "/api/auth/login",
            json={"token": token.token},
            headers={"user-agent": "pytest-agent"},
        )

        assert await table_count(session, LoginHistory) == 1

    async def test_whitespace_is_stripped(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        token = await make_token(session, user.id)
        response = await client.post(
            "/api/auth/login", json={"token": f"  {token.token}  "}
        )
        assert response.status_code == 200

    async def test_unknown_token(self, client: httpx.AsyncClient) -> None:
        response = await client.post("/api/auth/login", json={"token": "nope"})
        assert response.status_code == 401
        assert response.json()["detail"] == "Invalid token"

    async def test_expired_token(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        token = await make_token(
            session,
            user.id,
            expires_at=datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
            - datetime.timedelta(minutes=1),
        )

        response = await client.post("/api/auth/login", json={"token": token.token})

        assert response.status_code == 401
        assert response.json()["detail"] == "Token expired"

    async def test_used_token(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        token = await make_token(session, user.id, used=True)

        response = await client.post("/api/auth/login", json={"token": token.token})

        assert response.status_code == 401
        assert response.json()["detail"] == "Token already used"

    async def test_token_cannot_be_reused(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        token = await make_token(session, user.id)

        first = await client.post("/api/auth/login", json={"token": token.token})
        second = await client.post("/api/auth/login", json={"token": token.token})

        assert first.status_code == 200
        assert second.status_code == 401

    async def test_missing_body_field(self, client: httpx.AsyncClient) -> None:
        response = await client.post("/api/auth/login", json={})
        assert response.status_code == 422


class TestCurrentUser:
    """``GET /api/auth/me`` и зависимость ``CurrentUser``."""

    async def test_returns_user(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.get("/api/auth/me", headers=auth_headers(user.id))

        assert response.status_code == 200
        assert response.json() == {
            "id": user.id,
            "is_superuser": False,
            "is_bot": False,
            "first_name": None,
            "last_name": None,
            "nick": None,
            "about": None,
            "photo_url": None,
            "is_owner": False,
            "display_name": user.id,
        }

    async def test_returns_display_name(
        self, client: httpx.AsyncClient, session: AsyncSession
    ) -> None:
        """Панель показывает имя из профиля, а не id."""
        me = await create_chat_user(
            session, "ivan@example.com", first_name="Иван", last_name="Иванов"
        )

        body = (await client.get("/api/auth/me", headers=auth_headers(me.id))).json()

        assert body["display_name"] == "Иван Иванов"
        assert body["first_name"] == "Иван"

    async def test_owner_flag(self, client: httpx.AsyncClient, owner: ChatUser) -> None:
        response = await client.get("/api/auth/me", headers=auth_headers(owner.id))
        assert response.json()["is_owner"] is True

    async def test_superuser_flag(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.get("/api/auth/me", headers=auth_headers(superuser.id))
        assert response.json()["is_superuser"] is True

    async def test_without_header(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/auth/me")).status_code == 403

    async def test_malformed_header(self, client: httpx.AsyncClient) -> None:
        response = await client.get(
            "/api/auth/me", headers={"Authorization": "Token abc"}
        )
        assert response.status_code == 403

    async def test_invalid_jwt(self, client: httpx.AsyncClient) -> None:
        response = await client.get(
            "/api/auth/me", headers={"Authorization": "Bearer garbage"}
        )
        assert response.status_code == 401

    async def test_jwt_signed_with_other_key(self, client: httpx.AsyncClient) -> None:
        token = jwt.encode({"sub": "u"}, "wrong-key", algorithm="HS256")
        response = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401

    async def test_expired_jwt(self, client: httpx.AsyncClient, user: ChatUser) -> None:
        token = create_access_token(
            data={"sub": user.id}, expires_delta=datetime.timedelta(minutes=-5)
        )
        response = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401

    async def test_jwt_without_subject(self, client: httpx.AsyncClient) -> None:
        token = create_access_token(data={"foo": "bar"})
        response = await client.get(
            "/api/auth/me", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 401

    async def test_jwt_for_unknown_user(self, client: httpx.AsyncClient) -> None:
        response = await client.get(
            "/api/auth/me", headers=auth_headers("ghost@example.com")
        )
        assert response.status_code == 401


class TestAdminAccess:
    """``CurrentAdminUser`` — на примере ``GET /api/bot-settings``."""

    ENDPOINT = "/api/bot-settings"

    async def test_plain_user_is_forbidden(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.get(self.ENDPOINT, headers=auth_headers(user.id))

        assert response.status_code == 403
        assert "Admin access required" in response.json()["detail"]

    async def test_superuser_is_allowed(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.get(self.ENDPOINT, headers=auth_headers(superuser.id))
        assert response.status_code == 200

    async def test_owner_is_allowed_without_superuser_flag(
        self, client: httpx.AsyncClient, owner: ChatUser
    ) -> None:
        assert owner.is_superuser is False
        response = await client.get(self.ENDPOINT, headers=auth_headers(owner.id))
        assert response.status_code == 200

    async def test_anonymous_is_rejected(self, client: httpx.AsyncClient) -> None:
        assert (await client.get(self.ENDPOINT)).status_code == 403


class TestOwnerAccess:
    """``CurrentOwnerUser`` — на примере ``PATCH /api/chat-users/{id}``."""

    async def test_superuser_is_not_enough(
        self, client: httpx.AsyncClient, superuser: ChatUser, user: ChatUser
    ) -> None:
        response = await client.patch(
            f"/api/chat-users/{user.id}",
            json={"is_superuser": True},
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 403
        assert "Owner access required" in response.json()["detail"]

    async def test_owner_is_allowed(
        self, client: httpx.AsyncClient, owner: ChatUser, user: ChatUser
    ) -> None:
        response = await client.patch(
            f"/api/chat-users/{user.id}",
            json={"is_superuser": True},
            headers=auth_headers(owner.id),
        )
        assert response.status_code == 200


class TestDependencyHelpers:
    """``is_owner`` / ``is_admin``."""

    def test_is_owner(self, owner_id: str) -> None:
        from vkt_bot.core.models import ChatUser
        from vkt_bot.webapp.dependencies import is_owner

        assert is_owner(ChatUser(id=owner_id)) is True
        assert is_owner(ChatUser(id="other@example.com")) is False

    def test_is_admin_for_superuser(self) -> None:
        from vkt_bot.core.models import ChatUser
        from vkt_bot.webapp.dependencies import is_admin

        assert is_admin(ChatUser(id="a@example.com", is_superuser=True)) is True

    def test_is_admin_for_owner(self, owner_id: str) -> None:
        from vkt_bot.core.models import ChatUser
        from vkt_bot.webapp.dependencies import is_admin

        assert is_admin(ChatUser(id=owner_id, is_superuser=False)) is True

    def test_is_admin_for_plain_user(self) -> None:
        from vkt_bot.core.models import ChatUser
        from vkt_bot.webapp.dependencies import is_admin

        assert is_admin(ChatUser(id="u@example.com", is_superuser=False)) is False

    def test_is_owner_without_configured_owner(
        self, monkeypatch: pytest.MonkeyPatch, settings: VktSettings
    ) -> None:
        from vkt_bot.core.models import ChatUser
        from vkt_bot.webapp.dependencies import is_owner

        monkeypatch.setattr(settings, "owner_id", None)
        assert is_owner(ChatUser(id="anyone@example.com")) is False


class TestServiceEndpoints:
    """Служебные ручки."""

    async def test_root(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/")
        assert response.status_code == 200
        assert response.json() == {"message": "VKT Bot API"}

    async def test_health(self, client: httpx.AsyncClient) -> None:
        response = await client.get("/health")
        assert response.json() == {"status": "ok"}
