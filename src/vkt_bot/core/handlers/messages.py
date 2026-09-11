"""История сообщений: правки, удаления и выключатель на чат."""

from typing import ClassVar

import structlog

from vkteams_client import VKTeams
from vkteams_client.types import (
    DeletedMessageEvent,
    EditedMessageEvent,
    NewMessageEvent,
)
from vkt_dispatcher.handlers import (
    CommandHandler,
    DeletedMessageHandler,
    EditedMessageHandler,
)

from vkt_bot.app import dispatcher
from vkt_bot.core.handlers.mixins import AdminRequiredMixin
from vkt_bot.core.messages import history_enabled, set_chat_history
from vkt_bot.core.repositories.message import MessageRepository
from vkt_bot.db.session import async_session
from vkt_bot.utils.message import mention

logger = structlog.get_logger("vkt_bot.handlers.messages")

OFF_ARGS = frozenset({"off", "выкл", "0", "false", "no"})
ON_ARGS = frozenset({"on", "вкл", "1", "true", "yes"})


@dispatcher.register_handler
class MessageEditedHandler(EditedMessageHandler):
    """Правка сообщения обновляет текст в истории."""

    async def callback(self, bot: VKTeams, event: EditedMessageEvent) -> None:
        payload = event.payload
        async with async_session() as session:
            # Проверки на ``history_enabled`` здесь нет намеренно, как и у
            # удаления: новых строк правка не создаёт, а оставить уже
            # сохранённую с дореакционным текстом — хуже, чем обновить.
            # Запись выключили — значит, в истории не должно остаться того,
            # что человек уже исправил.
            await MessageRepository(session).mark_edited(
                payload.chat.chatId,
                payload.msgId,
                payload.text,
                payload.editedTimestamp,
            )
            await session.commit()


@dispatcher.register_handler
class MessageDeletedHandler(DeletedMessageHandler):
    """Удалённое сообщение помечается и больше не отдаётся.

    Строка не удаляется физически: по ней видно, что сообщение было, —
    но ни автоконтекст, ни инструменты агента её не покажут.
    """

    async def callback(self, bot: VKTeams, event: DeletedMessageEvent) -> None:
        payload = event.payload
        async with async_session() as session:
            await MessageRepository(session).mark_deleted(
                payload.chat.chatId, payload.msgId
            )
            await session.commit()


@dispatcher.register_handler
class HistoryHandler(AdminRequiredMixin, CommandHandler):
    """/history — запись истории сообщений в текущем чате."""

    commands: ClassVar[list[str]] = ["history"]
    description = "/history [off] - Включить или выключить историю сообщений чата"

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        args = (event.payload.text or "").split()[1:]
        chat_id = event.payload.chat.chatId
        who = mention(event.payload.sender.userId)

        async with async_session() as session:
            if not args:
                enabled = await history_enabled(session, chat_id)
                state = "включена" if enabled else "выключена"
                await bot.send_text(
                    chat_id,
                    f"{who}, запись истории сообщений в этом чате {state}. "
                    "Выключить — /history off, включить обратно — /history on.",
                )
                return

            argument = args[0].lower()
            if argument not in OFF_ARGS | ON_ARGS:
                # Опечатка не должна молча включать запись переписки:
                # «/history оff» с латинской o раньше означала «включить».
                await bot.send_text(
                    chat_id,
                    f"{who}, не понял «{args[0]}». "
                    "Включить — /history on, выключить — /history off.",
                )
                return

            enable = argument in ON_ARGS
            await set_chat_history(session, chat_id, enabled=enable)
            await session.commit()

        if enable:
            await bot.send_text(
                chat_id,
                f"{who}, записываю историю сообщений этого чата. "
                "Она нужна ИИ-агенту, чтобы отвечать в контексте разговора.",
            )
        else:
            await bot.send_text(
                chat_id,
                f"{who}, больше не записываю сообщения этого чата. "
                "Уже записанное остаётся до истечения срока хранения.",
            )
