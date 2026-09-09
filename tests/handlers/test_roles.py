"""Хендлеры управления ролями."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

import pytest

from vkt_bot.core.handlers.callback import DeleteRoleCallbackData
from vkt_bot.core.handlers.roles import (
    AssignRoleHandler,
    CreateRoleHandler,
    DeleteRoleConfirmation,
    DeleteRoleHandler,
    ListRoleMembersHandler,
    ListRolesHandler,
    NotifyRoleIsTaggedHandler,
    RevokeRoleHandler,
)
from vkt_bot.core.models import Role, RoleAssignment
from vkt_bot.core.repositories.role import RoleRepository
from vkt_bot.db.exceptions import NotFoundError

from tests.conftest import table_count
from tests.factories import assign_role, create_chat_user, create_role, make_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from vkt_dispatcher import Dispatcher
    from vkteams_client.types import Event

    from tests.conftest import FakeBot


def owner_message(text: str, owner_id: str) -> Event:
    """Сообщение от владельца бота (проходит ``AdminRequiredMixin``)."""
    return make_event("new_message", text=text, **{"from": {"userId": owner_id}})


class TestCreateRole:
    """``/createrole``."""

    async def test_creates_role(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        await CreateRoleHandler.handle(
            owner_message("/createrole devs", owner_id), dispatcher
        )

        assert (await RoleRepository(session).get_by_name("devs")).name == "devs"
        assert "роль devs добавлена" in fake_bot.texts[-1]

    async def test_duplicate_role_is_reported(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        await create_role(session, "devs")

        await CreateRoleHandler.handle(
            owner_message("/createrole devs", owner_id), dispatcher
        )

        assert "уже существует" in fake_bot.texts[-1]
        assert await table_count(session, Role) == 1

    async def test_requires_admin(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await CreateRoleHandler.handle(
            make_event("new_message", text="/createrole devs"), dispatcher
        )

        assert "нет доступа" in fake_bot.texts[-1]
        assert await table_count(session, Role) == 1  # только созданная роль admin

    async def test_without_argument_raises(
        self, dispatcher: Dispatcher, session_factory: object, owner_id: str
    ) -> None:
        """Известный дефект: команда без аргумента падает на ``args[0]``."""
        with pytest.raises(IndexError):
            await CreateRoleHandler.handle(
                owner_message("/createrole", owner_id), dispatcher
            )


class TestDeleteRole:
    """``/deleterole``."""

    async def test_deletes_unused_role(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        await create_role(session, "devs")

        await DeleteRoleHandler.handle(
            owner_message("/deleterole devs", owner_id), dispatcher
        )

        with pytest.raises(NotFoundError):
            await RoleRepository(session).get_by_name("devs")
        assert "удалена" in fake_bot.texts[-1]

    @pytest.mark.parametrize("protected", ["admin", "botowner", "ADMIN"])
    async def test_protected_roles_cannot_be_deleted(
        self,
        protected: str,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        await DeleteRoleHandler.handle(
            owner_message(f"/deleterole {protected}", owner_id), dispatcher
        )

        assert "нельзя удалить" in fake_bot.texts[-1]

    async def test_unknown_role_is_reported(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        await DeleteRoleHandler.handle(
            owner_message("/deleterole nope", owner_id), dispatcher
        )
        assert "не существует" in fake_bot.texts[-1]

    async def test_assigned_role_asks_for_confirmation(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        role = await create_role(session, "devs")
        user = await create_chat_user(session, "u@example.com")
        await assign_role(session, user.id, role.id)

        await DeleteRoleHandler.handle(
            owner_message("/deleterole devs", owner_id), dispatcher
        )

        (call,) = fake_bot.sent
        assert "Вы уверены" in call.text
        keyboard = json.loads(call.kwargs["inline_keyboard_markup"])
        button = keyboard[0][0]
        assert button["style"] == "attention"
        data = DeleteRoleCallbackData.model_validate_json(button["callbackData"])
        assert data.role == "devs"
        assert data.requested_by == owner_id
        assert await table_count(session, Role) == 1


class TestDeleteRoleConfirmation:
    """Подтверждение удаления роли кнопкой."""

    def callback_event(self, role: str, requested_by: str, sender: str) -> Event:
        """Callback-событие подтверждения."""
        return make_event(
            "callback_query",
            **{
                "from": {"userId": sender},
                "callbackData": DeleteRoleCallbackData(
                    role=role, requested_by=requested_by
                ).model_dump_json(),
            },
        )

    async def test_deletes_role_and_assignments(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        role = await create_role(session, "devs")
        user = await create_chat_user(session, "u@example.com")
        await assign_role(session, user.id, role.id)

        await DeleteRoleConfirmation.handle(
            self.callback_event("devs", "1234567890", "1234567890"), dispatcher
        )

        assert await table_count(session, Role) == 0
        assert await table_count(session, RoleAssignment) == 0

    async def test_answers_query_and_edits_message(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await create_role(session, "devs")

        await DeleteRoleConfirmation.handle(
            self.callback_event("devs", "1234567890", "1234567890"), dispatcher
        )

        (answer,) = fake_bot.calls_of("answer_callback_query")
        assert "удалена" in answer.kwargs["text"]
        (edit,) = fake_bot.calls_of("edit_text")
        assert edit.kwargs["msg_id"] == "6752739791872001120"

    async def test_only_requester_can_confirm(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await create_role(session, "devs")

        await DeleteRoleConfirmation.handle(
            self.callback_event("devs", "1234567890", "9999999999"), dispatcher
        )

        (answer,) = fake_bot.calls_of("answer_callback_query")
        assert answer.kwargs["show_alert"] is True
        assert await table_count(session, Role) == 1

    async def test_already_deleted_role(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session_factory: object
    ) -> None:
        await DeleteRoleConfirmation.handle(
            self.callback_event("devs", "1234567890", "1234567890"), dispatcher
        )

        (answer,) = fake_bot.calls_of("answer_callback_query")
        assert "уже не существует" in answer.kwargs["text"]

    async def test_ignores_foreign_callback_data(
        self, dispatcher: Dispatcher, fake_bot: FakeBot
    ) -> None:
        event = make_event(
            "callback_query",
            callbackData=json.dumps(
                {"command": "start__showcommands", "requested_by": "1234567890"}
            ),
        )
        await DeleteRoleConfirmation.handle(event, dispatcher)
        assert fake_bot.calls == []


class TestAssignRole:
    """``/assignrole``."""

    async def test_assigns_role(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        await create_role(session, "devs")

        await AssignRoleHandler.handle(
            owner_message("/assignrole u@example.com devs", owner_id), dispatcher
        )

        assert await table_count(session, RoleAssignment) == 1

    async def test_notifies_both_chat_and_user(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        await create_role(session, "devs")

        await AssignRoleHandler.handle(
            owner_message("/assignrole u@example.com devs", owner_id), dispatcher
        )

        chats = [call.chat_id for call in fake_bot.sent]
        assert "681869378@chat.agent" in chats
        assert "u@example.com" in chats

    async def test_creates_user_if_missing(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        from vkt_bot.core.repositories.user import ChatUserRepository

        await create_role(session, "devs")
        await AssignRoleHandler.handle(
            owner_message("/assignrole newbie@example.com devs", owner_id), dispatcher
        )

        assert await ChatUserRepository(session).get_or_none("newbie@example.com")

    async def test_unknown_role(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        await AssignRoleHandler.handle(
            owner_message("/assignrole u@example.com nope", owner_id), dispatcher
        )
        assert "не существует" in fake_bot.texts[-1]

    async def test_botowner_role_cannot_be_assigned(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        await create_role(session, "botowner")

        await AssignRoleHandler.handle(
            owner_message("/assignrole u@example.com botowner", owner_id), dispatcher
        )

        assert "нельзя назначить" in fake_bot.texts[-1]
        assert await table_count(session, RoleAssignment) == 0

    async def test_duplicate_assignment_is_reported(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        role = await create_role(session, "devs")
        user = await create_chat_user(session, "u@example.com")
        await assign_role(session, user.id, role.id)

        await AssignRoleHandler.handle(
            owner_message("/assignrole u@example.com devs", owner_id), dispatcher
        )

        assert "уже назначена" in fake_bot.texts[-1]
        assert await table_count(session, RoleAssignment) == 1

    async def test_missing_arguments_raise(
        self, dispatcher: Dispatcher, session_factory: object, owner_id: str
    ) -> None:
        """Известный дефект: без второго аргумента падает на ``args[1]``."""
        with pytest.raises(IndexError):
            await AssignRoleHandler.handle(
                owner_message("/assignrole u@example.com", owner_id), dispatcher
            )


class TestRevokeRole:
    """``/revokerole``."""

    async def test_revokes_role(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        role = await create_role(session, "devs")
        user = await create_chat_user(session, "u@example.com")
        await assign_role(session, user.id, role.id)

        await RevokeRoleHandler.handle(
            owner_message("/revokerole u@example.com devs", owner_id), dispatcher
        )

        assert await table_count(session, RoleAssignment) == 0
        assert "отозвана" in fake_bot.texts[-1]

    async def test_unknown_role(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        await RevokeRoleHandler.handle(
            owner_message("/revokerole u@example.com nope", owner_id), dispatcher
        )
        assert "не существует" in fake_bot.texts[-1]

    async def test_botowner_role_cannot_be_revoked(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        await create_role(session, "botowner")

        await RevokeRoleHandler.handle(
            owner_message("/revokerole u@example.com botowner", owner_id), dispatcher
        )

        assert "нельзя отозвать" in fake_bot.texts[-1]

    async def test_user_without_role(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
        owner_id: str,
    ) -> None:
        await create_role(session, "devs")

        await RevokeRoleHandler.handle(
            owner_message("/revokerole u@example.com devs", owner_id), dispatcher
        )

        assert "нет роли" in fake_bot.texts[-1]


class TestListRoles:
    """``/listroles``."""

    async def test_lists_all_roles(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await create_role(session, "devs")
        await create_role(session, "qa")

        await ListRolesHandler.handle(
            make_event("new_message", text="/listroles"), dispatcher
        )

        text = fake_bot.texts[-1]
        assert "devs" in text
        assert "qa" in text

    async def test_lists_user_roles(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        role = await create_role(session, "devs")
        user = await create_chat_user(session, "u@example.com")
        await assign_role(session, user.id, role.id)

        await ListRolesHandler.handle(
            make_event("new_message", text="/listroles u@example.com"), dispatcher
        )

        assert "роли пользователя u@example.com: devs" in fake_bot.texts[-1]

    async def test_unknown_user(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session_factory: object
    ) -> None:
        await ListRolesHandler.handle(
            make_event("new_message", text="/listroles ghost@example.com"), dispatcher
        )
        assert "не найден" in fake_bot.texts[-1]

    async def test_user_without_roles(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await create_chat_user(session, "u@example.com")

        await ListRolesHandler.handle(
            make_event("new_message", text="/listroles u@example.com"), dispatcher
        )

        assert "нет ролей" in fake_bot.texts[-1]

    async def test_does_not_require_admin(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session_factory: object
    ) -> None:
        await ListRolesHandler.handle(
            make_event("new_message", text="/listroles"), dispatcher
        )
        assert "нет доступа" not in fake_bot.texts[-1]


class TestListRoleMembers:
    """``/listrolemembers``."""

    async def test_lists_members(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        role = await create_role(session, "devs")
        user = await create_chat_user(session, "u@example.com")
        await assign_role(session, user.id, role.id)

        await ListRoleMembersHandler.handle(
            make_event("new_message", text="/listrolemembers devs"), dispatcher
        )

        assert "u@example.com" in fake_bot.texts[-1]

    async def test_without_argument(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session_factory: object
    ) -> None:
        await ListRoleMembersHandler.handle(
            make_event("new_message", text="/listrolemembers"), dispatcher
        )
        assert "укажите" in fake_bot.texts[-1]

    async def test_unknown_role(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session_factory: object
    ) -> None:
        await ListRoleMembersHandler.handle(
            make_event("new_message", text="/listrolemembers nope"), dispatcher
        )
        assert "не найдена" in fake_bot.texts[-1]

    async def test_role_without_members(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        await create_role(session, "devs")

        await ListRoleMembersHandler.handle(
            make_event("new_message", text="/listrolemembers devs"), dispatcher
        )

        assert "нет пользователей" in fake_bot.texts[-1]


class TestNotifyRoleIsTagged:
    """Упоминание роли через хештег."""

    def test_matches_hashtag(self, dispatcher: Dispatcher) -> None:
        event = make_event("new_message", text="Нужна помощь #devs")
        assert NotifyRoleIsTaggedHandler.check(event, dispatcher) is True

    def test_ignores_message_without_hashtag(self, dispatcher: Dispatcher) -> None:
        event = make_event("new_message", text="просто текст")
        assert NotifyRoleIsTaggedHandler.check(event, dispatcher) is False

    async def test_forwards_message_to_role_members(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        role = await create_role(session, "devs")
        user = await create_chat_user(session, "u@example.com")
        await assign_role(session, user.id, role.id)

        event = make_event("new_message", text="Нужна помощь #devs")
        await NotifyRoleIsTaggedHandler.handle(event, dispatcher)

        (call,) = fake_bot.sent
        assert call.kwargs["chat_id"] == "u@example.com"
        assert call.kwargs["forward_chat_id"] == "681869378@chat.agent"
        assert call.kwargs["forward_msg_id"] == event.payload.msgId
        assert "Тестовая группа" in call.kwargs["text"]

    async def test_several_hashtags(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        devs = await create_role(session, "devs")
        qa = await create_role(session, "qa")
        dev = await create_chat_user(session, "dev@example.com")
        tester = await create_chat_user(session, "qa@example.com")
        await assign_role(session, dev.id, devs.id)
        await assign_role(session, tester.id, qa.id)

        event = make_event("new_message", text="#devs и #qa, гляньте")
        await NotifyRoleIsTaggedHandler.handle(event, dispatcher)

        assert {call.kwargs["chat_id"] for call in fake_bot.sent} == {
            "dev@example.com",
            "qa@example.com",
        }

    async def test_unknown_hashtag_sends_nothing(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session_factory: object
    ) -> None:
        event = make_event("new_message", text="#nonexistent")
        await NotifyRoleIsTaggedHandler.handle(event, dispatcher)
        assert fake_bot.calls == []

    async def test_hashtag_at_the_start_of_message(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        role = await create_role(session, "devs")
        user = await create_chat_user(session, "u@example.com")
        await assign_role(session, user.id, role.id)

        await NotifyRoleIsTaggedHandler.handle(
            make_event("new_message", text="#devs"), dispatcher
        )

        assert len(fake_bot.sent) == 1

    async def test_hashtag_inside_word_is_ignored(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session: AsyncSession
    ) -> None:
        role = await create_role(session, "devs")
        user = await create_chat_user(session, "u@example.com")
        await assign_role(session, user.id, role.id)

        event = make_event("new_message", text="mail#devs")
        await NotifyRoleIsTaggedHandler.handle(event, dispatcher)

        assert fake_bot.calls == []
