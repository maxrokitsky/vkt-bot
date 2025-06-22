from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING, Any, NoReturn

from vkteams_client.types import EventType, NewMessageEvent
from .filters import Filter

if TYPE_CHECKING:
    from .filters import FilterBase

    from vkteams_client.types import Event
    from .dispatcher import Dispatcher


class StopDispatchingError(Exception):
    """StopDispatchingError."""


class HandlerBase:
    """HandlerBase."""

    filters: FilterBase | None = None
    callback: Callable[..., Any] | None = None

    def __init__(
        self,
        filters: FilterBase | None = None,
        callback: Callable[..., Any] | None = None,
    ) -> None:
        """__init__."""
        if filters:
            self.filters = filters
        if callback:
            self.callback = callback

    def check(self, event: Event, dispatcher: Dispatcher) -> bool:
        """Check."""
        return bool(not self.filters or self.filters(event))

    async def handle(self, event: Event, dispatcher: Dispatcher) -> None:
        if self.callback:
            await self.callback(bot=dispatcher.bot, event=event)


class DefaultHandler(HandlerBase):
    """DefaultHandler."""

    def __init__(self, callback: Callable[..., Any] | None = None) -> None:
        """__init__."""
        super().__init__(callback=callback)

    def check(self, event: Event, dispatcher: Dispatcher) -> bool:
        """Check."""
        return super().check(event=event, dispatcher=dispatcher) and not any(
            h.check(event=event, dispatcher=dispatcher)
            for h in dispatcher.handlers
            if h is not self
        )

    async def handle(self, event: Event, dispatcher: Dispatcher) -> NoReturn:
        """Handle."""
        await super().handle(event=event, dispatcher=dispatcher)
        raise StopDispatchingError


class NewChatMembersHandler(HandlerBase):
    """NewChatMembersHandler."""

    def check(self, event: Event, dispatcher: Dispatcher) -> bool:
        """Check."""
        return (
            super().check(event=event, dispatcher=dispatcher)
            and event.type == EventType.NEW_CHAT_MEMBERS
        )


class LeftChatMembersHandler(HandlerBase):
    """LeftChatMembersHandler."""

    def check(self, event: Event, dispatcher: Dispatcher) -> bool:
        """Check."""
        return (
            super().check(event=event, dispatcher=dispatcher)
            and event.type == EventType.LEFT_CHAT_MEMBERS
        )


class PinnedMessageHandler(HandlerBase):
    """PinnedMessageHandler."""

    def check(self, event: Event, dispatcher: Dispatcher) -> bool:
        """Check."""
        return (
            super().check(event=event, dispatcher=dispatcher)
            and event.type == EventType.PINNED_MESSAGE
        )


class UnPinnedMessageHandler(HandlerBase):
    """UnPinnedMessageHandler."""

    def check(self, event: Event, dispatcher: Dispatcher) -> bool:
        """Check."""
        return (
            super().check(event=event, dispatcher=dispatcher)
            and event.type == EventType.UNPINNED_MESSAGE
        )


class MessageHandler(HandlerBase):
    """MessageHandler."""

    def check(self, event: Event, dispatcher: Dispatcher) -> bool:
        """Check."""
        return (
            super().check(event=event, dispatcher=dispatcher)
            and event.type == EventType.NEW_MESSAGE
        )


class EditedMessageHandler(HandlerBase):
    """EditedMessageHandler."""

    def check(self, event: Event, dispatcher: Dispatcher) -> bool:
        """Check."""
        return (
            super().check(event=event, dispatcher=dispatcher)
            and event.type == EventType.EDITED_MESSAGE
        )


class DeletedMessageHandler(HandlerBase):
    """DeletedMessageHandler."""

    def check(self, event: Event, dispatcher: Dispatcher) -> bool:
        """Check."""
        return (
            super().check(event=event, dispatcher=dispatcher)
            and event.type == EventType.DELETED_MESSAGE
        )


class CommandHandler(MessageHandler):
    """CommandHandler."""

    def __init__(
        self,
        command: str | None = None,
        filters: FilterBase | None = None,
        callback: Callable[..., Any] | None = None,
        roles: list[str] | None = None,
    ) -> None:
        """__init__."""
        super().__init__(
            filters=Filter.command if filters is None else Filter.command & filters,
            callback=callback,
        )
        if command:
            self.commands = [command] if command else []
        if roles is not None:
            self.roles = roles

    def check(self, event: Event, dispatcher: Dispatcher) -> bool:
        """Check."""
        if not isinstance(event, NewMessageEvent) or not event.payload.text:
            return False
        if super().check(event=event, dispatcher=dispatcher):
            command = event.payload.text.partition(" ")[0][1:].lower()
            return not self.commands or any(c.lower() == command for c in self.commands)
        return False


class HelpCommandHandler(CommandHandler):
    """HelpCommandHandler."""

    def __init__(
        self,
        filters: FilterBase | None = None,
        callback: Callable[..., Any] | None = None,
    ) -> None:
        """__init__."""
        super().__init__(command="help", filters=filters, callback=callback)


class StartCommandHandler(CommandHandler):
    """StartCommandHandler."""

    def __init__(
        self,
        filters: FilterBase | None = None,
        callback: Callable[..., Any] | None = None,
    ) -> None:
        """__init__."""
        super().__init__(command="start", filters=filters, callback=callback)


# class FeedbackCommandHandler(CommandHandler):
#     """FeedbackCommandHandler."""

#     def __init__(
#         self,
#         target,
#         message='Feedback from {source}: {message}',
#         reply='Got it!',
#         error_reply=None,
#         command='feedback',
#         filters=None,
#     ) -> None:
#         """__init__."""
#         super().__init__(command=command, filters=filters, callback=self.message_cb)

#         self.target = target
#         self.message = message
#         self.reply = reply
#         self.error_reply = error_reply

#     def message_cb(self, bot, event):
#         source = event.data['chat']['chatId']
#         feedback_text = event.data['text'].partition(' ')[2].strip()

#         if feedback_text:
#             bot.send_text(chat_id=self.target, text=self.message.format(source=source, message=feedback_text))

#             if self.reply is not None:
#                 bot.send_text(chat_id=source, text=self.reply)
#         elif self.error_reply is not None:
#             bot.send_text(chat_id=source, text=self.error_reply)


# class UnknownCommandHandler(CommandHandler):
#     """UnknownCommandHandler."""

#     def __init__(self, filters=None, callback: Callable[..., Any] | None = None) -> None:
#         """__init__."""
#         super().__init__(filters=filters, callback=callback)

#     def check(self, event: Event, dispatcher: Dispatcher) -> bool:
# """Check."""
#         return super().check(event=event, dispatcher=dispatcher) and not any(
#             h.check(event=event, dispatcher=dispatcher)
#             for h in dispatcher.handlers
#             if isinstance(h, CommandHandler) and h is not self
#         )

#     def handle(self, event: Event, dispatcher):
#         super().handle(event=event, dispatcher=dispatcher)
#         raise StopDispatchingError


class BotButtonCommandHandler(HandlerBase):
    """BotButtonCommandHandler."""

    def check(self, event: Event, dispatcher: Dispatcher) -> bool:
        """Check."""
        return (
            super().check(event=event, dispatcher=dispatcher)
            and event.type == EventType.CALLBACK_QUERY
        )
