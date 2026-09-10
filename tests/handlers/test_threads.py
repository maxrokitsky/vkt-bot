"""Подписка на обсуждения командой ``/subscribethreads``."""

from __future__ import annotations

from typing import TYPE_CHECKING

from vkteams_client.types import Response

from vkt_bot.core.handlers.threads import SubscribeThreadsHandler

from tests.factories import make_event

if TYPE_CHECKING:
    from vkt_dispatcher import Dispatcher
    from vkteams_client.types import Event

    from tests.conftest import FakeBot

CHAT_ID = "681869378@chat.agent"


def owner_message(text: str, owner_id: str) -> Event:
    """Сообщение от владельца бота (проходит ``AdminRequiredMixin``)."""
    return make_event("new_message", text=text, **{"from": {"userId": owner_id}})


class TestSubscribeThreads:
    """``/subscribethreads``."""

    async def test_subscribes_including_existing_threads(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        await SubscribeThreadsHandler.handle(
            owner_message("/subscribethreads", owner_id), dispatcher
        )

        (call,) = fake_bot.calls_of("threads_autosubscribe")
        assert call.kwargs["chat_id"] == CHAT_ID
        assert call.kwargs["enable"] is True
        assert call.kwargs["with_existing"] is True
        assert "подписался на обсуждения" in fake_bot.texts[-1]

    async def test_off_unsubscribes(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        await SubscribeThreadsHandler.handle(
            owner_message("/subscribethreads off", owner_id), dispatcher
        )

        (call,) = fake_bot.calls_of("threads_autosubscribe")
        assert call.kwargs["enable"] is False
        assert "больше не подписываюсь" in fake_bot.texts[-1]

    async def test_requires_admin(
        self, dispatcher: Dispatcher, fake_bot: FakeBot, session_factory: object
    ) -> None:
        await SubscribeThreadsHandler.handle(
            make_event("new_message", text="/subscribethreads"), dispatcher
        )

        assert fake_bot.calls_of("threads_autosubscribe") == []
        assert "нет доступа" in fake_bot.texts[-1]

    async def test_api_failure_is_reported(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        fake_bot.results["threads_autosubscribe"] = Response(ok=False)

        await SubscribeThreadsHandler.handle(
            owner_message("/subscribethreads", owner_id), dispatcher
        )

        assert "не удалось" in fake_bot.texts[-1]

    async def test_api_error_is_reported(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
        owner_id: str,
    ) -> None:
        fake_bot.errors["threads_autosubscribe"] = RuntimeError("нет связи")

        await SubscribeThreadsHandler.handle(
            owner_message("/subscribethreads", owner_id), dispatcher
        )

        assert "не удалось" in fake_bot.texts[-1]

    def test_matches_command(self, dispatcher: Dispatcher, owner_id: str) -> None:
        assert (
            SubscribeThreadsHandler.check(
                owner_message("/subscribethreads", owner_id), dispatcher
            )
            is True
        )

    def test_ignores_other_commands(
        self, dispatcher: Dispatcher, owner_id: str
    ) -> None:
        assert (
            SubscribeThreadsHandler.check(
                owner_message("/listroles", owner_id), dispatcher
            )
            is False
        )
