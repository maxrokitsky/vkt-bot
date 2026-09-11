"""Инструменты про чат и участника: то, что приносит ``chats/getInfo``.

Читают из базы, а не из API: данные там уже есть — их складывает
``vkt_bot.core.chatinfo`` при добавлении бота в чат и дальше по потоку
сообщений. Если они устарели, инструмент сам их освежит: у сессии агента
есть клиент бота, а лимиты и TTL живут внутри ``chatinfo``.
"""

from __future__ import annotations

import sqlalchemy as sa
from pydantic_ai import RunContext

from vkt_agent import AgentDeps
from vkt_bot.core import chatinfo
from vkt_bot.core.models.role import Role, RoleAssignment
from vkt_bot.core.repositories.chat import ChatRepository
from vkt_bot.core.repositories.user import ChatUserRepository
from vkteams_client.enums import ChatType

from . import registry
from .access import NO_ACCESS, THREAD_SCOPE_ONLY, can_read_chat


@registry.tool
async def chat_info(ctx: RunContext[AgentDeps], chat_id: str = "") -> str:
    """Что за чат: название, описание, правила, вид и ссылка-приглашение.

    Args:
        chat_id: идентификатор чата; пусто — текущий чат.
    """
    deps = ctx.deps
    # Пустая строка — «текущий чат»; резолвим до проверки прав, иначе у
    # администратора она уходит в запрос как есть.
    target = chat_id.strip() or deps.chat_id
    if deps.chat_is_thread and target != deps.chat_id:
        return THREAD_SCOPE_ONLY
    if not await can_read_chat(deps, target):
        return NO_ACCESS

    chat = await ChatRepository(deps.session).get_or_none(target)
    if chat is None:
        return (
            f"Чата {target} я не знаю: бот записывает чаты с того момента, "
            "как его в них добавили."
        )

    if deps.bot is not None and chatinfo.is_stale(chat.info_updated_at):
        await chatinfo.enrich_chat(deps.bot, target)
        deps.session.expire(chat)
        chat = await ChatRepository(deps.session).get_or_none(target)
        if chat is None:
            return f"Чата {target} я не знаю."

    kinds = {
        ChatType.PRIVATE: "личный чат",
        ChatType.GROUP: "группа",
        ChatType.CHANNEL: "канал",
    }
    lines = [
        f"{chat.title or 'без названия'} (id: {chat.id})",
        # ``get``, а не индекс: новый вид чата в перечислении не должен
        # ронять инструмент на ровном месте.
        kinds.get(chat.type, "чат неизвестного вида"),
    ]
    if chat.about:
        lines.append(f"Описание: {chat.about}")
    if chat.rules:
        lines.append(f"Правила: {chat.rules}")
    if chat.public is not None:
        lines.append("Публичный" if chat.public else "Закрытый")
    if chat.join_moderation:
        lines.append("Вступление — с одобрения администратора")
    if chat.invite_link:
        lines.append(f"Ссылка-приглашение: {chat.invite_link}")
    if chat.info_updated_at is None:
        # Отличаем «нечего рассказать» от «ещё не спрашивали»: иначе
        # модель выдаёт пустоту за факт.
        lines.append("Описание и правила у API ещё не спрашивали.")
    return "\n".join(lines)


@registry.tool
async def user_info(ctx: RunContext[AgentDeps], user_id: str = "") -> str:
    """Кто этот участник: имя, ник, «о себе», человек или бот, роли.

    Args:
        user_id: идентификатор участника; пусто — сам спрашивающий.
    """
    deps = ctx.deps
    target = user_id.strip() or deps.actor.user_id

    users = ChatUserRepository(deps.session)
    user = await users.get_or_none(target)
    if user is None:
        return (
            f"Участника {target} я не знаю: в базу люди попадают по событиям "
            "о составе чатов и по своим сообщениям."
        )

    if deps.bot is not None and chatinfo.is_stale(user.info_updated_at):
        await chatinfo.enrich_members(deps.bot, [target])
        deps.session.expire(user)
        user = await users.get_or_none(target)
        if user is None:
            return f"Участника {target} я не знаю."

    lines = [f"{user.display_name} (id: {user.id})"]
    if user.nick and user.nick != user.display_name:
        lines.append(f"Ник: {user.nick}")
    if user.about:
        lines.append(f"О себе: {user.about}")
    lines.append("Это бот." if user.is_bot else "Это человек.")
    # Отдельным запросом, а не через ``user.roles``: ленивая загрузка в
    # асинхронной сессии не работает.
    stmt = (
        sa.select(Role.name)
        .join(RoleAssignment, RoleAssignment.role_id == Role.id)
        .where(RoleAssignment.user_id == user.id)
        .order_by(Role.name)
    )
    roles = list((await deps.session.scalars(stmt)).all())
    if roles:
        lines.append("Роли: " + ", ".join(roles))
    return "\n".join(lines)
