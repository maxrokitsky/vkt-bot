import logging
from typing import ClassVar

from vkteams_client import VKTeams
from vkteams_client.types import NewMessageEvent
from vkt_bot.app import dispatcher
from vkt_bot.config import settings
from vkt_bot.core.repositories.login_token import LoginTokenRepository
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.db.session import async_session
from vkt_bot.utils.message import mention
from vkt_dispatcher.handlers import CommandHandler

logger = logging.getLogger(__name__)


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

            await user_repo.get_or_create(user_id)

            login_token = await token_repo.create_token(user_id, expires_minutes=5)
            await session.commit()
            logger.info("Created login token for user %s: %s... (id=%s)", user_id, login_token.token[:10], login_token.id)

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
            parse_mode="MarkdownV2",
        )
