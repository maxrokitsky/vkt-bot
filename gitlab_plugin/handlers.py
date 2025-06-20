import logging
from typing import ClassVar
from urllib.parse import urljoin
import uuid
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

logger = logging.getLogger("teams_bot.handlers.roles")


@dispatcher.register_handler
class CreateGlWebhook(AdminRequiredMixin, CommandHandler):
    """/gl webhook add"""

    commands: ClassVar[list[str]] = ["glwebhookadd"]

    async def callback(self, bot: VkTeamsBot, event: NewMessageEvent):
        if not event.payload.text:
            return

        user_id = event.payload.sender.userId
        chat_id = event.payload.chat.chatId
        # if not event.payload.chat.type == ChatType.GROUP:
        #     msg = (
        #         f"{mention(user_id)}, пока что вебхук можно создать только в группе.",
        #     )
        #     await bot.send_text(chat_id, msg)
        #     return

        webhook_id = uuid.uuid4()
        webhook_url = urljoin(settings.public_url, f"/gl/webhooks/{webhook_id}")
        secret = get_random_string()
        async with async_session() as session:
            gl_webhook_repository = GlWebhookRepository(session)
            await gl_webhook_repository.create(
                CreateGlWebhookSchema(
                    id=webhook_id,
                    chat_id=chat_id,
                    created_by_id=user_id,
                    hashed_secret=get_password_hash(secret),
                ),
                commit=True,
            )
        await bot.send_text(
            chat_id,
            f"{mention(user_id)}, вебхук для Gitlab создан.\nURL: {webhook_url}\nSecret token: {secret}\nТриггер: События сборочной линии",
        )
        return


# @dispatcher.register_handler
# class CreateRoleHandler(AdminRequiredMixin, CommandHandler):
#     """/createrole."""

#     commands: ClassVar[list[str]] = ['createrole']

#     async def callback(self, bot: VkTeamsBot, event: NewMessageEvent) -> None:
#         """/createrole."""
#         if not event.payload.text:
#             return
#         args = event.payload.text.split(' ')[1:]
#         role_name = args[0]

#         async with async_session() as session:
#             role_repository = RoleRepository(session)
#             try:
#                 await role_repository.get_by_name(role_name)
#             except NotFoundError:
#                 pass
#             else:
#                 await bot.send_text(
#                     event.payload.chat.chatId,
#                     f'{mention(event.payload.sender.userId)}, роль {role_name} уже существует.',
#                 )
#                 return

#             await role_repository.create(CreateRoleSchema(name=role_name), commit=True)
#         await bot.send_text(
#             event.payload.chat.chatId, f'{mention(event.payload.sender.userId)}, роль {role_name} добавлена'
#         )


# @dispatcher.register_handler
# class DeleteRoleHandler(AdminRequiredMixin, CommandHandler):
#     """/deleterole."""

#     commands: ClassVar[list[str]] = ['deleterole']

#     async def callback(self, bot: VkTeamsBot, event: NewMessageEvent) -> None:
#         """/deleterole."""
#         if not event.payload.text:
#             return
#         args = event.payload.text.split(' ')[1:]
#         role_name = args[0]
#         if role_name.lower() in ['admin', 'botowner']:
#             await bot.send_text(
#                 event.payload.chat.chatId, f'{mention(event.payload.sender.userId)}, роль {role_name} нельзя удалить.'
#             )
#             return

#         async with async_session() as session:
#             role_repository = RoleRepository(session)
#             try:
#                 role = await role_repository.get_by_name(role_name)
#             except NotFoundError:
#                 await bot.send_text(
#                     event.payload.chat.chatId,
#                     f'{mention(event.payload.sender.userId)}, роль {role_name} не существует.',
#                 )
#                 return

#             role_assignment_repository = RoleAssignmentRepository(session)
#             assignments = await role_assignment_repository.query(
#                 RoleAssignmentByUserAndRoleQuery(
#                     role_id=role.id,
#                 )
#             ).list()
#             if assignments:
#                 await bot.send_text(
#                     event.payload.chat.chatId,
#                     f'Роль назначена {len(assignments)} пользователям.\n\n'
#                     f'Вы уверены, что хотите удалить роль {role.name}?',
#                     inline_keyboard_markup='[{}]'.format(
#                         json.dumps(
#                             [
#                                 {
#                                     'text': f'Удалить роль {role.name}',
#                                     'callbackData': DeleteRoleCallbackData(
#                                         command='deleterole',
#                                         role=role.name,
#                                         requested_by=event.payload.sender.userId,
#                                     ).model_dump_json(),
#                                     'style': 'attention',
#                                 },
#                             ]
#                         )
#                     ),
#                 )
#                 return
#             for assignment in assignments:
#                 await session.delete(assignment)
#             await session.delete(role)
#             await session.commit()
#         await bot.send_text(
#             event.payload.chat.chatId, f'{mention(event.payload.sender.userId)}, роль {role_name} удалена.'
#         )


# @dispatcher.register_handler
# class AssignRoleHandler(AdminRequiredMixin, CommandHandler):
#     """/assignrole."""

#     commands: ClassVar[list[str]] = ['assignrole']

#     async def callback(self, bot: VkTeamsBot, event: NewMessageEvent) -> None:
#         """/assignrole."""
#         if not event.payload.text:
#             return
#         args = event.payload.text.split(' ')[1:]
#         user_id = args[0]
#         role_name = args[1]

#         try:
#             async with async_session() as session:
#                 role_repository = RoleRepository(session)
#                 chat_user_repository = ChatUserRepository(session)
#                 try:
#                     role = await role_repository.get_by_name(role_name)
#                 except NotFoundError:
#                     await bot.send_text(
#                         event.payload.chat.chatId,
#                         f'{mention(event.payload.sender.userId)}, роль {role_name} не существует.',
#                     )
#                     return

#                 role_assignment_repository = RoleAssignmentRepository(session)

#                 if role_name.lower() == 'botowner':
#                     await bot.send_text(
#                         event.payload.chat.chatId,
#                         f'{mention(event.payload.sender.userId)}, роль {role_name} нельзя назначить.',
#                     )
#                     return

#                 if await role_assignment_repository.query(
#                     RoleAssignmentByUserAndRoleQuery(user_id=user_id, role_id=role.id)
#                 ).exists():
#                     await bot.send_text(
#                         event.payload.chat.chatId,
#                         f'{mention(event.payload.sender.userId)}, пользователю {user_id} уже назначена роль {role_name}.',
#                     )
#                     return
#                 try:
#                     await chat_user_repository.get(user_id)
#                 except NotFoundError:
#                     await chat_user_repository.create(CreateChatUserSchema(id=user_id))
#                 await role_assignment_repository.create(CreateRoleAssignmentSchema(role_id=role.id, user_id=user_id))
#                 await session.commit()
#         except Exception:
#             logger.exception('Ошибка наначения роли %s пользователю %s', role_name, user_id)
#             await bot.send_text(
#                 event.payload.chat.chatId, f'{mention(event.payload.sender.userId)}, ошибка при добавлении роли.'
#             )
#             return
#         await bot.send_text(
#             event.payload.chat.chatId,
#             f'{mention(event.payload.sender.userId)}, роль {role.name} назначена пользователю {user_id}.',
#         )
#         await bot.send_text(chat_id=user_id, text=f'Вам назначена роль "{role.name}"')


# @dispatcher.register_handler
# class RevokeRoleHandler(AdminRequiredMixin, CommandHandler):
#     """/revokerole."""

#     commands: ClassVar[list[str]] = ['revokerole']
#     description = '/revokerole id_пользователя роль - Отзывает роль у пользователя'

#     async def callback(self, bot: VkTeamsBot, event: NewMessageEvent) -> None:
#         """/revokerole."""
#         if not event.payload.text:
#             return
#         args = event.payload.text.split(' ')[1:]
#         user_id = args[0]
#         role_name = args[1]

#         try:
#             async with async_session() as session:
#                 try:
#                     role = await RoleRepository(session).get_by_name(role_name)
#                 except NotFoundError:
#                     await bot.send_text(
#                         event.payload.chat.chatId,
#                         f'{mention(event.payload.sender.userId)}, роль {role_name} не существует.',
#                     )
#                     return

#                 if role_name.lower() in ['botowner']:
#                     await bot.send_text(
#                         event.payload.chat.chatId,
#                         f'{mention(event.payload.sender.userId)}, роль {role_name} нельзя отозвать.',
#                     )
#                     return

#                 role_assignment_repository = RoleAssignmentRepository(session)
#                 role_assignment = await role_assignment_repository.query(
#                     RoleAssignmentByUserAndRoleQuery(user_id=user_id, role_id=role.id)
#                 ).one_or_none()
#                 if not role_assignment:
#                     await bot.send_text(
#                         event.payload.chat.chatId,
#                         f'{mention(event.payload.sender.userId)}, у пользователя {user_id} нет роли {role_name}.',
#                     )
#                     return
#                 await session.delete(role_assignment)
#                 await session.commit()
#         except Exception:
#             logger.exception('Ошибка удаления роли %s пользователю %s', role_name, user_id)
#             await bot.send_text(
#                 event.payload.chat.chatId, f'{mention(event.payload.sender.userId)}, ошибка при удалении роли.'
#             )
#             return
#         await bot.send_text(
#             event.payload.chat.chatId,
#             f'{mention(event.payload.sender.userId)}, роль {role_name} отозвана у пользователю {user_id}.',
#         )
#         await bot.send_text(
#             chat_id=user_id,
#             text=f'{mention(event.payload.sender.userId)}, роль "{role.name}" отозвана у пользователя {user_id}.',
#         )


# @dispatcher.register_handler
# class ListRolesHandler(CommandHandler):
#     """/listroles."""

#     commands: ClassVar[list[str]] = ['listroles']

#     async def callback(self, bot: VkTeamsBot, event: NewMessageEvent) -> None:
#         """/listroles."""
#         if not event.payload.text:
#             return
#         words = event.payload.text.split(' ')[1:]
#         async with async_session() as session:
#             role_repository = RoleRepository(session)
#             if not words:
#                 roles = await role_repository.list()
#                 await bot.send_text(
#                     event.payload.chat.chatId,
#                     f'{mention(event.payload.sender.userId)}, роли: {', '.join([role.name for role in roles])}',
#                 )
#                 return

#             user_id = words[0]
#             if not await ChatUserRepository(session).exists(pk=user_id):
#                 await bot.send_text(
#                     event.payload.chat.chatId,
#                     f'{mention(event.payload.sender.userId)}, пользователь {user_id} не найден.',
#                 )
#                 return

#             roles = await role_repository.query(RoleByUserQuery(user_id=user_id)).list()
#             if not roles:
#                 await bot.send_text(
#                     event.payload.chat.chatId,
#                     f'{mention(event.payload.sender.userId)}, у пользователя {user_id} нет ролей.',
#                 )
#                 return
#             role_names = [role.name for role in roles]
#             await bot.send_text(
#                 event.payload.chat.chatId,
#                 f'{mention(event.payload.sender.userId)}, роли пользователя {user_id}: {', '.join(role_names)}.',
#             )


# @dispatcher.register_handler
# class ListRoleMembersHandler(CommandHandler):
#     """/listrolemembers."""

#     commands: ClassVar[list[str]] = ['listrolemembers']

#     async def callback(self, bot: VkTeamsBot, event: NewMessageEvent) -> None:
#         """/listrolemembers."""
#         if not event.payload.text:
#             return
#         words = event.payload.text.split(' ')[1:]
#         async with async_session() as session:
#             chat_user_repository = ChatUserRepository(session)
#             role_repository = RoleRepository(session)

#             if not words:
#                 await bot.send_text(
#                     event.payload.chat.chatId, f'{mention(event.payload.sender.userId)}, укажите навзвание роли'
#                 )
#                 return

#             role_name = words[0]
#             try:
#                 role = await role_repository.get_by_name(role_name)
#             except NotFoundError:
#                 await bot.send_text(
#                     event.payload.chat.chatId,
#                     f'{mention(event.payload.sender.userId)}, роль {role_name} не найдена.',
#                 )
#                 return

#             users = [user.id for user in await chat_user_repository.list_by_roles([role.name])]
#             if users:
#                 await bot.send_text(
#                     event.payload.chat.chatId,
#                     f'{mention(event.payload.sender.userId)}, пользователи с ролью {role.name}:\n{'\n'.join(users)}',
#                 )
#             else:
#                 await bot.send_text(
#                     event.payload.chat.chatId,
#                     f'{mention(event.payload.sender.userId)}, нет пользователей с ролью {role.name}',
#                 )


# @dispatcher.register_handler
# class NotifyRoleIsTaggedHandler(MessageHandler):
#     """/role_is_tagged."""

#     pattern = re.compile(r'(?:\W|^)\#([\w]+)')
#     filters = RegexpFilter(pattern)

#     async def callback(self, bot: VkTeamsBot, event: NewMessageEvent) -> None:
#         """role_is_tagged."""
#         if not event.payload.text:
#             return
#         hashtags = self.pattern.findall(event.payload.text)
#         if not hashtags:
#             return

#         async with async_session() as session:
#             try:
#                 users = await ChatUserRepository(session).query(ChatUserHasRoleQuery(roles=hashtags)).list()
#                 for user in users:
#                     await bot.send_text(
#                         chat_id=user.id,
#                         text=f'Вас упомянули в группе "{event.payload.chat.title}"',
#                         forward_chat_id=event.payload.chat.chatId,
#                         forward_msg_id=event.payload.msgId,
#                     )
#             except Exception:
#                 logger.exception('error')


# @dispatcher.register_handler
# class DeleteRoleConfirmation(BotButtonCommandHandler):
#     async def callback(self, bot: VkTeamsBot, event: CallbackQueryEvent) -> None:
#         ta: TypeAdapter[CallbackData] = TypeAdapter(CallbackData)
#         data = ta.validate_json(event.payload.callbackData)

#         if not isinstance(data, DeleteRoleCallbackData):
#             return

#         if event.payload.sender.userId != data.requested_by:
#             await bot.answer_callback_query(
#                 query_id=event.payload.queryId,
#                 text='Подтвердить может только тот, кто запросил удаление роли.',
#                 show_alert=True,
#             )
#             return
#         async with async_session() as session:
#             role_repository = RoleRepository(session)
#             try:
#                 role = await role_repository.get_by_name(data.role)
#             except NotFoundError:
#                 await bot.answer_callback_query(
#                     query_id=event.payload.queryId,
#                     text=f'❌ Роль {data.role} уже не существует.',
#                     show_alert=True,
#                 )
#                 return

#             role_assignment_repository = RoleAssignmentRepository(session)
#             assignments = await role_assignment_repository.query(
#                 RoleAssignmentByUserAndRoleQuery(
#                     role_id=role.id,
#                 )
#             ).list()
#             for assignment in assignments:
#                 await session.delete(assignment)
#             await session.delete(role)
#             await session.commit()
#         await bot.answer_callback_query(query_id=event.payload.queryId, text=f'Роль {data.role} удалена.')
#         await bot.edit_text(
#             chat_id=event.payload.message.chat.chatId,
#             msg_id=event.payload.message.msgId,
#             text=f'{mention(event.payload.sender.userId)}, роль {data.role} удалена.',
#         )
