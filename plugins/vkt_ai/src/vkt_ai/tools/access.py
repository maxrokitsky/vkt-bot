"""Права инструментов.

Проверяются здесь, а не в промпте: системный промпт про права тоже
рассказывает, но полагаться на него нельзя — модель не должна быть
каналом эскалации привилегий.

Единственный по-настоящему опасный инструмент — ``chat_messages``: агент
доступен всем участникам, и без проверки членства любой прочитал бы
через бота чужую переписку.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa

from vkt_bot.core.models.chat import ChatMembership

if TYPE_CHECKING:
    from vkt_agent import AgentDeps

#: Что отвечает инструмент, когда чат читать нельзя. Текст пойдёт модели,
#: и она перескажет его пользователю.
NO_ACCESS = (
    "Нет доступа: спрашивающий не состоит в этом чате. "
    "Скажи ему об этом и не выдумывай содержимое."
)

#: Отказ в обсуждении: состав треда узнать нечем, родительский чат по
#: треду — тоже.
THREAD_SCOPE_ONLY = (
    "Разговор идёт в обсуждении, а состав обсуждения у API не спросить. "
    "Поэтому здесь я читаю только само это обсуждение и никакие другие "
    "чаты. Скажи об этом пользователю."
)


async def user_chat_ids(deps: AgentDeps, user_id: str) -> set[str]:
    """Чаты, в которых состоит участник."""
    stmt = sa.select(ChatMembership.chat_id).where(ChatMembership.user_id == user_id)
    return set((await deps.session.scalars(stmt)).all())


async def can_read_chat(deps: AgentDeps, chat_id: str) -> bool:
    """Можно ли актору читать переписку этого чата.

    Правила те же, что у ``GET /api/chat-users``: обычный чат — по
    ``chat_memberships``, администратор — любой.
    """
    if deps.actor.is_admin:
        return True
    if chat_id == deps.chat_id:
        # Человек пишет в этом чате прямо сейчас — значит, он в нём.
        return True
    return chat_id in await user_chat_ids(deps, deps.actor.user_id)
