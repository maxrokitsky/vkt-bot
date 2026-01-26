import json
import logging
from typing import ClassVar

from vkteams_client import VKTeams
from vkteams_client.types import CallbackQueryEvent, NewMessageEvent
from vkt_bot.config import settings
from vkt_bot.db.session import async_session
from vkt_dispatcher.handlers import (
    BotButtonCommandHandler,
    CommandHandler,
)
from vkt_bot.db.repository import NotFoundError
from vkt_bot.core.repositories.webhook import WebhookRepository
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.app import dispatcher
from vkt_bot.core.handlers.callback import CallbackData, WebhookCallbackData
from vkt_bot.core.handlers.mixins import AdminRequiredMixin
from vkt_bot.utils.message import mention

logger = logging.getLogger("teams_bot.handlers.webhooks")


@dispatcher.register_handler
class CreateWebhookHandler(AdminRequiredMixin, CommandHandler):
    """/createwebhook."""

    commands: ClassVar[list[str]] = ["createwebhook"]
    description = "/createwebhook название - Создать вебхук для текущего чата"

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        args = event.payload.text.split(" ")[1:]
        if not args:
            await bot.send_text(
                event.payload.chat.chatId,
                f"{mention(event.payload.sender.userId)}, укажите название вебхука.\n"
                f"Пример: /createwebhook Мои уведомления",
            )
            return

        webhook_name = " ".join(args)
        chat_id = event.payload.chat.chatId
        user_id = event.payload.sender.userId

        async with async_session() as session:
            webhook_repository = WebhookRepository(session)
            user_repository = ChatUserRepository(session)

            # Проверяем, существует ли уже вебхук с таким именем в этом чате
            existing_webhooks = await webhook_repository.list_by_chat(chat_id)
            for webhook in existing_webhooks:
                if webhook.name.lower() == webhook_name.lower():
                    await bot.send_text(
                        event.payload.chat.chatId,
                        f"{mention(user_id)}, вебхук с названием '{webhook_name}' уже существует в этом чате.",
                    )
                    return

            # Создаем пользователя если не существует
            await user_repository.get_or_create(user_id)

            # Создаем вебхук
            from vkt_bot.webapp.schemas.webhook import WebhookCreateSchema

            webhook_data = WebhookCreateSchema(
                name=webhook_name, chat_id=chat_id, webhook_metadata={}
            )

            webhook, api_key = await webhook_repository.create_with_api_key(
                webhook_data, creator_id=user_id
            )

            await session.commit()

        # Формируем URL вебхука
        base_url = settings.public_url or "http://localhost:8765"
        webhook_url = f"{base_url}/api/webhooks/{webhook.id}/send"

        await bot.send_text(
            event.payload.chat.chatId,
            f"{mention(user_id)}, вебхук '{webhook_name}' создан!\n\n"
            f"📝 **ID вебхука:** `{webhook.id}`\n"
            f"🔑 **API ключ:** `{api_key}`\n"
            f"🌐 **URL для отправки:** `{webhook_url}`\n\n"
            f"⚠️ **Сохраните API ключ!** Он показывается только один раз.\n"
            f"Для отправки сообщений используйте POST запрос с заголовком:\n"
            f"`Authorization: Bearer {api_key}`",
            parse_mode="MarkdownV2",
        )


@dispatcher.register_handler
class ListWebhooksHandler(CommandHandler):
    """/listwebhooks."""

    commands: ClassVar[list[str]] = ["listwebhooks"]
    description = "/listwebhooks - Показать список вебхуков текущего чата"

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        chat_id = event.payload.chat.chatId
        user_id = event.payload.sender.userId

        async with async_session() as session:
            webhook_repository = WebhookRepository(session)
            webhooks = await webhook_repository.list_by_chat(chat_id)

        if not webhooks:
            await bot.send_text(
                event.payload.chat.chatId,
                f"{mention(user_id)}, в этом чате нет вебхуков.\n"
                f"Создайте вебхук командой /createwebhook",
            )
            return

        webhook_list = []
        for i, webhook in enumerate(webhooks, 1):
            status = "✅" if webhook.is_active else "❌"
            webhook_list.append(
                f"{i}. {status} **{webhook.name}**\n"
                f"   ID: `{webhook.id}`\n"
                f"   Создан: {webhook.created_at.strftime('%d.%m.%Y %H:%M')}\n"
                f"   Создатель: {mention(webhook.created_by)}"
            )

        await bot.send_text(
            event.payload.chat.chatId,
            f"{mention(user_id)}, вебхуки в этом чате:\n\n" + "\n\n".join(webhook_list),
            parse_mode="MarkdownV2",
        )


@dispatcher.register_handler
class DeleteWebhookHandler(AdminRequiredMixin, CommandHandler):
    """/deletewebhook."""

    commands: ClassVar[list[str]] = ["deletewebhook"]
    description = "/deletewebhook ID_вебхука - Удалить вебхук"

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        args = event.payload.text.split(" ")[1:]
        if not args:
            await bot.send_text(
                event.payload.chat.chatId,
                f"{mention(event.payload.sender.userId)}, укажите ID вебхука.\n"
                f"Пример: /deletewebhook abc123-def456",
            )
            return

        webhook_id = args[0]
        user_id = event.payload.sender.userId
        chat_id = event.payload.chat.chatId

        async with async_session() as session:
            webhook_repository = WebhookRepository(session)
            try:
                webhook = await webhook_repository.get(webhook_id)
            except NotFoundError:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(user_id)}, вебхук с ID '{webhook_id}' не найден.",
                )
                return

            # Проверяем, что вебхук принадлежит текущему чату
            if webhook.chat_id != chat_id:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(user_id)}, этот вебхук не принадлежит текущему чату.",
                )
                return

            # Запрашиваем подтверждение
            await bot.send_text(
                event.payload.chat.chatId,
                f"Вы уверены, что хотите удалить вебхук '{webhook.name}'?\n\n"
                f"📝 **ID:** `{webhook.id}`\n"
                f"📅 **Создан:** {webhook.created_at.strftime('%d.%m.%Y %H:%M')}\n\n"
                f"После удаления восстановить вебхук будет невозможно.",
                parse_mode="MarkdownV2",
                inline_keyboard_markup="[{}]".format(
                    json.dumps(
                        [
                            {
                                "text": f"Удалить вебхук '{webhook.name}'",
                                "callbackData": WebhookCallbackData(
                                    command="deletewebhook",
                                    webhook_id=webhook.id,
                                    webhook_name=webhook.name,
                                    requested_by=user_id,
                                ).model_dump_json(),
                                "style": "attention",
                            },
                        ]
                    )
                ),
            )


@dispatcher.register_handler
class RegenerateWebhookKeyHandler(AdminRequiredMixin, CommandHandler):
    """/regeneratewebhookkey."""

    commands: ClassVar[list[str]] = ["regeneratewebhookkey"]
    description = "/regeneratewebhookkey ID_вебхука - Перегенерировать API ключ вебхука"

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        args = event.payload.text.split(" ")[1:]
        if not args:
            await bot.send_text(
                event.payload.chat.chatId,
                f"{mention(event.payload.sender.userId)}, укажите ID вебхука.\n"
                f"Пример: /regeneratewebhookkey abc123-def456",
            )
            return

        webhook_id = args[0]
        user_id = event.payload.sender.userId
        chat_id = event.payload.chat.chatId

        async with async_session() as session:
            webhook_repository = WebhookRepository(session)
            try:
                webhook = await webhook_repository.get(webhook_id)
            except NotFoundError:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(user_id)}, вебхук с ID '{webhook_id}' не найден.",
                )
                return

            # Проверяем, что вебхук принадлежит текущему чату
            if webhook.chat_id != chat_id:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(user_id)}, этот вебхук не принадлежит текущему чату.",
                )
                return

            # Запрашиваем подтверждение
            await bot.send_text(
                event.payload.chat.chatId,
                f"Вы уверены, что хотите перегенерировать API ключ для вебхука '{webhook.name}'?\n\n"
                f"⚠️ **Старый ключ перестанет работать!**\n"
                f"Все интеграции, использующие старый ключ, нужно будет обновить.",
                parse_mode="MarkdownV2",
                inline_keyboard_markup="[{}]".format(
                    json.dumps(
                        [
                            {
                                "text": f"Перегенерировать ключ '{webhook.name}'",
                                "callbackData": WebhookCallbackData(
                                    command="regeneratewebhookkey",
                                    webhook_id=webhook.id,
                                    webhook_name=webhook.name,
                                    requested_by=user_id,
                                ).model_dump_json(),
                                "style": "attention",
                            },
                        ]
                    )
                ),
            )


@dispatcher.register_handler
class ToggleWebhookHandler(AdminRequiredMixin, CommandHandler):
    """/togglewebhook."""

    commands: ClassVar[list[str]] = ["togglewebhook"]
    description = "/togglewebhook ID_вебхука - Включить/выключить вебхук"

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        args = event.payload.text.split(" ")[1:]
        if not args:
            await bot.send_text(
                event.payload.chat.chatId,
                f"{mention(event.payload.sender.userId)}, укажите ID вебхука.\n"
                f"Пример: /togglewebhook abc123-def456",
            )
            return

        webhook_id = args[0]
        user_id = event.payload.sender.userId
        chat_id = event.payload.chat.chatId

        async with async_session() as session:
            webhook_repository = WebhookRepository(session)
            try:
                webhook = await webhook_repository.get(webhook_id)
            except NotFoundError:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(user_id)}, вебхук с ID '{webhook_id}' не найден.",
                )
                return

            # Проверяем, что вебхук принадлежит текущему чату
            if webhook.chat_id != chat_id:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(user_id)}, этот вебхук не принадлежит текущему чату.",
                )
                return

            # Обновляем статус
            from vkt_bot.webapp.schemas.webhook import WebhookUpdateSchema

            update_data = WebhookUpdateSchema(is_active=not webhook.is_active)
            updated_webhook = await webhook_repository.update(webhook_id, update_data)
            await session.commit()

            status = "включен" if updated_webhook.is_active else "выключен"
            await bot.send_text(
                event.payload.chat.chatId,
                f"{mention(user_id)}, вебхук '{webhook.name}' {status}.",
            )


@dispatcher.register_handler
class WebhookInfoHandler(CommandHandler):
    """/webhookinfo."""

    commands: ClassVar[list[str]] = ["webhookinfo"]
    description = "/webhookinfo ID_вебхука - Показать информацию о вебхуке"

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        args = event.payload.text.split(" ")[1:]
        if not args:
            await bot.send_text(
                event.payload.chat.chatId,
                f"{mention(event.payload.sender.userId)}, укажите ID вебхука.\n"
                f"Пример: /webhookinfo abc123-def456",
            )
            return

        webhook_id = args[0]
        user_id = event.payload.sender.userId
        chat_id = event.payload.chat.chatId

        async with async_session() as session:
            webhook_repository = WebhookRepository(session)
            try:
                webhook = await webhook_repository.get(webhook_id)
            except NotFoundError:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(user_id)}, вебхук с ID '{webhook_id}' не найден.",
                )
                return

            # Проверяем, что вебхук принадлежит текущему чату
            if webhook.chat_id != chat_id:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(user_id)}, этот вебхук не принадлежит текущему чату.",
                )
                return

            # Формируем URL вебхука
            base_url = settings.public_url or "http://localhost:8765"
            webhook_url = f"{base_url}/api/webhooks/{webhook.id}/send"

            status = "✅ Активен" if webhook.is_active else "❌ Неактивен"
            metadata = json.dumps(
                webhook.webhook_metadata, indent=2, ensure_ascii=False
            )

            await bot.send_text(
                event.payload.chat.chatId,
                f"📋 **Информация о вебхуке**\n\n"
                f"📝 **Название:** {webhook.name}\n"
                f"🆔 **ID:** `{webhook.id}`\n"
                f"💬 **Чат:** {mention(webhook.chat_id)}\n"
                f"👤 **Создатель:** {mention(webhook.created_by)}\n"
                f"📅 **Создан:** {webhook.created_at.strftime('%d.%m.%Y %H:%M:%S')}\n"
                f"🔄 **Обновлен:** {webhook.updated_at.strftime('%d.%m.%Y %H:%M:%S')}\n"
                f"⚡ **Статус:** {status}\n"
                f"🌐 **URL:** `{webhook_url}`\n\n"
                f"📊 **Метаданные:**\n```json\n{metadata}\n```",
                parse_mode="MarkdownV2",
            )


@dispatcher.register_handler
class WebhookConfirmationHandler(BotButtonCommandHandler):
    async def callback(self, bot: VKTeams, event: CallbackQueryEvent) -> None:
        from pydantic import TypeAdapter

        ta: TypeAdapter[CallbackData] = TypeAdapter(CallbackData)
        data = ta.validate_json(event.payload.callbackData)

        if not isinstance(data, WebhookCallbackData):
            return

        if event.payload.sender.userId != data.requested_by:
            await bot.answer_callback_query(
                query_id=event.payload.queryId,
                text="Подтвердить может только тот, кто запросил операцию.",
                show_alert=True,
            )
            return

        async with async_session() as session:
            webhook_repository = WebhookRepository(session)

            try:
                webhook = await webhook_repository.get(data.webhook_id)
            except NotFoundError:
                await bot.answer_callback_query(
                    query_id=event.payload.queryId,
                    text=f"❌ Вебхук '{data.webhook_name}' уже не существует.",
                    show_alert=True,
                )
                return

            if data.command == "deletewebhook":
                await session.delete(webhook)
                await session.commit()

                await bot.answer_callback_query(
                    query_id=event.payload.queryId,
                    text=f"Вебхук '{data.webhook_name}' удален.",
                )
                await bot.edit_text(
                    chat_id=event.payload.message.chat.chatId,
                    msg_id=event.payload.message.msgId,
                    text=f"{mention(event.payload.sender.userId)}, вебхук '{data.webhook_name}' удален.",
                )

            elif data.command == "regeneratewebhookkey":
                (
                    updated_webhook,
                    new_api_key,
                ) = await webhook_repository.regenerate_api_key(data.webhook_id)
                await session.commit()

                base_url = settings.public_url or "http://localhost:8765"
                webhook_url = f"{base_url}/api/webhooks/{updated_webhook.id}/send"

                await bot.answer_callback_query(
                    query_id=event.payload.queryId,
                    text=f"API ключ для вебхука '{data.webhook_name}' перегенерирован.",
                )
                await bot.edit_text(
                    chat_id=event.payload.message.chat.chatId,
                    msg_id=event.payload.message.msgId,
                    text=f"{mention(event.payload.sender.userId)}, API ключ для вебхука '{data.webhook_name}' перегенерирован!\n\n"
                    f"🔑 **Новый API ключ:** `{new_api_key}`\n"
                    f"🌐 **URL для отправки:** `{webhook_url}`\n\n"
                    f"⚠️ **Сохраните новый ключ!** Старый ключ больше не работает.\n"
                    f"Для отправки сообщений используйте POST запрос с заголовком:\n"
                    f"`Authorization: Bearer {new_api_key}`",
                    parse_mode="MarkdownV2",
                )
