"""Инструменты агента и их права.

Главный здесь — ``chat_messages``: агент доступен всем участникам, и
ошибка в проверке членства означает утечку чужой переписки.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from vkteams_client.enums import ChatType
from vkteams_client.types import GroupChatInfo, PrivateChatInfo

from vkt_agent import AgentActor, AgentDeps
from vkt_bot.core.constants import MESSAGES_HISTORY_SETTING
from vkt_bot.core.repositories.bot_settings import BotSettingsRepository
from vkt_bot.core.repositories.chat import ChatMembershipRepository
from vkt_bot.core.repositories.message import MessageRepository
from vkt_bot.utils.datetime import utcnow
from vkt_ai.tools import chats as chat_tools
from vkt_ai.tools import events as event_tools
from vkt_ai.tools import messages as message_tools
from vkt_ai.tools import profiles as profile_tools
from vkt_ai.tools import roles as role_tools

from tests.factories import assign_role, create_chat, create_chat_user, create_role

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from tests.conftest import FakeBot

MY_CHAT = "111@chat.agent"
FOREIGN_CHAT = "222@chat.agent"
THREAD = "333@chat.agent"


class Ctx:
    """Минимальный ``RunContext``: инструментам нужен только ``deps``."""

    def __init__(self, deps: AgentDeps) -> None:
        self.deps = deps


def ctx(
    session: AsyncSession,
    *,
    chat_id: str = MY_CHAT,
    user_id: str = "member@example.com",
    is_admin: bool = False,
    chat_is_thread: bool = False,
    bot: Any = None,
) -> Any:
    return Ctx(
        AgentDeps(
            session=session,
            actor=AgentActor(
                user_id=user_id, display_name="Участник", is_admin=is_admin
            ),
            chat_id=chat_id,
            chat_is_thread=chat_is_thread,
            bot=bot,
        )
    )


@pytest.fixture
async def world(session: AsyncSession) -> None:
    """Два чата, участник своего и посторонний."""
    await create_chat(session, MY_CHAT, title="Поддержка")
    await create_chat(session, FOREIGN_CHAT, title="Дирекция")
    await create_chat_user(session, "member@example.com", first_name="Иван")
    await create_chat_user(session, "boss@example.com", first_name="Босс")
    memberships = ChatMembershipRepository(session)
    await memberships.add(MY_CHAT, "member@example.com")
    await memberships.add(FOREIGN_CHAT, "boss@example.com")

    messages = MessageRepository(session)
    await messages.record(MY_CHAT, "m1", user_id="member@example.com", text="свои дела")
    await messages.record(
        FOREIGN_CHAT, "f1", user_id="boss@example.com", text="секретное совещание"
    )
    await messages.record(THREAD, "t1", user_id="member@example.com", text="в треде")
    await session.commit()


@pytest.mark.usefixtures("world")
class TestChatMessages:
    """``chat_messages`` — единственный инструмент с риском утечки."""

    async def test_member_reads_own_chat(self, session: AsyncSession) -> None:
        answer = await message_tools.chat_messages(ctx(session), chat_id=MY_CHAT)
        assert "свои дела" in answer

    async def test_outsider_is_refused(self, session: AsyncSession) -> None:
        """Посторонний не должен прочитать чужой чат через бота."""
        answer = await message_tools.chat_messages(ctx(session), chat_id=FOREIGN_CHAT)

        assert "Нет доступа" in answer
        assert "секретное совещание" not in answer

    async def test_admin_reads_any_chat(self, session: AsyncSession) -> None:
        answer = await message_tools.chat_messages(
            ctx(session, is_admin=True), chat_id=FOREIGN_CHAT
        )
        assert "секретное совещание" in answer

    async def test_deleted_messages_never_returned(self, session: AsyncSession) -> None:
        """Человек убрал сообщение — бот не должен быть способом его прочитать."""
        await MessageRepository(session).mark_deleted(MY_CHAT, "m1")
        await session.commit()

        answer = await message_tools.chat_messages(ctx(session), chat_id=MY_CHAT)

        assert "свои дела" not in answer

    async def test_thread_scope_is_closed(self, session: AsyncSession) -> None:
        """В обсуждении состав проверять нечем — значит, только сам тред."""
        answer = await message_tools.chat_messages(
            ctx(session, chat_id=THREAD, chat_is_thread=True), chat_id=MY_CHAT
        )

        assert "свои дела" not in answer
        assert "обсуждени" in answer

    async def test_thread_reads_itself(self, session: AsyncSession) -> None:
        answer = await message_tools.chat_messages(
            ctx(session, chat_id=THREAD, chat_is_thread=True)
        )
        assert "в треде" in answer

    async def test_history_switched_off(self, session: AsyncSession) -> None:
        await BotSettingsRepository(session).set_value(MESSAGES_HISTORY_SETTING, "off")
        await session.commit()

        answer = await message_tools.chat_messages(ctx(session), chat_id=MY_CHAT)

        assert "выключена" in answer

    async def test_search(self, session: AsyncSession) -> None:
        await MessageRepository(session).record(MY_CHAT, "m2", text="deploy failed")
        await session.commit()

        answer = await message_tools.chat_messages(ctx(session), query="deploy")

        assert "deploy failed" in answer
        assert "свои дела" not in answer

    async def test_bot_messages_are_marked(self, session: AsyncSession) -> None:
        await MessageRepository(session).record(
            MY_CHAT, "b1", text="я бот", is_outgoing=True
        )
        await session.commit()

        answer = await message_tools.chat_messages(ctx(session))

        assert "бот: я бот" in answer


@pytest.mark.usefixtures("world")
class TestChats:
    """``find_chats`` и ``chat_members``."""

    async def test_member_sees_only_own_chats(self, session: AsyncSession) -> None:
        answer = await chat_tools.find_chats(ctx(session))

        assert "Поддержка" in answer
        assert "Дирекция" not in answer

    async def test_admin_sees_everything(self, session: AsyncSession) -> None:
        answer = await chat_tools.find_chats(ctx(session, is_admin=True))

        assert "Дирекция" in answer

    async def test_search_by_title(self, session: AsyncSession) -> None:
        answer = await chat_tools.find_chats(ctx(session, is_admin=True), query="Дирек")

        assert "Дирекция" in answer
        assert "Поддержка" not in answer

    async def test_members_of_own_chat(self, session: AsyncSession) -> None:
        answer = await chat_tools.chat_members(ctx(session), chat_id=MY_CHAT)

        assert "Иван" in answer

    async def test_members_without_chat_id_means_current(
        self, session: AsyncSession
    ) -> None:
        """Модель передаёт пустую строку, когда чат в вопросе не назван."""
        answer = await chat_tools.chat_members(ctx(session), chat_id="")

        assert "Иван" in answer

    async def test_empty_roster_does_not_claim_a_thread(
        self, session: AsyncSession
    ) -> None:
        """Пустой ростер — это «не знаю», а не «это обсуждение»."""
        answer = await chat_tools.chat_members(
            ctx(session, is_admin=True), chat_id="empty@chat.agent"
        )

        assert "не знаю" in answer

    async def test_admin_empty_chat_id_still_means_current(
        self, session: AsyncSession
    ) -> None:
        """У админа проверка прав пропускает что угодно — включая пустую
        строку. Резолвить её надо до проверки, иначе он получал бы
        «состав неизвестен» на собственный чат."""
        answer = await chat_tools.chat_members(ctx(session, is_admin=True), chat_id="")

        assert "Иван" in answer

    async def test_members_of_foreign_chat_refused(self, session: AsyncSession) -> None:
        answer = await chat_tools.chat_members(ctx(session), chat_id=FOREIGN_CHAT)

        assert "Нет доступа" in answer
        assert "Босс" not in answer


@pytest.mark.usefixtures("world")
class TestProfiles:
    """``chat_info`` и ``user_info``."""

    async def test_chat_info_of_own_chat(self, session: AsyncSession) -> None:
        answer = await profile_tools.chat_info(ctx(session), chat_id=MY_CHAT)

        assert "Поддержка" in answer
        assert "группа" in answer

    async def test_chat_info_without_id_means_current(
        self, session: AsyncSession
    ) -> None:
        answer = await profile_tools.chat_info(ctx(session), chat_id="")

        assert "Поддержка" in answer

    async def test_chat_info_of_foreign_chat_refused(
        self, session: AsyncSession
    ) -> None:
        answer = await profile_tools.chat_info(ctx(session), chat_id=FOREIGN_CHAT)

        assert "Нет доступа" in answer
        assert "Дирекция" not in answer

    async def test_chat_info_in_thread_stays_in_thread(
        self, session: AsyncSession
    ) -> None:
        """Состав обсуждения не узнать, значит и выходить из него нельзя."""
        answer = await profile_tools.chat_info(
            ctx(session, chat_id=THREAD, chat_is_thread=True), chat_id=MY_CHAT
        )

        assert "обсуждени" in answer
        assert "Поддержка" not in answer

    async def test_chat_info_says_when_api_was_not_asked(
        self, session: AsyncSession
    ) -> None:
        """Пустое описание — это «не спрашивали», а не «описания нет»."""
        answer = await profile_tools.chat_info(ctx(session), chat_id=MY_CHAT)

        assert "ещё не спрашивали" in answer

    async def test_chat_info_shows_description_and_rules(
        self, session: AsyncSession
    ) -> None:
        await create_chat(
            session,
            "d@chat.agent",
            title="Дежурство",
            about="Кто на смене",
            rules="Отвечать за 15 минут",
            invite_link="https://icq.com/chat/AoLFkoRCn4MpaP0DjUI",
            public=False,
            info_updated_at=utcnow(),
        )
        await session.commit()

        answer = await profile_tools.chat_info(
            ctx(session, is_admin=True), chat_id="d@chat.agent"
        )

        assert "Кто на смене" in answer
        assert "Отвечать за 15 минут" in answer
        assert "Закрытый" in answer
        assert "https://icq.com/chat/AoLFkoRCn4MpaP0DjUI" in answer

    async def test_unknown_chat_explains_why(self, session: AsyncSession) -> None:
        answer = await profile_tools.chat_info(
            ctx(session, is_admin=True), chat_id="nobody@chat.agent"
        )

        assert "не знаю" in answer

    async def test_user_info(self, session: AsyncSession) -> None:
        await create_chat_user(
            session,
            "ivan@example.com",
            first_name="Иван",
            last_name="Иванов",
            nick="ivan",
            about="Архитектор",
            info_updated_at=utcnow(),
        )
        await session.commit()

        answer = await profile_tools.user_info(ctx(session), user_id="ivan@example.com")

        assert "Иван Иванов" in answer
        assert "ivan" in answer
        assert "Архитектор" in answer
        assert "Это человек." in answer

    async def test_user_info_lists_roles(self, session: AsyncSession) -> None:
        role = await create_role(session, "дежурный")
        await assign_role(session, "member@example.com", role.id)
        await session.commit()

        answer = await profile_tools.user_info(
            ctx(session), user_id="member@example.com"
        )

        assert "дежурный" in answer

    async def test_user_info_without_id_means_asker(
        self, session: AsyncSession
    ) -> None:
        answer = await profile_tools.user_info(ctx(session), user_id="")

        assert "Иван" in answer

    async def test_user_info_marks_bots(self, session: AsyncSession) -> None:
        await create_chat_user(
            session, "bot@bot", first_name="Бот", is_bot=True, info_updated_at=utcnow()
        )
        await session.commit()

        answer = await profile_tools.user_info(ctx(session), user_id="bot@bot")

        assert "Это бот." in answer

    async def test_unknown_user_explains_why(self, session: AsyncSession) -> None:
        answer = await profile_tools.user_info(
            ctx(session), user_id="nobody@example.com"
        )

        assert "не знаю" in answer

    async def test_stale_chat_is_refreshed(
        self, session: AsyncSession, fake_bot: FakeBot
    ) -> None:
        """Данные устарели — инструмент сам сходит в API."""
        fake_bot.results["get_chat_info"] = GroupChatInfo(
            ok=True, type=ChatType.GROUP, title="Поддержка", about="Первая линия"
        )

        answer = await profile_tools.chat_info(
            ctx(session, bot=fake_bot), chat_id=MY_CHAT
        )

        assert fake_bot.calls_of("get_chat_info")
        assert "Первая линия" in answer

    async def test_fresh_chat_is_not_refreshed(
        self, session: AsyncSession, fake_bot: FakeBot
    ) -> None:
        await create_chat(
            session, "f@chat.agent", title="Свежий", info_updated_at=utcnow()
        )
        await session.commit()

        await profile_tools.chat_info(
            ctx(session, is_admin=True, bot=fake_bot), chat_id="f@chat.agent"
        )

        assert fake_bot.calls_of("get_chat_info") == []

    async def test_stale_user_is_refreshed(
        self, session: AsyncSession, fake_bot: FakeBot
    ) -> None:
        fake_bot.results["get_chat_info"] = PrivateChatInfo(
            ok=True, type=ChatType.PRIVATE, firstName="Иван", about="Архитектор"
        )

        answer = await profile_tools.user_info(
            ctx(session, bot=fake_bot), user_id="member@example.com"
        )

        assert fake_bot.calls_of("get_chat_info")
        assert "Архитектор" in answer


@pytest.mark.usefixtures("world")
class TestRoles:
    """Роли доступны всем: они не про содержимое чатов."""

    async def test_user_roles(self, session: AsyncSession) -> None:
        role = await create_role(session, "дежурный")
        await assign_role(session, "member@example.com", role.id)

        answer = await role_tools.user_roles(ctx(session), user_id="member@example.com")

        assert "дежурный" in answer

    async def test_user_without_roles(self, session: AsyncSession) -> None:
        answer = await role_tools.user_roles(ctx(session), user_id="boss@example.com")

        assert "ролей нет" in answer

    async def test_role_members(self, session: AsyncSession) -> None:
        role = await create_role(session, "дежурный")
        await assign_role(session, "member@example.com", role.id)

        answer = await role_tools.role_members(ctx(session), role="#дежурный")

        assert "Иван" in answer

    async def test_unknown_role(self, session: AsyncSession) -> None:
        answer = await role_tools.role_members(ctx(session), role="нетакой")

        assert "не существует" in answer


@pytest.mark.usefixtures("world")
class TestEvents:
    """``recent_events`` — журнал, а не переписка."""

    async def test_texts_are_stripped(self, session: AsyncSession) -> None:
        """Тексты сообщений в ленту не попадают — как и в панели."""
        from vkt_bot.core.events import EventType, emit

        await emit(
            session,
            EventType.MESSAGE_SEND_FAILED,
            chat_id=MY_CHAT,
            payload={"reason": "лимит", "text": "секрет в тексте"},
        )
        await session.commit()

        answer = await event_tools.recent_events(ctx(session), chat_id=MY_CHAT)

        assert "лимит" in answer
        assert "секрет в тексте" not in answer

    async def test_foreign_chat_refused(self, session: AsyncSession) -> None:
        answer = await event_tools.recent_events(ctx(session), chat_id=FOREIGN_CHAT)

        assert "Нет доступа" in answer

    async def test_empty_chat(self, session: AsyncSession) -> None:
        answer = await event_tools.recent_events(ctx(session), chat_id=MY_CHAT)

        assert "не записано" in answer
