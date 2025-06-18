import json
import logging
from typing import ClassVar

from pydantic import TypeAdapter

from bot_framework.bot.client import VkTeamsBot
from bot_framework.bot.types import CallbackQueryEvent, NewMessageEvent
from bot_framework.handlers import BotButtonCommandHandler, CommandHandler
from teams_bot.app import dispatcher

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

Команды администратора (требуется роль `admin`)
/createrole `названиероли` - создать новую роль
/deleterole `названиероли` - удалить роль
/assignrole `idпользователя` `названиероли` - Назначить роль пользователю
/revokerole `idпользователя` `названиероли` - Отозвать роль у пользователя
"""


@dispatcher.register_handler
class HelpHandler(CommandHandler):
    """/help."""

    commands: ClassVar[list[str]] = ["help"]
    description = "/help - Описание бота и команд"

    async def callback(self, bot: VkTeamsBot, event: NewMessageEvent) -> None:
        await bot.send_text(
            event.payload.chat.chatId,
            help_msg,
            parse_mode="MarkdownV2",
        )


start_msg = """
Привет! Я бот 🤖Ассистент. Управляю ролями и стремлюсь к большему 🚀

Вот что я умею:
- *Управление ролями* - я могу создавать и удалять роли, назначать роли пользователям.
- *Призывать пользователей по роли* - если ты упомянешь роль с помощью хештега `#названиероли`, то я перешлю твоё сообщение всем пользователям с этой ролью, чтобы они обратили внимание.

⚠️ Бот находится в стадии активной разработки.

Версия: 0.1
by max@rokitsky.ru
"""  # noqa: E501


@dispatcher.register_handler
class StartHandler(CommandHandler):
    """/start."""

    commands: ClassVar[list[str]] = ["start"]
    description = "/start - Приветственное сообщение."

    async def callback(self, bot: VkTeamsBot, event: NewMessageEvent) -> None:
        await bot.send_text(
            event.payload.chat.chatId,
            start_msg,
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
    async def callback(self, bot: VkTeamsBot, event: CallbackQueryEvent) -> None:
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
