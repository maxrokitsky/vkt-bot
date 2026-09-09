"""Хендлеры ``/help`` и ``/start``."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

from vkt_bot.core.constants import DEFAULT_START_MESSAGE
from vkt_bot.core.handlers.callback import ShowCommandsCallbackData
from vkt_bot.core.handlers.help import (
    DeleteRoleConfirmation,
    HelpHandler,
    StartHandler,
    help_msg,
)
from vkt_bot.core.repositories.bot_settings import BotSettingsRepository

from tests.factories import make_event

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession
    from vkt_dispatcher import Dispatcher

    from tests.conftest import FakeBot


class TestHelpHandler:
    """``/help``."""

    def test_matches_help_command(self, dispatcher: Dispatcher) -> None:
        assert HelpHandler.check(make_event("new_message", text="/help"), dispatcher)

    def test_rejects_other_commands(self, dispatcher: Dispatcher) -> None:
        assert not HelpHandler.check(
            make_event("new_message", text="/start"), dispatcher
        )

    async def test_sends_help_message(
        self, dispatcher: Dispatcher, fake_bot: FakeBot
    ) -> None:
        event = make_event("new_message", text="/help")
        await HelpHandler.handle(event, dispatcher)

        (call,) = fake_bot.sent
        assert call.chat_id == "681869378@chat.agent"
        assert call.text == help_msg
        assert call.kwargs["parse_mode"] == "MarkdownV2"

    def test_help_message_lists_main_commands(self) -> None:
        for command in ("/start", "/help", "/listroles", "/createrole"):
            assert command in help_msg


class TestStartHandler:
    """``/start``."""

    def test_matches_start_command(self, dispatcher: Dispatcher) -> None:
        assert StartHandler.check(make_event("new_message", text="/start"), dispatcher)

    async def test_sends_default_message(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
    ) -> None:
        event = make_event("new_message", text="/start")
        await StartHandler.handle(event, dispatcher)

        (call,) = fake_bot.sent
        assert call.text == DEFAULT_START_MESSAGE

    async def test_sends_custom_message_from_settings(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session: AsyncSession,
    ) -> None:
        await BotSettingsRepository(session).set_value("start_message", "Своё привет")
        await session.commit()

        await StartHandler.handle(make_event("new_message", text="/start"), dispatcher)

        assert fake_bot.texts == ["Своё привет"]

    async def test_attaches_show_commands_button(
        self,
        dispatcher: Dispatcher,
        fake_bot: FakeBot,
        session_factory: object,
    ) -> None:
        event = make_event("new_message", text="/start")
        await StartHandler.handle(event, dispatcher)

        keyboard = json.loads(fake_bot.sent[0].kwargs["inline_keyboard_markup"])
        (row,) = keyboard
        (button,) = row
        assert button["text"] == "Показать команды"
        callback = ShowCommandsCallbackData.model_validate_json(button["callbackData"])
        assert callback.command == "start__showcommands"
        assert callback.requested_by == "1234567890"


class TestShowCommandsCallback:
    """Кнопка «Показать команды»."""

    def test_accepts_callback_query(self, dispatcher: Dispatcher) -> None:
        assert DeleteRoleConfirmation.check(make_event("callback_query"), dispatcher)

    async def test_sends_help_and_answers_query(
        self, dispatcher: Dispatcher, fake_bot: FakeBot
    ) -> None:
        event = make_event("callback_query")
        await DeleteRoleConfirmation.handle(event, dispatcher)

        assert fake_bot.texts == [help_msg]
        (answer,) = fake_bot.calls_of("answer_callback_query")
        assert answer.kwargs["query_id"] == "SVR:123456"

    async def test_ignores_other_callback_data(
        self, dispatcher: Dispatcher, fake_bot: FakeBot
    ) -> None:
        event = make_event(
            "callback_query",
            callbackData=json.dumps(
                {
                    "command": "deleterole",
                    "role": "devs",
                    "requested_by": "1234567890",
                }
            ),
        )
        await DeleteRoleConfirmation.handle(event, dispatcher)

        assert fake_bot.calls == []
