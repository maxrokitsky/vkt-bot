import logging

from bot_framework.bot.types import Event, NewMessageEvent
from bot_framework.db.session import async_session
from bot_framework.middleware import Middleware
from bot_framework.repository import NotFoundError
from teams_bot.app import dispatcher
from teams_bot.repositories.chat import ChatRepository, CreateChatSchema

logger = logging.getLogger('teams_bot')


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
                logger.info("First event from chat %s. Created chat in database.", event.payload.chat.chatId)
