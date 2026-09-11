"""Обогащение чатов и участников (``vkt_bot.core.chatinfo``)."""

from __future__ import annotations

import datetime
import logging
from typing import TYPE_CHECKING

import pytest

from vkteams_client.enums import ChatType
from vkteams_client.types import (
    ChatPhoto,
    GroupChatInfo,
    PrivateChatInfo,
    UnknownChatInfo,
)

from vkt_bot.core import chatinfo
from vkt_bot.core.repositories.chat import ChatRepository
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.utils.datetime import utcnow

from tests.factories import create_chat, create_chat_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from tests.conftest import FakeBot

CHAT_ID = "694348323@chat.agent"
THREAD_ID = "693938330@chat.agent"
USER_ID = "1234567890"
AVATAR = "https://rapi.icq.net/avatar/get?targetSn=1234567890&size=1024"


def private(**overrides: object) -> PrivateChatInfo:
    """Ответ ``chats/getInfo`` про человека."""
    fields: dict[str, object] = {
        "ok": True,
        "type": ChatType.PRIVATE,
        "firstName": "Иван",
        "lastName": "Иванов",
        "nick": "ivan",
        "about": "Архитектор",
        "photo": [ChatPhoto(url=AVATAR)],
    }
    fields.update(overrides)
    return PrivateChatInfo(**fields)  # type: ignore[arg-type]


def group(**overrides: object) -> GroupChatInfo:
    """Ответ ``chats/getInfo`` про группу."""
    fields: dict[str, object] = {
        "ok": True,
        "type": ChatType.GROUP,
        "title": "Тест группа",
        "about": "Описание",
        "rules": "Правила",
        "inviteLink": "https://icq.com/chat/AoLLi9QjQqY9G2FMXzA",
        "public": False,
        "joinModeration": False,
    }
    fields.update(overrides)
    return GroupChatInfo(**fields)  # type: ignore[arg-type]


class TestIsStale:
    """``is_stale``."""

    def test_never_asked(self) -> None:
        assert chatinfo.is_stale(None) is True

    def test_fresh(self) -> None:
        assert chatinfo.is_stale(utcnow()) is False

    def test_expired(self) -> None:
        old = utcnow() - chatinfo.INFO_TTL - datetime.timedelta(minutes=1)
        assert chatinfo.is_stale(old) is True

    def test_aware_time_does_not_raise(self) -> None:
        """В базе время наивное, но сравнивать могут и с осведомлённым."""
        aware = datetime.datetime.now(datetime.UTC)
        assert chatinfo.is_stale(aware) is False


class TestEnrichMembers:
    """``enrich_members``."""

    async def test_fills_profile(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Участник из ростера перестаёт быть безымянным id."""
        await create_chat_user(session, USER_ID)
        fake_bot.results["get_chat_info"] = private()

        await chatinfo.enrich_members(fake_bot, [USER_ID])  # type: ignore[arg-type]

        user = await ChatUserRepository(session).get(USER_ID)
        assert user.display_name == "Иван Иванов"
        assert user.nick == "ivan"
        assert user.about == "Архитектор"
        assert user.photo_url == AVATAR
        assert user.info_updated_at is not None

    async def test_empty_does_not_erase_known(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Правило то же, что у имён из событий."""
        await create_chat_user(session, USER_ID, first_name="Пётр", photo_url=AVATAR)
        fake_bot.results["get_chat_info"] = private(
            firstName=None, lastName=None, nick=None, about=None, photo=[]
        )

        await chatinfo.enrich_members(fake_bot, [USER_ID])  # type: ignore[arg-type]

        user = await ChatUserRepository(session).get(USER_ID)
        assert user.first_name == "Пётр"
        # Аватар не снимаем: «сняли» от «не было» не отличить.
        assert user.photo_url == AVATAR

    async def test_bot_flag_is_set_but_never_cleared(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """``isBot`` у человека не приходит вовсе."""
        await create_chat_user(session, USER_ID)
        fake_bot.results["get_chat_info"] = private(isBot=True)

        await chatinfo.enrich_members(fake_bot, [USER_ID])  # type: ignore[arg-type]
        user = await ChatUserRepository(session).get(USER_ID)
        assert user.is_bot is True

        # Без этого второй заход упёрся бы в TTL, ответ без ``isBot`` не
        # применился бы, и тест проверял бы сам себя.
        user.info_updated_at = utcnow() - chatinfo.INFO_TTL - datetime.timedelta(days=1)
        session.add(user)
        await session.commit()

        fake_bot.results["get_chat_info"] = private()
        await chatinfo.enrich_members(fake_bot, [USER_ID])  # type: ignore[arg-type]

        assert len(fake_bot.calls_of("get_chat_info")) == 2
        assert (await ChatUserRepository(session).get(USER_ID)).is_bot is True

    async def test_ttl_holds_back_the_second_call(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await create_chat_user(session, USER_ID)
        fake_bot.results["get_chat_info"] = private()

        await chatinfo.enrich_members(fake_bot, [USER_ID])  # type: ignore[arg-type]
        await chatinfo.enrich_members(fake_bot, [USER_ID])  # type: ignore[arg-type]

        assert len(fake_bot.calls_of("get_chat_info")) == 1

    async def test_refusal_is_remembered(
        self, fake_bot: FakeBot, session: AsyncSession, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Отказ — негативный кэш: второй раз не спрашиваем."""
        await create_chat_user(session, USER_ID)
        fake_bot.results["get_chat_info"] = UnknownChatInfo(
            ok=False, description="Invalid chatId"
        )

        with caplog.at_level(logging.WARNING, logger="vkt_bot"):
            await chatinfo.enrich_members(fake_bot, [USER_ID])  # type: ignore[arg-type]
        await chatinfo.enrich_members(fake_bot, [USER_ID])  # type: ignore[arg-type]

        assert "chatinfo.refused" in caplog.text
        assert len(fake_bot.calls_of("get_chat_info")) == 1
        assert (await ChatUserRepository(session).get(USER_ID)).info_updated_at

    async def test_network_error_is_not_remembered(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Сбой запроса — про нас, а не про участника: повторим позже."""
        await create_chat_user(session, USER_ID)
        fake_bot.errors["get_chat_info"] = RuntimeError("API упал")

        await chatinfo.enrich_members(fake_bot, [USER_ID])  # type: ignore[arg-type]

        user = await ChatUserRepository(session).get(USER_ID)
        assert user.info_updated_at is None
        assert user.first_name is None

    async def test_unknown_user_is_not_created(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Кто попадает в базу — решают хендлеры."""
        fake_bot.results["get_chat_info"] = private()

        await chatinfo.enrich_members(fake_bot, [USER_ID])  # type: ignore[arg-type]

        assert await ChatUserRepository(session).get_or_none(USER_ID) is None
        assert fake_bot.calls_of("get_chat_info") == []

    async def test_batch_is_capped(
        self,
        fake_bot: FakeBot,
        session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Ростер бывает большой — за заход берём не больше потолка."""
        monkeypatch.setattr(chatinfo, "MAX_BATCH", 3)
        ids = [f"user-{index}" for index in range(6)]
        for user_id in ids:
            await create_chat_user(session, user_id)
        fake_bot.results["get_chat_info"] = private()

        asked = await chatinfo.enrich_members(fake_bot, ids)  # type: ignore[arg-type]

        assert asked == 3
        assert len(fake_bot.calls_of("get_chat_info")) == 3


class TestEnrichChat:
    """``enrich_chat``."""

    async def test_fills_group(self, fake_bot: FakeBot, session: AsyncSession) -> None:
        await create_chat(session, CHAT_ID)
        fake_bot.results["get_chat_info"] = group()

        await chatinfo.enrich_chat(fake_bot, CHAT_ID)  # type: ignore[arg-type]

        chat = await ChatRepository(session).get(CHAT_ID)
        assert chat.title == "Тест группа"
        assert chat.about == "Описание"
        assert chat.rules == "Правила"
        assert chat.invite_link == "https://icq.com/chat/AoLLi9QjQqY9G2FMXzA"
        assert chat.public is False
        assert chat.join_moderation is False

    async def test_false_flag_overwrites_true(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Чат закрыли — панель не должна показывать «публичный»."""
        await create_chat(session, CHAT_ID, public=True)
        fake_bot.results["get_chat_info"] = group(public=False)

        await chatinfo.enrich_chat(fake_bot, CHAT_ID)  # type: ignore[arg-type]

        assert (await ChatRepository(session).get(CHAT_ID)).public is False

    async def test_unknown_flag_keeps_the_old_value(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """А вот «не знаем» затирать не должно."""
        await create_chat(session, CHAT_ID, public=True)
        fake_bot.results["get_chat_info"] = group(public=None)

        await chatinfo.enrich_chat(fake_bot, CHAT_ID)  # type: ignore[arg-type]

        assert (await ChatRepository(session).get(CHAT_ID)).public is True

    async def test_ttl_and_force(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await create_chat(session, CHAT_ID)
        fake_bot.results["get_chat_info"] = group()

        await chatinfo.enrich_chat(fake_bot, CHAT_ID)  # type: ignore[arg-type]
        await chatinfo.enrich_chat(fake_bot, CHAT_ID)  # type: ignore[arg-type]
        assert len(fake_bot.calls_of("get_chat_info")) == 1

        await chatinfo.enrich_chat(fake_bot, CHAT_ID, force=True)  # type: ignore[arg-type]
        assert len(fake_bot.calls_of("get_chat_info")) == 2

    async def test_thread_refusal_is_remembered(
        self, fake_bot: FakeBot, session: AsyncSession, caplog: pytest.LogCaptureFixture
    ) -> None:
        """В обсуждении метод отказывает, и это не повод шуметь."""
        await create_chat(session, THREAD_ID)
        fake_bot.results["get_chat_info"] = UnknownChatInfo(
            ok=False, description="Bad request"
        )

        with caplog.at_level(logging.DEBUG, logger="vkt_bot"):
            await chatinfo.enrich_chat(fake_bot, THREAD_ID)  # type: ignore[arg-type]
        await chatinfo.enrich_chat(fake_bot, THREAD_ID)  # type: ignore[arg-type]

        assert "chatinfo.not_a_chat" in caplog.text
        assert "chatinfo.refused" not in caplog.text
        assert len(fake_bot.calls_of("get_chat_info")) == 1
        assert (await ChatRepository(session).get(THREAD_ID)).info_updated_at

    async def test_unknown_chat_is_not_created(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await chatinfo.enrich_chat(fake_bot, CHAT_ID)  # type: ignore[arg-type]

        assert await ChatRepository(session).get_or_none(CHAT_ID) is None
        assert fake_bot.calls_of("get_chat_info") == []

    async def test_private_chat_goes_to_the_profile(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """В личке чат и участник — одна сущность, и запрос один."""
        await create_chat(session, USER_ID, chat_type="private")
        await create_chat_user(session, USER_ID)
        fake_bot.results["get_chat_info"] = private()

        await chatinfo.enrich_chat(fake_bot, USER_ID)  # type: ignore[arg-type]

        assert len(fake_bot.calls_of("get_chat_info")) == 1
        user = await ChatUserRepository(session).get(USER_ID)
        assert user.display_name == "Иван Иванов"
        # У личного чата названия нет и быть не должно.
        assert (await ChatRepository(session).get(USER_ID)).title is None


class TestRefreshFromMessage:
    """``refresh_from_message``."""

    async def test_asks_for_chat_and_sender(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await create_chat(session, CHAT_ID)
        await create_chat_user(session, USER_ID)
        fake_bot.results["get_chat_info"] = group()

        await chatinfo.refresh_from_message(fake_bot, CHAT_ID, USER_ID)  # type: ignore[arg-type]

        asked = {call.kwargs["chat_id"] for call in fake_bot.calls_of("get_chat_info")}
        assert asked == {CHAT_ID, USER_ID}

    async def test_second_message_costs_nothing(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await create_chat(session, CHAT_ID)
        await create_chat_user(session, USER_ID)
        fake_bot.results["get_chat_info"] = group()

        await chatinfo.refresh_from_message(fake_bot, CHAT_ID, USER_ID)  # type: ignore[arg-type]
        await chatinfo.refresh_from_message(fake_bot, CHAT_ID, USER_ID)  # type: ignore[arg-type]

        assert len(fake_bot.calls_of("get_chat_info")) == 2

    async def test_private_chat_asks_once(
        self, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """В личке чат и отправитель — одна сущность, запрос не двоится."""
        await create_chat(session, USER_ID, chat_type="private")
        await create_chat_user(session, USER_ID)
        fake_bot.results["get_chat_info"] = private()

        await chatinfo.refresh_from_message(fake_bot, USER_ID, USER_ID)  # type: ignore[arg-type]

        assert len(fake_bot.calls_of("get_chat_info")) == 1
