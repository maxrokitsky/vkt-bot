from typing import ClassVar

import structlog

from vkteams_client import VKTeams
from vkteams_client.types import NewMessageEvent
from vkt_dispatcher.handlers import CommandHandler

from vkt_bot.app import dispatcher
from vkt_bot.core.events import Actor, EventType, emit
from vkt_bot.core.handlers.mixins import AdminRequiredMixin
from vkt_bot.core.models.event import EntityType
from vkt_bot.core.threads import set_thread_autosubscribe
from vkt_bot.db.session import async_session
from vkt_bot.utils.message import mention

logger = structlog.get_logger("vkt_bot.handlers.threads")

OFF_ARGS = frozenset({"off", "выкл", "0", "false", "no"})


@dispatcher.register_handler
class SubscribeThreadsHandler(AdminRequiredMixin, CommandHandler):
    """/subscribethreads.

    Автоподписка включается сама, когда бота добавляют в чат. Команда нужна
    для чатов, где бот сидел ещё до появления этой возможности, и чтобы
    подписку можно было снять.
    """

    commands: ClassVar[list[str]] = ["subscribethreads"]
    description = "/subscribethreads [off] - Подписать бота на обсуждения текущего чата"

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        args = (event.payload.text or "").split()[1:]
        enable = not (args and args[0].lower() in OFF_ARGS)
        chat_id = event.payload.chat.chatId

        ok = await set_thread_autosubscribe(bot, chat_id, enable=enable)

        if ok:
            async with async_session() as session:
                await emit(
                    session,
                    EventType.THREAD_AUTOSUBSCRIBE_CHANGED,
                    actor=Actor.from_event(event),
                    chat_id=chat_id,
                    entity=(EntityType.CHAT, chat_id),
                    payload={"enabled": "включена" if enable else "выключена"},
                )
                await session.commit()

        who = mention(event.payload.sender.userId)
        if not ok:
            await bot.send_text(
                chat_id,
                f"{who}, не удалось изменить подписку на обсуждения этого чата.",
            )
            return
        if enable:
            await bot.send_text(
                chat_id,
                f"{who}, подписался на обсуждения этого чата, включая существующие.",
            )
        else:
            await bot.send_text(
                chat_id, f"{who}, больше не подписываюсь на обсуждения этого чата."
            )
