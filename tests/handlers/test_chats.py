"""Регистрация чатов и их состава."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from vkteams_client.enums import ChatType
from vkteams_client.types import ChatMember, GetMembersResponse, Response

from vkt_bot.core.handlers.chats import (
    ChatInfoChangedHandler,
    ChatMembersJoinedHandler,
    ChatMembersLeftHandler,
    CreateChatMiddleware,
)
from vkt_bot.core.constants import THREADS_AUTOSUBSCRIBE_SETTING
from vkt_bot.core.models import Chat, ChatMembership, ChatUser
from vkt_bot.core.repositories.bot_settings import BotSettingsRepository
from vkt_bot.core.repositories.chat import ChatMembershipRepository, ChatRepository
from vkt_bot.core.repositories.user import ChatUserRepository

from tests.conftest import table_count
from tests.factories import create_chat, create_chat_user, make_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from vkt_dispatcher import Dispatcher

    from tests.conftest import FakeBot

CHAT_ID = "681869378@chat.agent"
BOT_MEMBER = {"firstName": "Тестовый", "userId": "test_bot@bot", "nick": "test_bot"}


@pytest.fixture
def middleware() -> CreateChatMiddleware:
    """Middleware."""
    return CreateChatMiddleware()


def bot_added_event(**overrides: Any) -> Any:  # noqa: ANN401
    """Событие «бота добавили в чат»."""
    overrides.setdefault("newMembers", [BOT_MEMBER])
    return make_event("new_chat_members", **overrides)


def members_response(*user_ids: str) -> GetMembersResponse:
    """Ответ ``/chats/getMembers``."""
    return GetMembersResponse(
        ok=True, members=[ChatMember(userId=uid) for uid in user_ids]
    )


class TestCreateChatMiddleware:
    """``CreateChatMiddleware.on_event``."""

    async def test_creates_chat_on_first_message(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await middleware.on_event(make_event("new_message"))

        chat = await ChatRepository(session).get(CHAT_ID)
        assert chat.type is ChatType.GROUP

    async def test_stores_private_chat_type(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await middleware.on_event(make_event("new_message_private"))

        chat = await ChatRepository(session).get("1234567890")
        assert chat.type is ChatType.PRIVATE

    async def test_stores_title(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await middleware.on_event(make_event("new_message"))

        chat = await ChatRepository(session).get(CHAT_ID)
        assert chat.title == "Тестовая группа"

    async def test_private_chat_has_no_title(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await middleware.on_event(make_event("new_message_private"))

        chat = await ChatRepository(session).get("1234567890")
        assert chat.title is None

    async def test_renamed_chat_gets_new_title(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await middleware.on_event(make_event("new_message"))
        await middleware.on_event(
            make_event("new_message", chat={"title": "Переименовали"})
        )

        chat = await ChatRepository(session).get(CHAT_ID)
        assert chat.title == "Переименовали"

    async def test_existing_chat_is_not_duplicated(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await create_chat(session, CHAT_ID)

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

    async def test_second_message_is_not_logged_as_first(
        self,
        middleware: CreateChatMiddleware,
        session_factory: object,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        await middleware.on_event(make_event("new_message"))
        with caplog.at_level("INFO", logger="vkt_bot"):
            await middleware.on_event(make_event("new_message", text="ещё"))

        assert "Created chat in database" not in caplog.text

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

    async def test_message_fills_sender_name(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        """Имя из ростера не приходит — добираем его из сообщений."""
        await create_chat_user(session, "1234567890")

        await middleware.on_event(make_event("new_message"))

        user = await ChatUserRepository(session).get("1234567890")
        assert user.display_name == "Иван Иванов"

    async def test_message_does_not_create_a_user(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        """Кто попадает в базу — решают хендлеры, а не поток сообщений."""
        await middleware.on_event(make_event("new_message"))

        assert await table_count(session, ChatUser) == 0

    async def test_message_from_bot_flags_the_sender(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await create_chat_user(session, "1011835311")

        await middleware.on_event(
            make_event(
                "new_message_from_bot",
                **{"from": {"userId": "1011835311"}},
            )
        )

        user = await ChatUserRepository(session).get("1011835311")
        assert user.is_bot

    async def test_different_chats_are_both_created(
        self,
        middleware: CreateChatMiddleware,
        session: AsyncSession,
    ) -> None:
        await middleware.on_event(make_event("new_message"))
        await middleware.on_event(make_event("new_message_private"))

        assert await table_count(session, Chat) == 2


class TestChatMembersJoined:
    """``newChatMembers``: чат и его состав попадают в базу."""

    async def test_registers_chat_when_bot_is_added(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Главный сценарий: бота добавили — чат появился без единого сообщения."""
        await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        chat = await ChatRepository(session).get(CHAT_ID)
        assert chat.type is ChatType.GROUP
        assert chat.title == "Тестовая группа"

    async def test_registers_chat_when_user_is_added(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatMembersJoinedHandler.handle(
            make_event("new_chat_members"), dispatcher
        )

        assert await ChatRepository(session).get_or_none(CHAT_ID)

    async def test_records_membership(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatMembersJoinedHandler.handle(
            make_event("new_chat_members"), dispatcher
        )

        membership = await ChatMembershipRepository(session).get_or_none_by_pair(
            CHAT_ID, "9876543210"
        )
        assert membership is not None

    async def test_creates_missing_user(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatMembersJoinedHandler.handle(
            make_event("new_chat_members"), dispatcher
        )

        assert await table_count(session, ChatUser) == 1

    async def test_known_user_becomes_flagged_when_seen_as_a_bot(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Строка могла появиться раньше — например, из ростера другого чата."""
        await create_chat_user(session, BOT_MEMBER["userId"])

        await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        assert (await ChatUserRepository(session).get(BOT_MEMBER["userId"])).is_bot

    async def test_existing_user_is_reused(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await create_chat_user(session, "9876543210")

        await ChatMembersJoinedHandler.handle(
            make_event("new_chat_members"), dispatcher
        )

        assert await table_count(session, ChatUser) == 1

    async def test_bot_is_recorded_with_a_flag(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Бот — полноценный участник, но помечен как бот."""
        await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        user = await ChatUserRepository(session).get(BOT_MEMBER["userId"])
        assert user.is_bot
        membership = await ChatMembershipRepository(session).get_or_none_by_pair(
            CHAT_ID, BOT_MEMBER["userId"]
        )
        assert membership is not None

    async def test_humans_are_not_flagged_as_bots(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatMembersJoinedHandler.handle(
            make_event("new_chat_members"), dispatcher
        )

        user = await ChatUserRepository(session).get("9876543210")
        assert not user.is_bot

    async def test_repeated_event_does_not_duplicate_membership(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        event = make_event("new_chat_members")
        await ChatMembersJoinedHandler.handle(event, dispatcher)
        await ChatMembersJoinedHandler.handle(event, dispatcher)

        assert await table_count(session, ChatMembership) == 1

    async def test_fetches_roster_when_bot_is_added(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Участники, бывшие в чате до бота, событий не порождают."""
        fake_bot.results["get_members"] = members_response("111", "222")

        await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        memberships = ChatMembershipRepository(session)
        assert await memberships.get_or_none_by_pair(CHAT_ID, "111")
        assert await memberships.get_or_none_by_pair(CHAT_ID, "222")

    async def test_bot_from_roster_is_flagged(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """``getMembers`` отдаёт голые id — бота узнаём по событию."""
        fake_bot.results["get_members"] = members_response(BOT_MEMBER["userId"], "111")

        await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        users = ChatUserRepository(session)
        assert (await users.get(BOT_MEMBER["userId"])).is_bot
        assert not (await users.get("111")).is_bot
        assert await table_count(session, ChatMembership) == 2

    async def test_stores_member_name(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatMembersJoinedHandler.handle(
            make_event("new_chat_members"), dispatcher
        )

        user = await ChatUserRepository(session).get("9876543210")
        assert (user.first_name, user.last_name) == ("Пётр", "Петров")
        assert user.display_name == "Пётр Петров"

    async def test_stores_bot_nick(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        user = await ChatUserRepository(session).get(BOT_MEMBER["userId"])
        assert user.nick == "test_bot"
        assert user.display_name == "Тестовый"

    async def test_roster_member_has_no_name_yet(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """``getMembers`` имён не отдаёт — до первого события остаётся id."""
        fake_bot.results["get_members"] = members_response("111")

        await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        user = await ChatUserRepository(session).get("111")
        assert user.first_name is None
        assert user.display_name == "111"

    async def test_roster_is_not_fetched_for_a_plain_user(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatMembersJoinedHandler.handle(
            make_event("new_chat_members"), dispatcher
        )

        assert fake_bot.calls_of("get_members") == []

    async def test_roster_failure_does_not_break_registration(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Упавший ``getMembers`` не должен лишить нас самого чата."""
        fake_bot.errors["get_members"] = RuntimeError("API упал")

        await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        assert await ChatRepository(session).get_or_none(CHAT_ID)

    async def test_roster_and_new_member_are_merged(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Один и тот же id из события и из ростера — одно членство."""
        fake_bot.results["get_members"] = members_response("9876543210", "111")

        await ChatMembersJoinedHandler.handle(
            bot_added_event(
                newMembers=[
                    BOT_MEMBER,
                    {
                        "firstName": "Пётр",
                        "lastName": "Петров",
                        "userId": "9876543210",
                    },
                ]
            ),
            dispatcher,
        )

        # бот + 9876543210 + 111, дубль id из события и ростера не удвоился
        assert await table_count(session, ChatMembership) == 3

    async def test_logs_bot_addition(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        fake_bot.results["get_members"] = members_response(BOT_MEMBER["userId"], "111")

        with caplog.at_level("INFO", logger="vkt_bot"):
            await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        assert "Bot added to chat" in caplog.text
        assert "2 member(s)" in caplog.text


class TestChatMembersLeft:
    """``leftChatMembers``: членство снимается."""

    async def test_removes_membership(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatMembersJoinedHandler.handle(
            make_event("new_chat_members"), dispatcher
        )

        await ChatMembersLeftHandler.handle(make_event("left_chat_members"), dispatcher)

        assert await table_count(session, ChatMembership) == 0

    async def test_user_row_is_kept(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Пользователь мог остаться в других чатах и в ролях."""
        await ChatMembersJoinedHandler.handle(
            make_event("new_chat_members"), dispatcher
        )

        await ChatMembersLeftHandler.handle(make_event("left_chat_members"), dispatcher)

        assert await table_count(session, ChatUser) == 1

    async def test_unknown_member_is_ignored(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatMembersLeftHandler.handle(make_event("left_chat_members"), dispatcher)

        assert await table_count(session, ChatMembership) == 0

    async def test_other_chats_are_untouched(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await create_chat(session, "other@chat.agent")
        await create_chat_user(session, "9876543210")
        await ChatMembershipRepository(session).add("other@chat.agent", "9876543210")
        await session.commit()

        await ChatMembersLeftHandler.handle(make_event("left_chat_members"), dispatcher)

        assert await table_count(session, ChatMembership) == 1

    async def test_logs_bot_removal(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        with caplog.at_level("INFO", logger="vkt_bot"):
            await ChatMembersLeftHandler.handle(
                make_event("left_chat_members", leftMembers=[BOT_MEMBER]), dispatcher
            )

        assert "Bot removed from chat" in caplog.text


class TestChatInfoChanged:
    """``changedChatInfo``: название чата обновляется."""

    async def test_updates_title(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await create_chat(session, CHAT_ID)

        await ChatInfoChangedHandler.handle(make_event("changed_chat_info"), dispatcher)

        chat = await ChatRepository(session).get(CHAT_ID)
        assert chat.title == "Новое название"

    async def test_creates_unknown_chat(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatInfoChangedHandler.handle(make_event("changed_chat_info"), dispatcher)

        chat = await ChatRepository(session).get(CHAT_ID)
        assert chat.title == "Новое название"

    async def test_empty_title_does_not_erase_the_old_one(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatInfoChangedHandler.handle(make_event("changed_chat_info"), dispatcher)

        await ChatInfoChangedHandler.handle(
            make_event("changed_chat_info", title=None, chat={"title": None}),
            dispatcher,
        )

        chat = await ChatRepository(session).get(CHAT_ID)
        assert chat.title == "Новое название"


class TestThreadAutosubscribeOnJoin:
    """Бота добавили в чат — он подписывается на обсуждения."""

    async def test_subscribes_when_bot_is_added(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        (call,) = fake_bot.calls_of("threads_autosubscribe")
        assert call.kwargs["chat_id"] == CHAT_ID
        assert call.kwargs["enable"] is True

    async def test_subscribes_to_existing_threads(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        """Бота добавили в живой чат — обсуждения там уже есть."""
        await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        (call,) = fake_bot.calls_of("threads_autosubscribe")
        assert call.kwargs["with_existing"] is True

    async def test_no_subscribe_when_only_users_joined(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await ChatMembersJoinedHandler.handle(
            make_event("new_chat_members"), dispatcher
        )

        assert fake_bot.calls_of("threads_autosubscribe") == []

    async def test_setting_can_disable_autosubscribe(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await BotSettingsRepository(session).set_value(
            THREADS_AUTOSUBSCRIBE_SETTING, "false"
        )
        await session.commit()

        await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        assert fake_bot.calls_of("threads_autosubscribe") == []

    async def test_api_error_does_not_break_registration(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        fake_bot.errors["threads_autosubscribe"] = RuntimeError("нет связи")

        await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        assert await ChatRepository(session).get_or_none(CHAT_ID) is not None

    async def test_refusal_is_logged(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        fake_bot.results["threads_autosubscribe"] = Response(ok=False)

        with caplog.at_level("WARNING", logger="vkt_bot"):
            await ChatMembersJoinedHandler.handle(bot_added_event(), dispatcher)

        assert "refused thread autosubscribe" in caplog.text
