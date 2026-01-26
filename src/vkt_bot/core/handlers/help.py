import json
import logging
from typing import ClassVar

from pydantic import TypeAdapter

from vkteams_client import VKTeams
from vkteams_client.types import CallbackQueryEvent, NewMessageEvent
from vkt_dispatcher.handlers import BotButtonCommandHandler, CommandHandler
from vkt_bot.app import dispatcher
from vkt_bot.db.session import async_session
from vkt_bot.core.repositories.bot_settings import BotSettingsRepository
from vkt_bot.core.constants import DEFAULT_START_MESSAGE

from .callback import CallbackData, ShowCommandsCallbackData

logger = logging.getLogger("teams_bot.handlers.roles")


help_msg = """
Вот мои команды:

/start - показать приветственное сообщение
/stop - отключить чат с ботом
/help - описание бота и команд

Роли
/listroles - список всех ролей
/listroles `idпользователя` - список ролей пользователя
/listrolemembers `названиероли` - список пользователей с указанной ролью

Вебхуки
/listwebhooks - список вебхуков текущего чата
/webhookinfo `id-вебхука` - информация о вебхуке

Команды администратора (требуется роль `admin`)
/createrole `названиероли` - создать новую роль
/deleterole `названиероли` - удалить роль
/assignrole `id-пользователя` `названиероли` - Назначить роль пользователю
/revokerole `id-пользователя` `названиероли` - Отозвать роль у пользователя

/createwebhook `название` - создать вебхук для текущего чата
/deletewebhook `id-вебхука` - удалить вебхук
/regeneratewebhookkey `id-вебхука` - перегенерировать API ключ вебхука
/togglewebhook `id-вебхука` - включить/выключить вебхук
"""


@dispatcher.register_handler
class HelpHandler(CommandHandler):
    """/help."""

    commands: ClassVar[list[str]] = ["help"]
    description = "/help - Описание бота и команд"

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        await bot.send_text(
            event.payload.chat.chatId,
            help_msg,
            parse_mode="MarkdownV2",
        )


@dispatcher.register_handler
class StartHandler(CommandHandler):
    """/start."""

    commands: ClassVar[list[str]] = ["start"]
    description = "/start - Приветственное сообщение."

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        async with async_session() as session:
            repo = BotSettingsRepository(session)
            settings = await repo.get_by_key("start_message")
            message_text = settings.value if settings else DEFAULT_START_MESSAGE

        await bot.send_text(
            event.payload.chat.chatId,
            message_text,
            parse_mode="MarkdownV2",
            inline_keyboard_markup="[{}]".format(
                json.dumps(
                    [
                        {
                            "text": "Показать команды",
                            "callbackData": ShowCommandsCallbackData(
                                requested_by=event.payload.sender.userId,
                            ).model_dump_json(),
                        },
                    ]
                )
            ),
        )


@dispatcher.register_handler
class DeleteRoleConfirmation(BotButtonCommandHandler):
    async def callback(self, bot: VKTeams, event: CallbackQueryEvent) -> None:
        ta: TypeAdapter[CallbackData] = TypeAdapter(CallbackData)
        data = ta.validate_json(event.payload.callbackData)

        if not isinstance(data, ShowCommandsCallbackData):
            return

        await bot.send_text(
            event.payload.message.chat.chatId,
            help_msg,
            parse_mode="MarkdownV2",
        )
        await bot.answer_callback_query(query_id=event.payload.queryId)
