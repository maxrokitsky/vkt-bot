"""``/api/chats``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from tests.conftest import auth_headers
from tests.factories import create_chat

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession

    from tests.conftest import FakeBot
    from vkt_bot.core.models import ChatUser


class TestListChats:
    """``GET /api/chats``."""

    async def test_empty(self, client: httpx.AsyncClient, user: ChatUser) -> None:
        response = await client.get("/api/chats", headers=auth_headers(user.id))
        assert response.status_code == 200
        assert response.json()["items"] == []

    async def test_lists_chats(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat(session, "a@chat.agent")
        await create_chat(session, "b@chat.agent", "channel")

        body = (await client.get("/api/chats", headers=auth_headers(user.id))).json()

        assert body["total"] == 2
        assert {item["id"] for item in body["items"]} == {
            "a@chat.agent",
            "b@chat.agent",
        }

    async def test_title_is_null_until_known(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        """Название приходит только из событий, до тех пор — ``null``."""
        await create_chat(session, "a@chat.agent")
        body = (await client.get("/api/chats", headers=auth_headers(user.id))).json()
        assert body["items"][0]["title"] is None

    async def test_returns_title_and_type(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat(session, "a@chat.agent", "channel", title="Релизы")

        body = (await client.get("/api/chats", headers=auth_headers(user.id))).json()

        assert body["items"][0]["title"] == "Релизы"
        assert body["items"][0]["type"] == "channel"

    async def test_pagination(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        for i in range(5):
            await create_chat(session, f"chat-{i}@chat.agent")

        body = (
            await client.get(
                "/api/chats",
                params={"page": 2, "size": 2},
                headers=auth_headers(user.id),
            )
        ).json()

        assert len(body["items"]) == 2
        assert body["pages"] == 3

    async def test_requires_authentication(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/chats")).status_code == 403


class TestGetChat:
    """``GET /api/chats/{chat_id}``."""

    async def test_found(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat(session, "a@chat.agent")
        response = await client.get(
            "/api/chats/a@chat.agent", headers=auth_headers(user.id)
        )

        assert response.status_code == 200
        assert response.json()["id"] == "a@chat.agent"

    async def test_missing(self, client: httpx.AsyncClient, user: ChatUser) -> None:
        response = await client.get(
            "/api/chats/nope@chat.agent", headers=auth_headers(user.id)
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Chat not found"

    async def test_requires_authentication(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/chats/x")).status_code == 403


class TestSendMessage:
    """``POST /api/chats/{chat_id}/send-message``."""

    async def test_sends_via_bot(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        superuser: ChatUser,
        patched_bot: FakeBot,
    ) -> None:
        await create_chat(session, "a@chat.agent")

        response = await client.post(
            "/api/chats/a@chat.agent/send-message",
            json={"text": "Привет"},
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 200
        assert response.json() == {
            "success": True,
            "message": "Message sent successfully",
        }
        (call,) = patched_bot.sent
        assert call.kwargs["chat_id"] == "a@chat.agent"
        assert call.kwargs["text"] == "Привет"

    async def test_parse_mode_is_forwarded(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        superuser: ChatUser,
        patched_bot: FakeBot,
    ) -> None:
        await create_chat(session, "a@chat.agent")

        await client.post(
            "/api/chats/a@chat.agent/send-message",
            json={"text": "Привет", "parse_mode": "MarkdownV2"},
            headers=auth_headers(superuser.id),
        )

        assert patched_bot.sent[0].kwargs["parse_mode"] == "MarkdownV2"

    async def test_unknown_chat(
        self, client: httpx.AsyncClient, superuser: ChatUser, patched_bot: FakeBot
    ) -> None:
        response = await client.post(
            "/api/chats/nope@chat.agent/send-message",
            json={"text": "Привет"},
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 404
        assert patched_bot.calls == []

    async def test_bot_error_becomes_500(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        superuser: ChatUser,
        patched_bot: FakeBot,
    ) -> None:
        await create_chat(session, "a@chat.agent")
        patched_bot.errors["send_text"] = RuntimeError("нет сети")

        response = await client.post(
            "/api/chats/a@chat.agent/send-message",
            json={"text": "Привет"},
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 500
        assert "нет сети" in response.json()["detail"]

    async def test_plain_user_is_forbidden(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat(session, "a@chat.agent")
        response = await client.post(
            "/api/chats/a@chat.agent/send-message",
            json={"text": "Привет"},
            headers=auth_headers(user.id),
        )
        assert response.status_code == 403

    async def test_empty_text_is_rejected(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await create_chat(session, "a@chat.agent")
        response = await client.post(
            "/api/chats/a@chat.agent/send-message",
            json={"text": ""},
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 422

    async def test_too_long_text_is_rejected(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await create_chat(session, "a@chat.agent")
        response = await client.post(
            "/api/chats/a@chat.agent/send-message",
            json={"text": "x" * 4097},
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 422

    async def test_unknown_parse_mode_is_rejected(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        await create_chat(session, "a@chat.agent")
        response = await client.post(
            "/api/chats/a@chat.agent/send-message",
            json={"text": "x", "parse_mode": "Markdown"},
            headers=auth_headers(superuser.id),
        )
        assert response.status_code == 422


class TestSearchChats:
    """``GET /api/chats?search=``."""

    async def test_by_title(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat(session, "a@chat.agent", title="Release notes")
        await create_chat(session, "b@chat.agent", title="Support")

        body = (
            await client.get(
                "/api/chats", params={"search": "rele"}, headers=auth_headers(user.id)
            )
        ).json()

        assert body["total"] == 1
        assert body["items"][0]["id"] == "a@chat.agent"

    async def test_by_id(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat(session, "681869378@chat.agent", title="Релизы")
        await create_chat(session, "999@chat.agent", title="Поддержка")

        body = (
            await client.get(
                "/api/chats",
                params={"search": "6818"},
                headers=auth_headers(user.id),
            )
        ).json()

        assert [item["id"] for item in body["items"]] == ["681869378@chat.agent"]

    async def test_total_counts_only_matches(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        """``total`` — по найденному, иначе пагинация врёт."""
        for i in range(5):
            await create_chat(session, f"{i}@ch.agent", title=f"Release {i}")
        await create_chat(session, "x@ch.agent", title="Nope")

        body = (
            await client.get(
                "/api/chats",
                params={"search": "Release"},
                headers=auth_headers(user.id),
            )
        ).json()

        assert body["total"] == 5

    async def test_no_matches(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat(session, "a@chat.agent", title="Release notes")

        body = (
            await client.get(
                "/api/chats", params={"search": "zzz"}, headers=auth_headers(user.id)
            )
        ).json()

        assert body["items"] == []
        assert body["total"] == 0

    async def test_blank_search_returns_all(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat(session, "a@chat.agent", title="Release notes")
        await create_chat(session, "b@chat.agent", title="Support")

        body = (
            await client.get(
                "/api/chats", params={"search": "   "}, headers=auth_headers(user.id)
            )
        ).json()

        assert body["total"] == 2

    async def test_cyrillic_is_case_insensitive(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        user: ChatUser,
        is_postgres: bool,
    ) -> None:
        """``ilike`` приводит регистр кириллицы только в PostgreSQL."""
        if not is_postgres:
            pytest.skip("SQLite не приводит регистр кириллицы в LIKE")
        await create_chat(session, "a@chat.agent", title="Релизы")

        body = (
            await client.get(
                "/api/chats", params={"search": "РЕЛИЗ"}, headers=auth_headers(user.id)
            )
        ).json()

        assert [item["id"] for item in body["items"]] == ["a@chat.agent"]
