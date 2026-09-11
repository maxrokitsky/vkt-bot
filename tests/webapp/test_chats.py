"""``/api/chats``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vkt_bot.core.models import ChatMembership
from vkt_bot.core.repositories.webhook import WebhookRepository
from vkt_bot.webapp.schemas.webhook import WebhookCreateSchema

from tests.conftest import auth_headers
from tests.factories import create_chat, create_chat_user

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

    async def test_returns_info_from_get_info(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        """Описание, правила, ссылка и флаги — всё из ``chats/getInfo``."""
        await create_chat(
            session,
            "a@chat.agent",
            about="Описание",
            rules="Правила",
            invite_link="https://icq.com/chat/AoLLi9QjQqY9G2FMXzA",
            public=False,
            join_moderation=True,
        )

        body = (
            await client.get("/api/chats/a@chat.agent", headers=auth_headers(user.id))
        ).json()

        assert body["about"] == "Описание"
        assert body["rules"] == "Правила"
        assert body["public"] is False
        assert body["join_moderation"] is True

    async def test_invite_link_only_for_members(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        """Ссылка — это вход в чат, а список чатов в панели видят все."""
        link = "https://icq.com/chat/AoLLi9QjQqY9G2FMXzA"
        chat = await create_chat(session, "a@chat.agent", invite_link=link)

        outsider = (
            await client.get("/api/chats/a@chat.agent", headers=auth_headers(user.id))
        ).json()
        assert outsider["invite_link"] is None

        session.add(ChatMembership(chat_id=chat.id, user_id=user.id))
        await session.commit()

        member = (
            await client.get("/api/chats/a@chat.agent", headers=auth_headers(user.id))
        ).json()
        assert member["invite_link"] == link

    async def test_admin_sees_invite_link(
        self, client: httpx.AsyncClient, session: AsyncSession, owner: ChatUser
    ) -> None:
        """Администратору чат виден целиком и без членства."""
        link = "https://icq.com/chat/AoLLi9QjQqY9G2FMXzA"
        await create_chat(session, "a@chat.agent", invite_link=link)

        body = (
            await client.get("/api/chats/a@chat.agent", headers=auth_headers(owner.id))
        ).json()

        assert body["invite_link"] == link

    async def test_list_has_no_invite_links(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        """В списке ссылок нет вовсе — он отдаёт все чаты бота подряд."""
        await create_chat(
            session, "a@chat.agent", invite_link="https://icq.com/chat/AoLL"
        )

        body = (await client.get("/api/chats", headers=auth_headers(user.id))).json()

        assert "invite_link" not in body["items"][0]

    async def test_counts_members(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        chat = await create_chat(session, "a@chat.agent")
        other = await create_chat_user(session, "second@example.com")
        session.add_all(
            [
                ChatMembership(chat_id=chat.id, user_id=user.id),
                ChatMembership(chat_id=chat.id, user_id=other.id),
            ]
        )
        await session.commit()

        body = (
            await client.get("/api/chats/a@chat.agent", headers=auth_headers(user.id))
        ).json()

        assert body["member_count"] == 2

    async def test_counts_are_zero_for_empty_chat(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat(session, "a@chat.agent")

        body = (
            await client.get("/api/chats/a@chat.agent", headers=auth_headers(user.id))
        ).json()

        assert body["member_count"] == 0
        assert body["webhook_count"] == 0

    async def test_webhook_count_shows_only_own_to_plain_user(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        """Счётчик обещает ровно то, что покажет список вебхуков."""
        chat = await create_chat(session, "a@chat.agent")
        other = await create_chat_user(session, "second@example.com")
        repo = WebhookRepository(session)
        await repo.create_with_api_key(
            WebhookCreateSchema(name="свой", chat_id=chat.id), user.id
        )
        await repo.create_with_api_key(
            WebhookCreateSchema(name="чужой", chat_id=chat.id), other.id
        )

        body = (
            await client.get("/api/chats/a@chat.agent", headers=auth_headers(user.id))
        ).json()

        assert body["webhook_count"] == 1

    async def test_webhook_count_shows_all_to_admin(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        chat = await create_chat(session, "a@chat.agent")
        other = await create_chat_user(session, "second@example.com")
        repo = WebhookRepository(session)
        await repo.create_with_api_key(
            WebhookCreateSchema(name="свой", chat_id=chat.id), superuser.id
        )
        await repo.create_with_api_key(
            WebhookCreateSchema(name="чужой", chat_id=chat.id), other.id
        )

        body = (
            await client.get(
                "/api/chats/a@chat.agent", headers=auth_headers(superuser.id)
            )
        ).json()

        assert body["webhook_count"] == 2

    async def test_missing(self, client: httpx.AsyncClient, user: ChatUser) -> None:
        response = await client.get(
            "/api/chats/nope@chat.agent", headers=auth_headers(user.id)
        )
        assert response.status_code == 404
        assert response.json()["detail"] == "Chat not found"

    async def test_requires_authentication(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/chats/x")).status_code == 403


class TestListChatWebhooks:
    """``GET /api/chats/{chat_id}/webhooks``."""

    async def test_empty(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        await create_chat(session, "a@chat.agent")

        response = await client.get(
            "/api/chats/a@chat.agent/webhooks", headers=auth_headers(user.id)
        )

        assert response.status_code == 200
        assert response.json() == {"webhooks": [], "total": 0}

    async def test_only_webhooks_of_this_chat(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        chat = await create_chat(session, "a@chat.agent")
        another = await create_chat(session, "b@chat.agent")
        repo = WebhookRepository(session)
        await repo.create_with_api_key(
            WebhookCreateSchema(name="здесь", chat_id=chat.id), user.id
        )
        await repo.create_with_api_key(
            WebhookCreateSchema(name="там", chat_id=another.id), user.id
        )

        body = (
            await client.get(
                "/api/chats/a@chat.agent/webhooks", headers=auth_headers(user.id)
            )
        ).json()

        assert body["total"] == 1
        assert body["webhooks"][0]["name"] == "здесь"

    async def test_plain_user_sees_only_own(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        chat = await create_chat(session, "a@chat.agent")
        other = await create_chat_user(session, "second@example.com")
        repo = WebhookRepository(session)
        await repo.create_with_api_key(
            WebhookCreateSchema(name="свой", chat_id=chat.id), user.id
        )
        await repo.create_with_api_key(
            WebhookCreateSchema(name="чужой", chat_id=chat.id), other.id
        )

        body = (
            await client.get(
                "/api/chats/a@chat.agent/webhooks", headers=auth_headers(user.id)
            )
        ).json()

        assert [item["name"] for item in body["webhooks"]] == ["свой"]

    async def test_admin_sees_all(
        self, client: httpx.AsyncClient, session: AsyncSession, superuser: ChatUser
    ) -> None:
        chat = await create_chat(session, "a@chat.agent")
        other = await create_chat_user(session, "second@example.com")
        await WebhookRepository(session).create_with_api_key(
            WebhookCreateSchema(name="чужой", chat_id=chat.id), other.id
        )

        body = (
            await client.get(
                "/api/chats/a@chat.agent/webhooks", headers=auth_headers(superuser.id)
            )
        ).json()

        assert [item["name"] for item in body["webhooks"]] == ["чужой"]

    async def test_api_key_is_not_returned(
        self, client: httpx.AsyncClient, session: AsyncSession, user: ChatUser
    ) -> None:
        chat = await create_chat(session, "a@chat.agent")
        await WebhookRepository(session).create_with_api_key(
            WebhookCreateSchema(name="хук", chat_id=chat.id), user.id
        )

        body = (
            await client.get(
                "/api/chats/a@chat.agent/webhooks", headers=auth_headers(user.id)
            )
        ).json()

        assert "api_key" not in body["webhooks"][0]
        assert "api_key_hash" not in body["webhooks"][0]

    async def test_unknown_chat(
        self, client: httpx.AsyncClient, user: ChatUser
    ) -> None:
        response = await client.get(
            "/api/chats/nope@chat.agent/webhooks", headers=auth_headers(user.id)
        )

        assert response.status_code == 404
        assert response.json()["detail"] == "Chat not found"

    async def test_requires_authentication(self, client: httpx.AsyncClient) -> None:
        assert (await client.get("/api/chats/x/webhooks")).status_code == 403


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
