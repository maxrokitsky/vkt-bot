import logging
from typing import ClassVar
from urllib.parse import urljoin
import uuid
from bot_framework.exceptions import NotFoundError
from gitlab_plugin.models import GlWebhook
from gitlab_plugin.queries import GlWebhookByChatId
from teams_bot.config import settings

from bot_framework.bot.client import VkTeamsBot
from bot_framework.bot.types import NewMessageEvent
from bot_framework.db.session import async_session
from bot_framework.handlers import (
    CommandHandler,
)
from core.security import get_password_hash, get_random_string
from gitlab_plugin.repositories import CreateGlWebhookSchema, GlWebhookRepository
from teams_bot.app import dispatcher
from teams_bot.handlers.mixins import AdminRequiredMixin
from teams_bot.utils import mention
from utils.datetime import localize_datetime

logger = logging.getLogger("teams_bot.handlers.roles")


@dispatcher.register_handler
class CreateGlWebhook(AdminRequiredMixin, CommandHandler):
    """/glwebhookadd"""

    commands: ClassVar[list[str]] = ["glwebhookadd"]

    async def callback(self, bot: VkTeamsBot, event: NewMessageEvent):
        if not event.payload.text:
            return

        user_id = event.payload.sender.userId
        chat_id = event.payload.chat.chatId

        args = event.payload.text.split(" ", maxsplit=1)[1:]
        name = args[0] if args else None

        if not name:
            await bot.send_text(
                chat_id,
                f"{mention(user_id)}, укажите название вебхука.\n\n/glwebhookadd Название вебхука",
            )
            return

        webhook_id = uuid.uuid4()
        webhook_url = urljoin(settings.public_url, f"/gl/webhooks/{webhook_id}")
        secret = get_random_string()
        async with async_session() as session:
            gl_webhook_repository = GlWebhookRepository(session)
            await gl_webhook_repository.create(
                CreateGlWebhookSchema(
                    id=webhook_id,
                    name=name,
                    chat_id=chat_id,
                    created_by_id=user_id,
                    hashed_secret=get_password_hash(secret),
                ),
                commit=True,
            )
        lines = [
            "Перейдите в настройки проекта › Веб-обработчики › Add new webhook",
            f"Название: {name}",
            f"URL: {webhook_url}",
            f"Secret token: {secret}",
            "Триггер: События сборочной линии",
        ]
        await bot.send_text(
            chat_id,
            f"{mention(user_id)}, вебхук для Gitlab создан.\n{'\n'.join(lines)}",
        )
        return


@dispatcher.register_handler
class DeleteGlWebhookHandler(AdminRequiredMixin, CommandHandler):
    """/glwebhookdel."""

    commands: ClassVar[list[str]] = ["glwebhookdel"]

    async def callback(self, bot: VkTeamsBot, event: NewMessageEvent) -> None:
        """/glwebhookdel."""
        if not event.payload.text:
            return
        args = event.payload.text.split(" ")[1:]
        webhook_id = args[0]

        async with async_session() as session:
            webhook_repository = GlWebhookRepository(session)
            try:
                webhook = await webhook_repository.get(webhook_id)
            except NotFoundError:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(event.payload.sender.userId)}, вебхук {webhook_id} не существует.",
                )
                return

            if webhook.chat_id != event.payload.chat.chatId:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(event.payload.sender.userId)}, вебхук {webhook_id} зарегестрирован в другом чате.",
                )
                return

            await session.delete(webhook)
            await session.commit()
        await bot.send_text(
            event.payload.chat.chatId,
            f"{mention(event.payload.sender.userId)}, вебхук {webhook_id} удалён.",
        )


@dispatcher.register_handler
class ListGlWebhooksHandler(CommandHandler):
    """/glwebhookls."""

    commands: ClassVar[list[str]] = ["glwebhookls"]

    async def callback(self, bot: VkTeamsBot, event: NewMessageEvent) -> None:
        """/glwebhookls."""
        if not event.payload.text:
            return

        async with async_session() as session:
            webhook_repository = GlWebhookRepository(session)
            webhooks = await webhook_repository.query(
                GlWebhookByChatId(chat_id=event.payload.chat.chatId)
            ).list()
            message = "в этом чате не зарегистрировано ни одного вебхука"
            if webhooks:
                lines = map(self._format_webhook, webhooks)
                message = f"вебхуки для этого чата:\n{'\n\n'.join(lines)}"

            await bot.send_text(
                event.payload.chat.chatId,
                f"{mention(event.payload.sender.userId)}, {message}",
            )
            return

    def _format_webhook(self, webhook: GlWebhook) -> str:
        last_used_at = (
            f"последний вызов {localize_datetime(webhook.last_used_at)}"
            if webhook.last_used_at
            else "не использовано"
        )
        return f"{webhook.id}\n{webhook.name} ({last_used_at})"
