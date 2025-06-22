import logging

from vkteams_client.types import Event, NewMessageEvent
from vkt_bot.db.session import async_session
from vkt_dispatcher.middleware import Middleware
from vkt_bot.core.repositories.chat import ChatRepository, CreateChatSchema
from vkt_bot.app import dispatcher

logger = logging.getLogger("vkt_bot")


@dispatcher.register_middleware
class CreateChatMiddleware(Middleware):
    async def on_event(self, event: Event) -> None:
        if not isinstance(event, NewMessageEvent):
            return
        async with async_session() as session:
            chat_repository = ChatRepository(session)
            if not await chat_repository.exists(event.payload.chat.chatId):
                await chat_repository.create(
                    CreateChatSchema(
                        id=event.payload.chat.chatId,
                        type=event.payload.chat.type,
                    ),
                    commit=True,
                )
                logger.info(
                    "First event from chat %s. Created chat in database.",
                    event.payload.chat.chatId,
                )
