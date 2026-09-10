from typing import ClassVar

import structlog

from vkteams_client import VKTeams
from vkteams_client.types import NewMessageEvent
from vkt_bot.app import dispatcher
from vkt_bot.config import settings
from vkt_bot.core.events import Actor, EventType, emit
from vkt_bot.core.models.event import EntityType
from vkt_bot.core.repositories.login_token import LoginTokenRepository
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.core.security import is_owner
from vkt_bot.db.session import async_session
from vkt_bot.utils.message import mention
from vkt_dispatcher.handlers import CommandHandler

logger = structlog.get_logger("vkt_bot.handlers.auth")


@dispatcher.register_handler
class LoginHandler(CommandHandler):
    """/login - Получить ссылку для входа в веб-панель."""

    commands: ClassVar[list[str]] = ["login"]
    description = "/login - Получить ссылку для входа в веб-панель"

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        user_id = event.payload.sender.userId

        async with async_session() as session:
            user_repo = ChatUserRepository(session)
            token_repo = LoginTokenRepository(session)

            user = await user_repo.sync_profile(event.payload.sender)

            # Владелец бота — админ по определению; закрепляем это в базе,
            # чтобы права не зависели от текущего значения OWNER_ID.
            if is_owner(user_id) and not user.is_superuser:
                await user_repo.grant_superuser(user)
                await emit(
                    session,
                    EventType.AUTH_SUPERUSER_GRANTED,
                    actor=Actor.from_event(event),
                    entity=(EntityType.CHAT_USER, user_id),
                    summary=("Владелец получил права администратора при входе"),
                )
                logger.info("auth.superuser_granted", user_id=user_id)

            login_token = await token_repo.create_token(user_id, expires_minutes=5)
            await session.commit()
            # В лог идёт id строки, а не сам токен: одноразовый он или
            # нет, в журнале ему не место.
            logger.info(
                "auth.login_token_created",
                user_id=user_id,
                login_token_id=str(login_token.id),
            )

        if settings.public_url:
            login_url = f"{settings.public_url}/login?token={login_token.token}"
            message = (
                f"Ссылка для входа (действительна 5 минут):\n"
                f"{login_url}\n\n"
                f"Или введите токен вручную на странице {settings.public_url}/login:\n`{login_token.token}`"
            )
        else:
            message = (
                f"{mention(user_id)}, токен для входа (действителен 5 минут):\n"
                f"`{login_token.token}`\n\n"
                f"Введите его на странице входа в веб-панель."
            )

        await bot.send_text(
            chat_id=event.payload.chat.chatId,
            text=message,
        )
