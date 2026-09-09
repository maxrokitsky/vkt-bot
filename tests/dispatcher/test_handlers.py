"""Базовые классы хендлеров ``vkt_dispatcher.handlers``."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from vkt_dispatcher.filters import Filter
from vkt_dispatcher.handlers import (
    BotButtonCommandHandler,
    CommandHandler,
    DefaultHandler,
    DeletedMessageHandler,
    EditedMessageHandler,
    HandlerBase,
    HelpCommandHandler,
    LeftChatMembersHandler,
    MessageHandler,
    ChangedChatInfoHandler,
    NewChatMembersHandler,
    PinnedMessageHandler,
    StartCommandHandler,
    StopDispatchingError,
    UnPinnedMessageHandler,
)

from tests.factories import make_event

if TYPE_CHECKING:
    from vkteams_client.types import Event
    from vkt_dispatcher import Dispatcher

    from tests.conftest import FakeBot


class TestHandlerBase:
    """``HandlerBase``."""

    def test_without_filters_accepts_everything(self, dispatcher: Dispatcher) -> None:
        handler = HandlerBase()
        assert handler.check(make_event("new_message"), dispatcher) is True
        assert handler.check(make_event("changed_chat_info"), dispatcher) is True

    def test_filters_from_constructor(self, dispatcher: Dispatcher) -> None:
        handler = HandlerBase(filters=Filter.command)
        assert handler.check(make_event("new_message", text="/help"), dispatcher)
        assert not handler.check(make_event("new_message", text="привет"), dispatcher)

    async def test_handle_calls_callback_with_bot_and_event(
        self, dispatcher: Dispatcher, fake_bot: FakeBot
    ) -> None:
        seen: dict[str, Any] = {}

        async def callback(bot: Any, event: Any) -> None:  # noqa: ANN401
            seen["bot"] = bot
            seen["event"] = event

        event = make_event("new_message")
        await HandlerBase(callback=callback).handle(event, dispatcher)

        assert seen == {"bot": fake_bot, "event": event}

    async def test_handle_without_callback_does_nothing(
        self, dispatcher: Dispatcher
    ) -> None:
        await HandlerBase().handle(make_event("new_message"), dispatcher)

    def test_class_level_filters_are_used(self, dispatcher: Dispatcher) -> None:
        class OnlyCommands(HandlerBase):
            filters = Filter.command

        assert OnlyCommands().check(make_event("new_message", text="/x"), dispatcher)
        assert not OnlyCommands().check(make_event("new_message"), dispatcher)


EVENT_TYPE_HANDLERS = [
    (MessageHandler, "new_message"),
    (EditedMessageHandler, "edited_message"),
    (DeletedMessageHandler, "deleted_message"),
    (NewChatMembersHandler, "new_chat_members"),
    (LeftChatMembersHandler, "left_chat_members"),
    (ChangedChatInfoHandler, "changed_chat_info"),
    (PinnedMessageHandler, "pinned_message"),
    (UnPinnedMessageHandler, "unpinned_message"),
    (BotButtonCommandHandler, "callback_query"),
]


class TestEventTypeHandlers:
    """Хендлеры, отбирающие события по ``type``."""

    @pytest.mark.parametrize(("handler_cls", "fixture"), EVENT_TYPE_HANDLERS)
    def test_accepts_own_event(
        self, handler_cls: type[HandlerBase], fixture: str, dispatcher: Dispatcher
    ) -> None:
        assert handler_cls().check(make_event(fixture), dispatcher) is True

    @pytest.mark.parametrize(("handler_cls", "fixture"), EVENT_TYPE_HANDLERS)
    def test_rejects_foreign_events(
        self, handler_cls: type[HandlerBase], fixture: str, dispatcher: Dispatcher
    ) -> None:
        others = [f for _, f in EVENT_TYPE_HANDLERS if f != fixture]
        assert not any(
            handler_cls().check(make_event(other), dispatcher) for other in others
        )

    @pytest.mark.parametrize(("handler_cls", "fixture"), EVENT_TYPE_HANDLERS)
    def test_filters_are_combined_with_type_check(
        self, handler_cls: type[HandlerBase], fixture: str, dispatcher: Dispatcher
    ) -> None:
        handler = handler_cls(filters=Filter.command)
        event = make_event(fixture)
        # Команда есть только у newMessage, остальные отсеются фильтром.
        expected = fixture == "new_message"
        assert handler_cls(filters=Filter.message).check(event, dispatcher) is expected
        assert handler.check(event, dispatcher) is False


class TestCommandHandler:
    """``CommandHandler``."""

    def test_matches_its_command(self, dispatcher: Dispatcher) -> None:
        handler = CommandHandler(command="help")
        assert handler.check(make_event("new_message", text="/help"), dispatcher)

    def test_is_case_insensitive(self, dispatcher: Dispatcher) -> None:
        handler = CommandHandler(command="Help")
        assert handler.check(make_event("new_message", text="/HELP"), dispatcher)

    def test_accepts_arguments(self, dispatcher: Dispatcher) -> None:
        handler = CommandHandler(command="assignrole")
        event = make_event("new_message", text="/assignrole user@example.com admin")
        assert handler.check(event, dispatcher) is True

    def test_rejects_other_command(self, dispatcher: Dispatcher) -> None:
        handler = CommandHandler(command="help")
        assert not handler.check(make_event("new_message", text="/start"), dispatcher)

    def test_rejects_prefix_only_match(self, dispatcher: Dispatcher) -> None:
        handler = CommandHandler(command="help")
        assert not handler.check(make_event("new_message", text="/helpme"), dispatcher)

    def test_rejects_plain_text(self, dispatcher: Dispatcher) -> None:
        handler = CommandHandler(command="help")
        assert not handler.check(make_event("new_message"), dispatcher)

    def test_rejects_message_without_text(self, dispatcher: Dispatcher) -> None:
        from tests.factories import raw_event
        from vkteams_client.types import NewMessageEvent

        data = raw_event("new_message")
        del data["payload"]["text"]
        handler = CommandHandler(command="help")
        assert not handler.check(NewMessageEvent.model_validate(data), dispatcher)

    def test_rejects_non_message_events(self, dispatcher: Dispatcher) -> None:
        handler = CommandHandler(command="help")
        assert not handler.check(make_event("callback_query"), dispatcher)

    @pytest.mark.parametrize("prefix", [".", "!"])
    def test_alternative_prefixes(self, prefix: str, dispatcher: Dispatcher) -> None:
        handler = CommandHandler(command="help")
        event = make_event("new_message", text=f"{prefix}help")
        assert handler.check(event, dispatcher) is True

    def test_commands_as_class_var(self, dispatcher: Dispatcher) -> None:
        class ListRoles(CommandHandler):
            commands = ["listroles", "roles"]

        handler = ListRoles()
        assert handler.check(make_event("new_message", text="/listroles"), dispatcher)
        assert handler.check(make_event("new_message", text="/roles"), dispatcher)
        assert not handler.check(make_event("new_message", text="/other"), dispatcher)

    def test_without_command_raises_attribute_error(
        self, dispatcher: Dispatcher
    ) -> None:
        """``CommandHandler()`` без команды не задаёт ``self.commands``.

        Ветка ``not self.commands`` в ``check`` недостижима: атрибут просто
        отсутствует. Фиксируем поведение — см. ROADMAP 3.9.
        """
        handler = CommandHandler()
        with pytest.raises(AttributeError):
            handler.check(make_event("new_message", text="/help"), dispatcher)

    def test_extra_filters_are_combined(self, dispatcher: Dispatcher) -> None:
        handler = CommandHandler(command="help", filters=Filter.sender("1234567890"))
        assert handler.check(
            make_event("new_message_private", text="/help"), dispatcher
        )
        assert not handler.check(make_event("new_message", text="/help"), dispatcher)

    def test_roles_are_stored(self) -> None:
        handler = CommandHandler(command="x", roles=["admin"])
        assert handler.roles == ["admin"]

    def test_roles_default_is_not_set(self) -> None:
        assert not hasattr(CommandHandler(command="x"), "roles")


class TestNamedCommandHandlers:
    """``HelpCommandHandler`` и ``StartCommandHandler``."""

    def test_help(self, dispatcher: Dispatcher) -> None:
        assert HelpCommandHandler().check(
            make_event("new_message", text="/help"), dispatcher
        )

    def test_start(self, dispatcher: Dispatcher) -> None:
        assert StartCommandHandler().check(
            make_event("new_message", text="/start"), dispatcher
        )

    def test_start_rejects_help(self, dispatcher: Dispatcher) -> None:
        assert not StartCommandHandler().check(
            make_event("new_message", text="/help"), dispatcher
        )


class TestDefaultHandler:
    """``DefaultHandler``."""

    def test_matches_when_nobody_else_does(self, dispatcher: Dispatcher) -> None:
        default = dispatcher.register_handler(DefaultHandler())
        dispatcher.register_handler(CommandHandler(command="help"))

        assert default.check(make_event("new_message"), dispatcher) is True

    def test_does_not_match_when_someone_else_does(
        self, dispatcher: Dispatcher
    ) -> None:
        default = dispatcher.register_handler(DefaultHandler())
        dispatcher.register_handler(CommandHandler(command="help"))

        event = make_event("new_message", text="/help")
        assert default.check(event, dispatcher) is False

    def test_ignores_itself_when_checking(self, dispatcher: Dispatcher) -> None:
        default = dispatcher.register_handler(DefaultHandler())
        assert default.check(make_event("new_message"), dispatcher) is True

    async def test_handle_raises_stop_dispatching(self, dispatcher: Dispatcher) -> None:
        with pytest.raises(StopDispatchingError):
            await DefaultHandler().handle(make_event("new_message"), dispatcher)

    async def test_handle_calls_callback_before_raising(
        self, dispatcher: Dispatcher
    ) -> None:
        called: list[Event] = []

        async def callback(bot: Any, event: Event) -> None:  # noqa: ANN401, ARG001
            called.append(event)

        with pytest.raises(StopDispatchingError):
            await DefaultHandler(callback=callback).handle(
                make_event("new_message"), dispatcher
            )
        assert len(called) == 1
