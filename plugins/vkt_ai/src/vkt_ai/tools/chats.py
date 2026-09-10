"""Инструменты про чаты."""

from __future__ import annotations

import sqlalchemy as sa
from pydantic_ai import RunContext

from vkt_agent import AgentDeps
from vkt_bot.core.models.chat import Chat, ChatMembership
from vkt_bot.core.models.user import ChatUser

from . import registry
from .access import THREAD_SCOPE_ONLY, can_read_chat, user_chat_ids

#: Сколько строк отдаём модели за раз. Больше — это уже не ответ, а
#: выгрузка: она съедает бюджет токенов и ничего не проясняет.
LIMIT = 50


@registry.tool
async def find_chats(ctx: RunContext[AgentDeps], query: str = "") -> str:
    """Найти чаты по названию или идентификатору.

    Участник видит только свои чаты, администратор — все.

    Args:
        query: часть названия или идентификатора; пусто — все доступные чаты.
    """
    deps = ctx.deps
    stmt = sa.select(Chat)
    if query.strip():
        pattern = f"%{query.strip()}%"
        stmt = stmt.where(sa.or_(Chat.title.ilike(pattern), Chat.id.ilike(pattern)))
    if not deps.actor.is_admin:
        allowed = await user_chat_ids(deps, deps.actor.user_id)
        allowed.add(deps.chat_id)
        stmt = stmt.where(Chat.id.in_(allowed))
    rows = (await deps.session.scalars(stmt.limit(LIMIT))).all()
    if not rows:
        return "Ничего не нашлось."
    return "\n".join(f"{chat.title or 'без названия'} (id: {chat.id})" for chat in rows)


@registry.tool
async def chat_members(ctx: RunContext[AgentDeps], chat_id: str = "") -> str:
    """Состав чата.

    Ушедшие из чата не показываются: членство снимается по событию
    ``leftChatMembers``.

    Args:
        chat_id: идентификатор чата; пусто — текущий чат.
    """
    deps = ctx.deps
    # Пустая строка — это «текущий чат»: модель передаёт её, когда чат в
    # вопросе не назван. Раньше такой вызов упирался в проверку прав и
    # возвращал отказ на собственный чат спрашивающего.
    target = chat_id.strip() or deps.chat_id
    if deps.chat_is_thread and target != deps.chat_id:
        return THREAD_SCOPE_ONLY
    if not await can_read_chat(deps, target):
        return "Нет доступа: спрашивающий не состоит в этом чате."

    stmt = (
        sa.select(ChatUser)
        .join(ChatMembership, ChatMembership.user_id == ChatUser.id)
        .where(ChatMembership.chat_id == target)
        .limit(LIMIT)
    )
    rows = (await deps.session.scalars(stmt)).all()
    if not rows:
        # Пустой ростер — это «не знаю», а не «это тред». Прежняя
        # формулировка называла причину уверенно, и модель пересказывала
        # её как факт — в том числе про обычную группу.
        return (
            f"Состав чата {target} я не знаю: участников бот записывает по "
            "событиям о входе и выходе, и до его добавления в чат таких "
            "событий не было. У обсуждений состава не будет никогда — их "
            "участников API не отдаёт."
        )
    return "\n".join(
        f"{user.display_name} (id: {user.id})" + (" — бот" if user.is_bot else "")
        for user in rows
    )
