"""Middleware, создающее чат при первом событии."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
from vkteams_client.enums import ChatType

from vkt_bot.core.handlers.chats import CreateChatMiddleware
from vkt_bot.core.models import Chat
from vkt_bot.core.repositories.chat import ChatRepository

from tests.conftest import table_count
from tests.factories import create_chat, make_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


@pytest.fixture
def middleware() -> CreateChatMiddleware:
    """Middleware."""
    return CreateChatMiddleware()


class TestCreateChatMiddleware:
    """``CreateChatMiddleware.on_event``."""

    async def test_creates_chat_on_first_message(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await middleware.on_event(make_event("new_message"))

        chat = await ChatRepository(session).get("681869378@chat.agent")
        assert chat.type is ChatType.GROUP

    async def test_stores_private_chat_type(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await middleware.on_event(make_event("new_message_private"))

        chat = await ChatRepository(session).get("1234567890")
        assert chat.type is ChatType.PRIVATE

    async def test_existing_chat_is_not_duplicated(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await create_chat(session, "681869378@chat.agent")

        await middleware.on_event(make_event("new_message"))

        assert await table_count(session, Chat) == 1

    async def test_logs_first_event(
        self,
        middleware: CreateChatMiddleware,
        session_factory: object,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level("INFO", logger="vkt_bot"):
            await middleware.on_event(make_event("new_message"))

        assert "Created chat in database" in caplog.text

    @pytest.mark.parametrize(
        "fixture",
        ["callback_query", "new_chat_members", "deleted_message", "edited_message"],
    )
    async def test_other_events_are_ignored(
        self,
        fixture: str,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await middleware.on_event(make_event(fixture))
        assert await table_count(session, Chat) == 0

    async def test_two_events_from_the_same_chat(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await middleware.on_event(make_event("new_message"))
        await middleware.on_event(make_event("new_message", text="ещё"))

        assert await table_count(session, Chat) == 1

    async def test_different_chats_are_both_created(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await middleware.on_event(make_event("new_message"))
        await middleware.on_event(make_event("new_message_private"))

        assert await table_count(session, Chat) == 2
