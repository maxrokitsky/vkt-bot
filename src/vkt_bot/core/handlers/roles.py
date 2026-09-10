import json
import logging
import re
from typing import ClassVar

from pydantic import TypeAdapter

from sqlalchemy.ext.asyncio import AsyncSession

from vkteams_client import ThreadSubscribersError, VKTeams
from vkteams_client.types import CallbackQueryEvent, NewMessageEvent
from vkteams_client.types import Chat as ChatPayload
from vkt_bot.db.session import async_session
from vkt_dispatcher.filters import RegexpFilter
from vkt_dispatcher.handlers import (
    BotButtonCommandHandler,
    CommandHandler,
    MessageHandler,
)
from vkt_bot.db.repository import NotFoundError
from vkt_bot.core.queries.roles import RoleAssignmentByUserAndRoleQuery, RoleByUserQuery
from vkt_bot.core.queries.user import ChatUserHasRoleQuery
from vkt_bot.core.repositories.role import (
    CreateRoleAssignmentSchema,
    CreateRoleSchema,
    RoleAssignmentRepository,
    RoleRepository,
)
from vkt_bot.core.repositories.chat import ChatMembershipRepository, ChatRepository
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.app import dispatcher
from vkt_bot.core.handlers.callback import CallbackData, DeleteRoleCallbackData
from vkt_bot.core.handlers.mixins import AdminRequiredMixin
from vkt_bot.utils.message import mention, sender_name

logger = logging.getLogger("teams_bot.handlers.roles")

# Так API отвечает на ``threads/subscribers/get`` для обычного чата.
NOT_A_THREAD = "incorrect threadid"


@dispatcher.register_handler
class CreateRoleHandler(AdminRequiredMixin, CommandHandler):
    """/createrole."""

    commands: ClassVar[list[str]] = ["createrole"]

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        args = event.payload.text.split(" ")[1:]
        role_name = args[0]

        async with async_session() as session:
            role_repository = RoleRepository(session)
            try:
                await role_repository.get_by_name(role_name)
            except NotFoundError:
                pass
            else:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(event.payload.sender.userId)}, роль {role_name} уже существует.",
                )
                return

            await role_repository.create(CreateRoleSchema(name=role_name), commit=True)
        await bot.send_text(
            event.payload.chat.chatId,
            f"{mention(event.payload.sender.userId)}, роль {role_name} добавлена",
        )


@dispatcher.register_handler
class DeleteRoleHandler(AdminRequiredMixin, CommandHandler):
    """/deleterole."""

    commands: ClassVar[list[str]] = ["deleterole"]

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        args = event.payload.text.split(" ")[1:]
        role_name = args[0]
        if role_name.lower() in ["admin", "botowner"]:
            await bot.send_text(
                event.payload.chat.chatId,
                f"{mention(event.payload.sender.userId)}, роль {role_name} нельзя удалить.",
            )
            return

        async with async_session() as session:
            role_repository = RoleRepository(session)
            try:
                role = await role_repository.get_by_name(role_name)
            except NotFoundError:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(event.payload.sender.userId)}, роль {role_name} не существует.",
                )
                return

            role_assignment_repository = RoleAssignmentRepository(session)
            assignments = await role_assignment_repository.query(
                RoleAssignmentByUserAndRoleQuery(
                    role_id=role.id,
                )
            ).list()
            if assignments:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"Роль назначена {len(assignments)} пользователям.\n\n"
                    f"Вы уверены, что хотите удалить роль {role.name}?",
                    inline_keyboard_markup="[{}]".format(
                        json.dumps(
                            [
                                {
                                    "text": f"Удалить роль {role.name}",
                                    "callbackData": DeleteRoleCallbackData(
                                        command="deleterole",
                                        role=role.name,
                                        requested_by=event.payload.sender.userId,
                                    ).model_dump_json(),
                                    "style": "attention",
                                },
                            ]
                        )
                    ),
                )
                return
            for assignment in assignments:
                await session.delete(assignment)
            await session.delete(role)
            await session.commit()
        await bot.send_text(
            event.payload.chat.chatId,
            f"{mention(event.payload.sender.userId)}, роль {role_name} удалена.",
        )


@dispatcher.register_handler
class AssignRoleHandler(AdminRequiredMixin, CommandHandler):
    """/assignrole."""

    commands: ClassVar[list[str]] = ["assignrole"]

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        args = event.payload.text.split(" ")[1:]
        user_id = args[0]
        role_name = args[1]

        try:
            async with async_session() as session:
                role_repository = RoleRepository(session)
                user_repository = ChatUserRepository(session)
                try:
                    role = await role_repository.get_by_name(role_name)
                except NotFoundError:
                    await bot.send_text(
                        event.payload.chat.chatId,
                        f"{mention(event.payload.sender.userId)}, роль {role_name} не существует.",
                    )
                    return

                role_assignment_repository = RoleAssignmentRepository(session)

                if role_name.lower() == "botowner":
                    await bot.send_text(
                        event.payload.chat.chatId,
                        f"{mention(event.payload.sender.userId)}, роль {role_name} нельзя назначить.",
                    )
                    return

                if await role_assignment_repository.query(
                    RoleAssignmentByUserAndRoleQuery(user_id=user_id, role_id=role.id)
                ).exists():
                    await bot.send_text(
                        event.payload.chat.chatId,
                        f"{mention(event.payload.sender.userId)}, пользователю {user_id} уже назначена роль {role_name}.",
                    )
                    return
                await user_repository.get_or_create(user_id)
                await role_assignment_repository.create(
                    CreateRoleAssignmentSchema(role_id=role.id, user_id=user_id)
                )
                await session.commit()
        except Exception:
            logger.exception(
                "Ошибка наначения роли %s пользователю %s", role_name, user_id
            )
            await bot.send_text(
                event.payload.chat.chatId,
                f"{mention(event.payload.sender.userId)}, ошибка при добавлении роли.",
            )
            return
        await bot.send_text(
            event.payload.chat.chatId,
            f"{mention(event.payload.sender.userId)}, роль {role.name} назначена пользователю {user_id}.",
        )
        await bot.send_text(chat_id=user_id, text=f'Вам назначена роль "{role.name}"')


@dispatcher.register_handler
class RevokeRoleHandler(AdminRequiredMixin, CommandHandler):
    """/revokerole."""

    commands: ClassVar[list[str]] = ["revokerole"]
    description = "/revokerole id_пользователя роль - Отзывает роль у пользователя"

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        args = event.payload.text.split(" ")[1:]
        user_id = args[0]
        role_name = args[1]

        try:
            async with async_session() as session:
                try:
                    role = await RoleRepository(session).get_by_name(role_name)
                except NotFoundError:
                    await bot.send_text(
                        event.payload.chat.chatId,
                        f"{mention(event.payload.sender.userId)}, роль {role_name} не существует.",
                    )
                    return

                if role_name.lower() in ["botowner"]:
                    await bot.send_text(
                        event.payload.chat.chatId,
                        f"{mention(event.payload.sender.userId)}, роль {role_name} нельзя отозвать.",
                    )
                    return

                role_assignment_repository = RoleAssignmentRepository(session)
                role_assignment = await role_assignment_repository.query(
                    RoleAssignmentByUserAndRoleQuery(user_id=user_id, role_id=role.id)
                ).one_or_none()
                if not role_assignment:
                    await bot.send_text(
                        event.payload.chat.chatId,
                        f"{mention(event.payload.sender.userId)}, у пользователя {user_id} нет роли {role_name}.",
                    )
                    return
                await session.delete(role_assignment)
                await session.commit()
        except Exception:
            logger.exception(
                "Ошибка удаления роли %s пользователю %s", role_name, user_id
            )
            await bot.send_text(
                event.payload.chat.chatId,
                f"{mention(event.payload.sender.userId)}, ошибка при удалении роли.",
            )
            return
        await bot.send_text(
            event.payload.chat.chatId,
            f"{mention(event.payload.sender.userId)}, роль {role_name} отозвана у пользователю {user_id}.",
        )
        await bot.send_text(
            chat_id=user_id,
            text=f'{mention(event.payload.sender.userId)}, роль "{role.name}" отозвана у пользователя {user_id}.',
        )


@dispatcher.register_handler
class ListRolesHandler(CommandHandler):
    """/listroles."""

    commands: ClassVar[list[str]] = ["listroles"]

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        words = event.payload.text.split(" ")[1:]
        async with async_session() as session:
            role_repository = RoleRepository(session)
            if not words:
                roles = await role_repository.list()
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(event.payload.sender.userId)}, роли: {', '.join([role.name for role in roles])}",
                )
                return

            user_id = words[0]
            if not await ChatUserRepository(session).exists(pk=user_id):
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(event.payload.sender.userId)}, пользователь {user_id} не найден.",
                )
                return

            roles = await role_repository.query(RoleByUserQuery(user_id=user_id)).list()
            if not roles:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(event.payload.sender.userId)}, у пользователя {user_id} нет ролей.",
                )
                return
            role_names = [role.name for role in roles]
            await bot.send_text(
                event.payload.chat.chatId,
                f"{mention(event.payload.sender.userId)}, роли пользователя {user_id}: {', '.join(role_names)}.",
            )


@dispatcher.register_handler
class ListRoleMembersHandler(CommandHandler):
    """/listrolemembers."""

    commands: ClassVar[list[str]] = ["listrolemembers"]

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        words = event.payload.text.split(" ")[1:]
        async with async_session() as session:
            user_repository = ChatUserRepository(session)
            role_repository = RoleRepository(session)

            if not words:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(event.payload.sender.userId)}, укажите навзвание роли",
                )
                return

            role_name = words[0]
            try:
                role = await role_repository.get_by_name(role_name)
            except NotFoundError:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(event.payload.sender.userId)}, роль {role_name} не найдена.",
                )
                return

            users = [
                user.id for user in await user_repository.list_by_roles([role.name])
            ]
            if users:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(event.payload.sender.userId)}, пользователи с ролью {role.name}:\n{'\n'.join(users)}",
                )
            else:
                await bot.send_text(
                    event.payload.chat.chatId,
                    f"{mention(event.payload.sender.userId)}, нет пользователей с ролью {role.name}",
                )


@dispatcher.register_handler
class NotifyRoleIsTaggedHandler(MessageHandler):
    """/role_is_tagged."""

    pattern = re.compile(r"(?:\W|^)\#([\w]+)")
    filters = RegexpFilter(pattern)

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        hashtags = self.pattern.findall(event.payload.text)
        if not hashtags:
            return

        async with async_session() as session:
            try:
                users = (
                    await ChatUserRepository(session)
                    .query(ChatUserHasRoleQuery(roles=hashtags))
                    .list()
                )
                if not users:
                    # Обычный хештег, а не призыв по роли: дальше идут
                    # запросы к API, и делать их незачем.
                    return

                text = await self.notification_text(session, event.payload.chat)
                audience = await self.audience(bot, session, event.payload.chat.chatId)
                for user in users:
                    await self.notify(
                        bot,
                        user.id,
                        text,
                        event,
                        may_see_content=user.id in audience,
                    )
            except Exception:
                logger.exception("error")

    async def audience(
        self, bot: VKTeams, session: AsyncSession, chat_id: str
    ) -> set[str]:
        """Кому исходное сообщение и так доступно.

        Роль глобальна, а чат — нет: носитель роли может не состоять в
        источнике. Для обсуждения список даёт ``threads/subscribers/get``,
        для обычного чата — таблица членства. Если подписчиков узнать не
        удалось, остаётся членство: для треда строк там нет, то есть
        доступ никому не подтвердится и тело сообщения не уйдёт. Так и
        нужно — при неизвестном составе лучше промолчать.
        """
        subscribers = await self.thread_subscribers(bot, chat_id)
        if subscribers is not None:
            return subscribers
        return await ChatMembershipRepository(session).user_ids(chat_id)

    async def thread_subscribers(self, bot: VKTeams, chat_id: str) -> set[str] | None:
        """Подписчики обсуждения или ``None``, если состав неизвестен.

        Отказ ``Incorrect threadId`` — это ответ «перед нами не
        обсуждение, а обычный чат», и он ожидаем: каждое сообщение
        проходит здесь. Всё остальное — сбой: сеть, права или ошибка в
        нашем коде. Различать их важно, иначе поломка выглядит как
        обычный чат и молча уходит в debug.
        """
        try:
            return {s.sn async for s in bot.iter_thread_subscribers(chat_id)}
        except ThreadSubscribersError as err:
            if NOT_A_THREAD in str(err).lower():
                logger.debug("Чат %s не обсуждение", chat_id)
            else:
                logger.warning("Подписчики обсуждения %s недоступны: %s", chat_id, err)
            return None
        except Exception:
            logger.warning(
                "Не удалось получить подписчиков чата %s", chat_id, exc_info=True
            )
            return None

    async def notify(
        self,
        bot: VKTeams,
        user_id: str,
        text: str,
        event: NewMessageEvent,
        *,
        may_see_content: bool,
    ) -> None:
        """Уведомить пользователя об упоминании.

        Обычно пересылаем исходное сообщение. Из обсуждения пересылка
        может не пройти — сервер отвечает ``ok: false``, и уведомление
        молча теряется. Поэтому на отказ шлём текст сообщения напрямую —
        но только тому, кому он и так доступен: пересылку получатель без
        доступа не открыл бы, а наш текст прочитал бы.
        """
        result = await bot.send_text(
            chat_id=user_id,
            text=text,
            # У обсуждения свой chatId, пересылка из него —
            # такая же, как из обычного чата.
            forward_chat_id=event.payload.chat.chatId,
            forward_msg_id=event.payload.msgId,
        )
        if result is None or result.ok:
            return

        logger.warning(
            "Пересылка упоминания из чата %s не прошла (%s). Отправляю текстом.",
            event.payload.chat.chatId,
            result.description,
        )
        body = self.quoted_text(text, event) if may_see_content else text
        await bot.send_text(chat_id=user_id, text=body)

    @staticmethod
    def quoted_text(text: str, event: NewMessageEvent) -> str:
        """Уведомление без пересылки: сам текст сообщения и его автор."""
        body = (event.payload.text or "").strip()
        if not body:
            return text
        return f"{text}\n\n{sender_name(event.payload.sender)}: {body}"

    async def notification_text(self, session: AsyncSession, chat: ChatPayload) -> str:
        """Текст уведомления об упоминании.

        В событиях из обсуждений названия чата нет, а в базе оно может
        оказаться от прошлых событий. Если названия нет вовсе — не выдумываем
        его: контекст даёт пересланное сообщение.
        """
        title = chat.title
        if not title:
            stored = await ChatRepository(session).get_or_none(chat.chatId)
            title = stored.title if stored else None
        return f'Вас упомянули в группе "{title}"' if title else "Вас упомянули"


@dispatcher.register_handler
class DeleteRoleConfirmation(BotButtonCommandHandler):
    async def callback(self, bot: VKTeams, event: CallbackQueryEvent) -> None:
        ta: TypeAdapter[CallbackData] = TypeAdapter(CallbackData)
        data = ta.validate_json(event.payload.callbackData)

        if not isinstance(data, DeleteRoleCallbackData):
            return

        if event.payload.sender.userId != data.requested_by:
            await bot.answer_callback_query(
                query_id=event.payload.queryId,
                text="Подтвердить может только тот, кто запросил удаление роли.",
                show_alert=True,
            )
            return
        async with async_session() as session:
            role_repository = RoleRepository(session)
            try:
                role = await role_repository.get_by_name(data.role)
            except NotFoundError:
                await bot.answer_callback_query(
                    query_id=event.payload.queryId,
                    text=f"❌ Роль {data.role} уже не существует.",
                    show_alert=True,
                )
                return

            role_assignment_repository = RoleAssignmentRepository(session)
            assignments = await role_assignment_repository.query(
                RoleAssignmentByUserAndRoleQuery(
                    role_id=role.id,
                )
            ).list()
            for assignment in assignments:
                await session.delete(assignment)
            await session.delete(role)
            await session.commit()
        await bot.answer_callback_query(
            query_id=event.payload.queryId, text=f"Роль {data.role} удалена."
        )
        await bot.edit_text(
            chat_id=event.payload.message.chat.chatId,
            msg_id=event.payload.message.msgId,
            text=f"{mention(event.payload.sender.userId)}, роль {data.role} удалена.",
        )
