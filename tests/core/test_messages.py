"""История сообщений: запись, правки, удаления и чистка."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest

from vkt_bot.core.constants import MESSAGES_HISTORY_SETTING
from vkt_bot.core.handlers.chats import CreateChatMiddleware
from vkt_bot.core.handlers.messages import MessageDeletedHandler, MessageEditedHandler
from vkt_bot.core.messages import (
    ATTACHMENT_PLACEHOLDER,
    history_enabled,
    purge_history,
    record_outgoing,
    set_chat_history,
)
from vkt_bot.core.models.message import Message
from vkt_bot.core.repositories.bot_settings import BotSettingsRepository
from vkt_bot.core.repositories.message import MessageRepository
from vkt_bot.utils.datetime import utcnow

from tests.conftest import table_count
from tests.factories import make_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from tests.conftest import FakeBot

CHAT_ID = "681869378@chat.agent"
MSG_ID = "6752739791872001111"


@pytest.fixture
def middleware() -> CreateChatMiddleware:
    return CreateChatMiddleware()


class TestRecording:
    """Запись входящих сообщений."""

    async def test_middleware_stores_message(
        self, session: AsyncSession, middleware: CreateChatMiddleware
    ) -> None:
        await middleware.on_event(make_event("new_message"))

        message = await MessageRepository(session).get_by_msg_id(CHAT_ID, MSG_ID)
        assert message is not None
        assert message.text == "Привет!"
        assert message.user_id == "1234567890"
        assert message.is_outgoing is False

    async def test_repeated_event_does_not_duplicate(
        self, session: AsyncSession, middleware: CreateChatMiddleware
    ) -> None:
        """Повторная доставка события — обычное дело, дублей быть не должно."""
        await middleware.on_event(make_event("new_message"))
        await middleware.on_event(make_event("new_message"))

        assert await table_count(session, Message) == 1

    async def test_message_without_text_gets_placeholder(
        self, session: AsyncSession, middleware: CreateChatMiddleware
    ) -> None:
        """Файлы и стикеры приходят без текста — на их месте заглушка."""
        await middleware.on_event(make_event("new_message", text=None))

        message = await MessageRepository(session).get_by_msg_id(CHAT_ID, MSG_ID)
        assert message is not None
        assert message.text == ATTACHMENT_PLACEHOLDER

    async def test_unknown_author_is_still_recorded(
        self, session: AsyncSession, middleware: CreateChatMiddleware
    ) -> None:
        """Автора может не быть в ``chat_users``: внешнего ключа тут нет."""
        await middleware.on_event(make_event("new_message"))

        message = await MessageRepository(session).get_by_msg_id(CHAT_ID, MSG_ID)
        assert message is not None
        assert message.user_id == "1234567890"

    async def test_disabled_history_records_nothing(
        self, session: AsyncSession, middleware: CreateChatMiddleware
    ) -> None:
        await BotSettingsRepository(session).set_value(MESSAGES_HISTORY_SETTING, "off")
        await session.commit()

        await middleware.on_event(make_event("new_message"))

        assert await table_count(session, Message) == 0

    async def test_disabled_for_chat_only(
        self, session: AsyncSession, middleware: CreateChatMiddleware
    ) -> None:
        """``/history off`` гасит один чат, не трогая остальные."""
        await set_chat_history(session, CHAT_ID, enabled=False)
        await session.commit()

        await middleware.on_event(make_event("new_message"))
        await middleware.on_event(
            make_event("new_message", chat={"chatId": "other@chat.agent"})
        )

        assert await table_count(session, Message) == 1
        assert await history_enabled(session, CHAT_ID) is False
        assert await history_enabled(session, "other@chat.agent") is True


class TestOutgoing:
    """Свои сообщения бота."""

    async def test_recorded(
        self, session: AsyncSession, session_factory: object
    ) -> None:
        """В поток событий они не возвращаются — пишем их сами."""
        await record_outgoing(CHAT_ID, "out-1", "Ответ бота")

        message = await MessageRepository(session).get_by_msg_id(CHAT_ID, "out-1")
        assert message is not None
        assert message.is_outgoing is True

    async def test_skipped_when_history_disabled(
        self, session: AsyncSession, session_factory: object
    ) -> None:
        await BotSettingsRepository(session).set_value(MESSAGES_HISTORY_SETTING, "no")
        await session.commit()

        await record_outgoing(CHAT_ID, "out-2", "Ответ бота")

        assert await MessageRepository(session).get_by_msg_id(CHAT_ID, "out-2") is None


class TestEditAndDelete:
    """Правки и удаления."""

    async def test_edit_updates_text(
        self,
        session: AsyncSession,
        middleware: CreateChatMiddleware,
        fake_bot: FakeBot,
    ) -> None:
        await middleware.on_event(make_event("new_message"))

        await MessageEditedHandler.callback(fake_bot, make_event("edited_message"))

        message = await MessageRepository(session).get_by_msg_id(CHAT_ID, MSG_ID)
        assert message is not None
        assert message.text == "Привет! (исправлено)"
        assert message.edited_at is not None

    async def test_delete_marks_row(
        self,
        session: AsyncSession,
        middleware: CreateChatMiddleware,
        fake_bot: FakeBot,
    ) -> None:
        """Строка остаётся, но агенту она больше не достанется."""
        await middleware.on_event(make_event("new_message"))

        await MessageDeletedHandler.callback(fake_bot, make_event("deleted_message"))

        message = await MessageRepository(session).get_by_msg_id(CHAT_ID, MSG_ID)
        assert message is not None
        assert message.deleted_at is not None
        assert await MessageRepository(session).recent(CHAT_ID) == []

    async def test_delete_of_unknown_message_is_harmless(
        self, fake_bot: FakeBot, session_factory: object
    ) -> None:
        """До внедрения истории сообщений нет — удалять нечего."""
        await MessageDeletedHandler.callback(fake_bot, make_event("deleted_message"))


class TestQueries:
    """Выборки."""

    @pytest.fixture(autouse=True)
    async def _messages(self, session: AsyncSession) -> None:
        repository = MessageRepository(session)
        base = utcnow() - datetime.timedelta(hours=5)
        for index, text in enumerate(["первое", "второе", "третье"]):
            await repository.record(
                CHAT_ID,
                f"m{index}",
                text=text,
                ts=base + datetime.timedelta(minutes=index),
            )
        await session.commit()

    async def test_recent_is_chronological(self, session: AsyncSession) -> None:
        rows = await MessageRepository(session).recent(CHAT_ID, limit=10)
        assert [row.text for row in rows] == ["первое", "второе", "третье"]

    async def test_recent_limit_keeps_the_latest(self, session: AsyncSession) -> None:
        rows = await MessageRepository(session).recent(CHAT_ID, limit=2)
        assert [row.text for row in rows] == ["второе", "третье"]

    async def test_in_range(self, session: AsyncSession) -> None:
        after = utcnow() - datetime.timedelta(hours=4)
        assert await MessageRepository(session).in_range(CHAT_ID, after=after) == []

    async def test_search_ascii(self, session: AsyncSession) -> None:
        """По кириллице ``ilike`` честно работает только на PostgreSQL."""
        await MessageRepository(session).record(CHAT_ID, "m9", text="deploy failed")
        await session.commit()

        rows = await MessageRepository(session).search(CHAT_ID, "DEPLOY")
        assert [row.text for row in rows] == ["deploy failed"]

    @pytest.mark.postgres
    async def test_search_cyrillic(
        self, session: AsyncSession, is_postgres: bool
    ) -> None:
        if not is_postgres:
            pytest.skip("SQLite не приводит регистр кириллицы в LIKE")
        rows = await MessageRepository(session).search(CHAT_ID, "ПЕРВОЕ")
        assert [row.text for row in rows] == ["первое"]


class TestPurge:
    """Чистка."""

    async def test_removes_old(self, session: AsyncSession) -> None:
        repository = MessageRepository(session)
        await repository.record(
            CHAT_ID, "old", text="старое", ts=utcnow() - datetime.timedelta(days=100)
        )
        await repository.record(CHAT_ID, "new", text="свежее")
        await session.commit()

        removed = await purge_history(session, days=30, max_per_chat=0)

        assert removed == 1
        assert [row.text for row in await repository.recent(CHAT_ID)] == ["свежее"]

    async def test_zero_days_disables_purge(self, session: AsyncSession) -> None:
        repository = MessageRepository(session)
        await repository.record(
            CHAT_ID, "old", text="старое", ts=utcnow() - datetime.timedelta(days=999)
        )
        await session.commit()

        assert await purge_history(session, days=0, max_per_chat=0) == 0

    async def test_chat_limit(self, session: AsyncSession) -> None:
        """Потолок на чат: болтливый чат не должен обогнать срок хранения."""
        repository = MessageRepository(session)
        base = utcnow() - datetime.timedelta(hours=1)
        for index in range(5):
            await repository.record(
                CHAT_ID,
                f"m{index}",
                text=str(index),
                ts=base + datetime.timedelta(minutes=index),
            )
        await session.commit()

        removed = await purge_history(session, days=0, max_per_chat=2)

        assert removed == 3
        assert [row.text for row in await repository.recent(CHAT_ID)] == ["3", "4"]

    async def test_other_chats_are_untouched(self, session: AsyncSession) -> None:
        repository = MessageRepository(session)
        await repository.record(CHAT_ID, "a", text="a")
        await repository.record("other@chat.agent", "b", text="b")
        await session.commit()

        await purge_history(session, days=0, max_per_chat=1)

        assert len(await repository.recent("other@chat.agent")) == 1
