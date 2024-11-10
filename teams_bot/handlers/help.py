import json
import logging
from typing import ClassVar

import sqlalchemy as sa

from bot_framework.bot.client import VkTeamsBot
from bot_framework.bot.types import NewMessageEvent
from bot_framework.db.session import async_session
from bot_framework.handlers import CommandHandler
from bot_framework.repository import NotFoundError
from teams_bot.app import dispatcher
from teams_bot.models.role import RoleAssignment
from teams_bot.repositories.role import RoleRepository

logger = logging.getLogger('teams_bot.handlers.roles')


msg = """
/help - описание бота и команд

Роли
/listroles - список всех ролей
/listroles `idпользователя` - список ролей пользователя

Команды администратора:
/createrole `названиероли` - создать новую роль
/deleterole `названиероли` - удалить роль
/assignrole `idпользователя` `названиероли` - Назначить роль пользователю
/revokerole `idпользователя` `названиероли` - Отозвать роль у пользователя
"""


@dispatcher.register_handler
class HelpHandler(CommandHandler):
    """/help."""

    commands: ClassVar[list[str]] = ['help']
    description = '/help - Описание бота и команд'

    async def callback(self, bot: VkTeamsBot, event: NewMessageEvent) -> None:
        await bot.send_text(
            event.payload.chat.chatId,
            msg,
            parse_mode='MarkdownV2',
        )
