"""``/api/bot-settings``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vkt_bot.core.constants import DEFAULT_START_MESSAGE
from vkt_bot.core.repositories.bot_settings import BotSettingsRepository

from tests.conftest import auth_headers

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkt_bot.core.models import ChatUser


class TestGetSetting:
    """``GET /api/bot-settings/{key}``."""

    async def test_returns_saved_setting(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        repo = BotSettingsRepository(session)
        await repo.set_value("start_message", "Привет", "Приветствие")
        await session.commit()

        response = await client.get(
            "/api/bot-settings/start_message", headers=auth_headers(superuser.id)
        )

        assert response.status_code == 200
        body = response.json()
        assert body["value"] == "Привет"
        assert body["description"] == "Приветствие"

    async def test_start_message_falls_back_to_default(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.get(
            "/api/bot-settings/start_message", headers=auth_headers(superuser.id)
        )

        assert response.status_code == 200
        assert response.json()["value"] == DEFAULT_START_MESSAGE

    async def test_unknown_key_is_404(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.get(
            "/api/bot-settings/nope", headers=auth_headers(superuser.id)
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"]

    async def test_plain_user_is_forbidden(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.get(
            "/api/bot-settings/start_message", headers=auth_headers(user.id)
        )
        assert response.status_code == 403


class TestUpdateSetting:
    """``PUT /api/bot-settings/{key}``."""

    async def test_creates_setting(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        response = await client.put(
            "/api/bot-settings/greeting",
            json={"value": "Здравствуйте", "description": "Приветствие"},
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 200
        assert response.json()["value"] == "Здравствуйте"
        assert (
            await BotSettingsRepository(session).get_by_key("greeting")
        ).value == "Здравствуйте"

    async def test_updates_existing(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        repo = BotSettingsRepository(session)
        await repo.set_value("greeting", "старое")
        await session.commit()

        response = await client.put(
            "/api/bot-settings/greeting",
            json={"value": "новое"},
            headers=auth_headers(superuser.id),
        )

        assert response.json()["value"] == "новое"

    async def test_empty_start_message_restores_default(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.put(
            "/api/bot-settings/start_message",
            json={"value": "   "},
            headers=auth_headers(superuser.id),
        )

        assert response.json()["value"] == DEFAULT_START_MESSAGE

    async def test_empty_value_for_other_keys_is_kept(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.put(
            "/api/bot-settings/other",
            json={"value": ""},
            headers=auth_headers(superuser.id),
        )
        assert response.json()["value"] == ""

    async def test_missing_value(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        response = await client.put(
            "/api/bot-settings/greeting",
            json={},
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 422

    async def test_plain_user_is_forbidden(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.put(
            "/api/bot-settings/greeting",
            json={"value": "x"},
            headers=auth_headers(user.id),
        )
        assert response.status_code == 403


class TestListSettings:
    """``GET /api/bot-settings``."""

    async def test_empty(self, client: httpx.AsyncClient, superuser: ChatUser) -> None:
        response = await client.get(
            "/api/bot-settings", headers=auth_headers(superuser.id)
        )
        assert response.status_code == 200
        assert response.json() == []

    async def test_lists_all(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        repo = BotSettingsRepository(session)
        await repo.set_value("a", "1")
        await repo.set_value("b", "2")
        await session.commit()

        body = (
            await client.get("/api/bot-settings", headers=auth_headers(superuser.id))
        ).json()

        assert {item["key"]: item["value"] for item in body} == {"a": "1", "b": "2"}

    async def test_does_not_include_default_start_message(
        self, client: httpx.AsyncClient, superuser: ChatUser
    ) -> None:
        """Список отдаёт только сохранённые настройки, без подстановки дефолта."""
        body = (
            await client.get("/api/bot-settings", headers=auth_headers(superuser.id))
        ).json()
        assert body == []
