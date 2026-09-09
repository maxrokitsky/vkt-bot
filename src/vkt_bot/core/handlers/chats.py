import logging

from vkteams_client import VKTeams
from vkteams_client.types import (
    Bot,
    ChangedChatInfoEvent,
    Event,
    LeftChatMembersEvent,
    NewChatMembersEvent,
    NewMessageEvent,
)
from vkt_bot.db.session import async_session
from vkt_dispatcher.handlers import (
    ChangedChatInfoHandler,
    LeftChatMembersHandler,
    NewChatMembersHandler,
)
from vkt_dispatcher.middleware import Middleware
from vkt_bot.core.repositories.chat import ChatMembershipRepository, ChatRepository
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.app import dispatcher

logger = logging.getLogger("vkt_bot")


@dispatcher.register_middleware
class CreateChatMiddleware(Middleware):
    async def on_event(self, event: Event) -> None:
        if not isinstance(event, NewMessageEvent):
            return
        async with async_session() as session:
            chat_repository = ChatRepository(session)
            known = await chat_repository.exists(event.payload.chat.chatId)
            await chat_repository.upsert(event.payload.chat)
            # Сообщения — самый частый источник имён.
            await ChatUserRepository(session).update_profile(event.payload.sender)
            await session.commit()
            if not known:
                logger.info(
                    "First event from chat %s. Created chat in database.",
                    event.payload.chat.chatId,
                )


@dispatcher.register_handler
class ChatMembersJoinedHandler(NewChatMembersHandler):
    """Регистрирует чат и его участников при добавлении в чат."""

    async def callback(self, bot: VKTeams, event: NewChatMembersEvent) -> None:
        payload = event.payload
        chat_id = payload.chat.chatId

        # ``getMembers`` отдаёт только ``userId`` — бота там не отличить.
        # Единственный надёжный источник — событие, где боты приходят
        # отдельным типом.
        bots = {m.userId for m in payload.newMembers if isinstance(m, Bot)}

        # Бота добавили в чат: остальные участники были там до нас,
        # событий по ним не будет — забираем состав у API.
        roster = await self.fetch_roster(bot, chat_id) if bots else []

        joined = [m.userId for m in payload.newMembers]
        members = list(dict.fromkeys(joined + roster))

        async with async_session() as session:
            chats = ChatRepository(session)
            users = ChatUserRepository(session)
            memberships = ChatMembershipRepository(session)

            await chats.upsert(payload.chat)

            named = {m.userId: m for m in payload.newMembers}
            for user_id in members:
                member = named.get(user_id)
                if member is not None:
                    await users.sync_profile(member)
                else:
                    # Из ростера приходит голый id — имя подтянется из события.
                    await users.get_or_create(user_id)
                await memberships.add(chat_id, user_id)

            await session.commit()

        if bots:
            logger.info(
                "Bot added to chat %s. Registered chat and %s member(s).",
                chat_id,
                len(members),
            )

    async def fetch_roster(self, bot: VKTeams, chat_id: str) -> list[str]:
        """Состав чата по данным API. Ошибка не должна ронять обработчик."""
        try:
            response = await bot.get_members(chat_id=chat_id)
        except Exception:
            logger.exception("Failed to fetch members of chat %s", chat_id)
            return []
        if response is None:
            return []
        return [member.userId for member in response.members]


@dispatcher.register_handler
class ChatMembersLeftHandler(LeftChatMembersHandler):
    """Снимает членство, когда участники покидают чат."""

    async def callback(self, bot: VKTeams, event: LeftChatMembersEvent) -> None:
        payload = event.payload
        chat_id = payload.chat.chatId

        async with async_session() as session:
            memberships = ChatMembershipRepository(session)
            for member in payload.leftMembers:
                await memberships.remove(chat_id, member.userId)
            await session.commit()

        if any(isinstance(member, Bot) for member in payload.leftMembers):
            logger.info("Bot removed from chat %s.", chat_id)


@dispatcher.register_handler
class ChatInfoChangedHandler(ChangedChatInfoHandler):
    """Обновляет название чата."""

    async def callback(self, bot: VKTeams, event: ChangedChatInfoEvent) -> None:
        async with async_session() as session:
            await ChatRepository(session).upsert(
                event.payload.chat, title=event.payload.title
            )
            await session.commit()
