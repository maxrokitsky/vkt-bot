"""Четыре источника событий: панель, команда, API и сам бот."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from vkt_bot.core.bot_events import record_bot_action
from vkt_bot.core.handlers.chats import (
    ChatInfoChangedHandler,
    ChatMembersJoinedHandler,
    ChatMembersLeftHandler,
    CreateChatMiddleware,
)
from vkt_bot.core.handlers.roles import CreateRoleHandler
from vkt_bot.core.handlers.threads import SubscribeThreadsHandler
from vkt_bot.core.handlers.webhooks import CreateWebhookHandler
from vkt_bot.core.models.event import ActorType, EventSource
from vkt_bot.core.repositories.event import EventRepository

from tests.conftest import auth_headers
from tests.factories import create_chat, create_chat_user, make_event

if TYPE_CHECKING:
    import httpx
    from sqlalchemy.ext.asyncio import AsyncSession
    from vkt_dispatcher import Dispatcher

    from tests.conftest import FakeBot
    from vkt_bot.core.models import Chat, ChatUser

CHAT_ID = "681869378@chat.agent"


def owner_message(text: str, owner_id: str) -> object:
    """Сообщение от владельца бота."""
    return make_event("new_message", text=text, **{"from": {"userId": owner_id}})


async def types_of(session: AsyncSession) -> list[str]:
    """Типы записанных событий."""
    return [row.type for row in await EventRepository(session).list()]


@pytest.fixture
async def chat(session: AsyncSession) -> Chat:
    return await create_chat(session, CHAT_ID)


class TestCommandSource:
    """Команды в чате: ``source=command`` и всегда есть чат."""

    async def test_role_created_by_command(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        await CreateRoleHandler.handle(
            owner_message("/createrole devs", owner_id), dispatcher
        )

        (row,) = await EventRepository(session).list()
        assert row.type == "role.created"
        assert row.source is EventSource.COMMAND
        assert row.chat_id == CHAT_ID
        assert row.actor_id == owner_id
        assert row.payload == {"role": "devs"}

    async def test_webhook_created_by_command(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        chat: Chat,
        owner_id: str,
    ) -> None:
        await CreateWebhookHandler.handle(
            owner_message("/createwebhook Хук", owner_id), dispatcher
        )

        (row,) = await EventRepository(session).list()
        assert row.type == "webhook.created"
        assert row.source is EventSource.COMMAND
        assert row.chat_id == CHAT_ID

    async def test_thread_autosubscribe_toggle(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        await SubscribeThreadsHandler.handle(
            owner_message("/subscribethreads off", owner_id), dispatcher
        )

        (row,) = await EventRepository(session).list()
        assert row.type == "thread.autosubscribe_changed"
        assert row.payload == {"enabled": "выключена"}

    async def test_failed_api_call_writes_no_event(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        """API отказал — подписки нет, значит и события быть не должно."""
        fake_bot.results["threads_autosubscribe"] = None
        fake_bot.errors["threads_autosubscribe"] = RuntimeError("боом")

        await SubscribeThreadsHandler.handle(
            owner_message("/subscribethreads", owner_id), dispatcher
        )

        assert await types_of(session) == []


class TestApiSource:
    """События опроса: ``source=api``, актор — тот, кто их вызвал."""

    async def test_chat_registered_on_first_message(
        self, session: AsyncSession
    ) -> None:
        await CreateChatMiddleware().on_event(make_event("new_message"))

        (row,) = await EventRepository(session).list()
        assert row.type == "chat.registered"
        assert row.source is EventSource.API
        assert row.chat_id

    async def test_second_message_writes_nothing(self, session: AsyncSession) -> None:
        middleware = CreateChatMiddleware()
        await middleware.on_event(make_event("new_message"))
        await middleware.on_event(make_event("new_message"))

        assert await types_of(session) == ["chat.registered"]

    async def test_member_joined(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatMembersJoinedHandler.handle(
            make_event("new_chat_members"), dispatcher
        )

        (row,) = await EventRepository(session).list()
        assert row.type == "chat.member_joined"
        assert row.source is EventSource.API

    async def test_bot_added_to_chat(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Добавили самого бота — это отдельное событие."""
        from vkteams_client.types import GetMembersResponse

        fake_bot.results["get_members"] = GetMembersResponse(ok=True, members=[])

        await ChatMembersJoinedHandler.handle(
            make_event(
                "new_chat_members",
                newMembers=[
                    {"firstName": "Бот", "userId": "bot@example.com", "nick": "bot"}
                ],
            ),
            dispatcher,
        )

        (row,) = await EventRepository(session).list()
        assert row.type == "chat.bot_added"

    async def test_member_left(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatMembersLeftHandler.handle(make_event("left_chat_members"), dispatcher)

        (row,) = await EventRepository(session).list()
        assert row.type in {"chat.member_left", "chat.bot_removed"}
        assert row.source is EventSource.API

    async def test_chat_info_changed(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatInfoChangedHandler.handle(make_event("changed_chat_info"), dispatcher)

        (row,) = await EventRepository(session).list()
        assert row.type == "chat.info_changed"


class TestBotSource:
    """Действия самого бота приезжают из клиента через ``event_sink``."""

    async def test_failed_send_is_recorded(self, session: AsyncSession) -> None:
        await record_bot_action(
            "message.send_failed",
            {"chat_id": CHAT_ID, "reason": "Chat not found", "text_preview": "привет"},
        )

        (row,) = await EventRepository(session).list()
        assert row.type == "message.send_failed"
        assert row.source is EventSource.BOT
        assert row.actor_type is ActorType.BOT
        assert row.chat_id == CHAT_ID
        assert row.payload["reason"] == "Chat not found"

    async def test_successful_send_stays_in_the_logs(
        self, session: AsyncSession
    ) -> None:
        """Поток отправок в базе не нужен — только в логах."""
        await record_bot_action("message.sent", {"chat_id": CHAT_ID})

        assert await types_of(session) == []

    async def test_client_notifies_the_sink(self) -> None:
        """Клиент зовёт наблюдателя, не зная, что тот делает."""
        from vkteams_client import VKTeams

        seen: list[tuple[str, dict]] = []
        client = VKTeams("token")
        client.event_sink = lambda event_type, fields: seen.append((event_type, fields))  # type: ignore[assignment]

        await client.notify("message.sent", chat_id=CHAT_ID)

        assert seen == [("message.sent", {"chat_id": CHAT_ID})]

    async def test_sink_error_does_not_escape(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Журнал событий — не причина не доставить сообщение."""
        from vkteams_client import VKTeams

        async def broken(event_type: str, fields: dict) -> None:
            msg = "боом"
            raise RuntimeError(msg)

        client = VKTeams("token")
        client.event_sink = broken

        with caplog.at_level("ERROR", logger="vkteams_client"):
            await client.notify("message.sent", chat_id=CHAT_ID)

        assert "event_sink.failed" in caplog.text

    async def test_no_sink_is_fine(self) -> None:
        from vkteams_client import VKTeams

        await VKTeams("token").notify("message.sent", chat_id=CHAT_ID)


class TestPanelSource:
    """Панель: ``source=panel`` и актор — вошедший пользователь."""

    async def test_webhook_created_from_panel(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        superuser: ChatUser,
        chat: Chat,
    ) -> None:
        response = await client.post(
            "/api/webhooks",
            json={"name": "Хук", "chat_id": chat.id},
            headers=auth_headers(superuser.id),
        )

        assert response.status_code == 200
        (row,) = await EventRepository(session).list()
        assert row.type == "webhook.created"
        assert row.source is EventSource.PANEL
        assert row.actor_id == superuser.id
        assert row.chat_id == chat.id

    async def test_setting_change_keeps_the_old_value(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
        superuser: ChatUser,
    ) -> None:
        await client.put(
            "/api/bot-settings/start_message",
            json={"value": "Первое"},
            headers=auth_headers(superuser.id),
        )
        await client.put(
            "/api/bot-settings/start_message",
            json={"value": "Второе"},
            headers=auth_headers(superuser.id),
        )

        rows = await EventRepository(session).list()
        assert [row.type for row in rows] == ["settings.changed", "settings.changed"]
        assert rows[1].payload["old_value"] == "Первое"

    async def test_login_is_recorded(
        self,
        client: httpx.AsyncClient,
        session: AsyncSession,
    ) -> None:
        from vkt_bot.core.repositories.login_token import LoginTokenRepository

        user = await create_chat_user(session, "panel@example.com")
        token = await LoginTokenRepository(session).create_token(
            user.id, expires_minutes=5
        )
        await session.commit()

        response = await client.post("/api/auth/login", json={"token": token.token})

        assert response.status_code == 200
        types = await types_of(session)
        assert "auth.login_succeeded" in types
