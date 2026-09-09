"""``AdminRequiredMixin``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

from vkt_bot.core.handlers.mixins import AdminRequiredMixin
from vkt_bot.core.repositories.role import RoleRepository
from vkt_dispatcher.handlers import CommandHandler

from tests.factories import assign_role, create_chat_user, make_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from vkt_dispatcher import Dispatcher
    from vkteams_client.types import Event

    from tests.conftest import FakeBot
    from vkt_bot.config import VktSettings
    from vkt_bot.core.models import Role


class Guarded(AdminRequiredMixin, CommandHandler):
    """Хендлер под защитой миксина."""

    commands = ["guarded"]

    def __init__(self) -> None:
        super().__init__()
        self.calls: list[Event] = []

    async def callback(self, bot: Any, event: Event) -> None:  # noqa: ANN401, ARG002
        self.calls.append(event)


@pytest.fixture
def handler() -> Guarded:
    """Защищённый хендлер."""
    return Guarded()


@pytest.fixture
def event() -> Event:
    """Команда ``/guarded`` от обычного пользователя."""
    return make_event("new_message", text="/guarded")


class TestAccessDenied:
    """Отказ в доступе."""

    async def test_plain_user_is_denied(
        self,
        handler: Guarded,
        event: Event,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
    ) -> None:
        await handler.handle(event, dispatcher)

        assert handler.calls == []
        (call,) = fake_bot.sent
        assert "нет доступа" in call.kwargs["text"]
        assert "@[1234567890]" in call.kwargs["text"]

    async def test_message_goes_to_the_same_chat(
        self,
        handler: Guarded,
        event: Event,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
    ) -> None:
        await handler.handle(event, dispatcher)
        assert fake_bot.sent[0].kwargs["chat_id"] == "681869378@chat.agent"

    async def test_user_with_other_role_is_denied(
        self,
        handler: Guarded,
        event: Event,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
    ) -> None:
        from tests.factories import create_role

        user = await create_chat_user(session, "1234567890")
        role = await create_role(session, "devs")
        await assign_role(session, user.id, role.id)

        await handler.handle(event, dispatcher)

        assert handler.calls == []


class TestAccessGranted:
    """Доступ разрешён."""

    async def test_owner_is_allowed(
        self,
        handler: Guarded,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        owner_id: str,
        session_factory: object,
    ) -> None:
        event = make_event(
            "new_message", text="/guarded", **{"from": {"userId": owner_id}}
        )
        await handler.handle(event, dispatcher)

        assert len(handler.calls) == 1
        assert fake_bot.calls == []

    async def test_user_with_admin_role_is_allowed(
        self,
        handler: Guarded,
        event: Event,
        dispatcher: Dispatcher,
        session: AsyncSession,
        admin_role: Role,
    ) -> None:
        user = await create_chat_user(session, "1234567890")
        await assign_role(session, user.id, admin_role.id)

        await handler.handle(event, dispatcher)

        assert len(handler.calls) == 1


class TestAdminRoleBootstrap:
    """Роль ``admin`` создаётся при первой проверке."""

    async def test_role_is_created_when_missing(
        self,
        handler: Guarded,
        event: Event,
        dispatcher: Dispatcher,
        session: AsyncSession,
    ) -> None:
        await handler.handle(event, dispatcher)

        assert await RoleRepository(session).get_by_name("admin")

    async def test_existing_role_is_reused(
        self,
        handler: Guarded,
        event: Event,
        dispatcher: Dispatcher,
        session: AsyncSession,
        admin_role: Role,
    ) -> None:
        await handler.handle(event, dispatcher)

        roles = await RoleRepository(session).list()
        assert [r.id for r in roles] == [admin_role.id]


class TestHelpers:
    """Вспомогательные проверки миксина."""

    def test_check_user_is_owner(self, handler: Guarded, owner_id: str) -> None:
        assert handler.check_user_is_owner(owner_id) is True
        assert handler.check_user_is_owner("other") is False

    def test_check_user_is_owner_without_owner_id(
        self,
        handler: Guarded,
        monkeypatch: pytest.MonkeyPatch,
        settings: VktSettings,
    ) -> None:
        monkeypatch.setattr(settings, "owner_id", None)
        assert handler.check_user_is_owner("anyone") is False

    async def test_check_user_is_admin(
        self,
        handler: Guarded,
        session: AsyncSession,
        admin_role: Role,
    ) -> None:
        user = await create_chat_user(session, "admin-check@example.com")
        assert await handler.check_user_is_admin(user.id) is False

        await assign_role(session, user.id, admin_role.id)
        assert await handler.check_user_is_admin(user.id) is True

    async def test_non_message_event_raises(
        self, handler: Guarded, dispatcher: Dispatcher
    ) -> None:
        with pytest.raises(TypeError, match="MessageHandler"):
            await handler.handle(make_event("callback_query"), dispatcher)
