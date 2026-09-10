"""Инструмент про переписку.

Единственный инструмент, где ошибка в правах означает утечку переписки:
агент доступен всем участникам, поэтому без проверки членства любой
прочитал бы через бота чужой чат. Правила проверяются здесь, а не
объясняются модели.
"""

from __future__ import annotations

import datetime

from pydantic_ai import RunContext

from vkt_agent import AgentDeps
from vkt_bot.core.messages import history_enabled
from vkt_bot.core.models.message import Message
from vkt_bot.core.repositories.message import MessageRepository
from vkt_bot.core.repositories.user import ChatUserRepository

from . import registry
from .access import NO_ACCESS, THREAD_SCOPE_ONLY, can_read_chat

#: Потолок выдачи: дальше это не ответ, а выгрузка переписки.
MAX_LIMIT = 50

HISTORY_OFF = (
    "В этом чате запись истории выключена, сообщений у меня нет. "
    "Скажи об этом пользователю прямо, ничего не придумывая."
)

NOTHING_RECORDED = (
    "Сообщений не нашлось. Учти: история набирается только с момента, "
    "когда бота этому научили, — прочитать переписку задним числом у API "
    "нельзя."
)


@registry.tool
async def chat_messages(
    ctx: RunContext[AgentDeps],
    chat_id: str = "",
    limit: int = 20,
    query: str = "",
    since_days: int = 0,
) -> str:
    """Сообщения чата: последние, за период или поиск по тексту.

    Доступны только чаты, где состоит спрашивающий (администратору —
    любые). Удалённые сообщения не показываются никогда.

    Args:
        chat_id: идентификатор чата; пусто — текущий чат или обсуждение.
        limit: сколько сообщений вернуть.
        query: искать сообщения с этой подстрокой; пусто — просто последние.
        since_days: ограничить выборку последними N днями; 0 — без ограничения.
    """
    deps = ctx.deps
    target = chat_id.strip() or deps.chat_id

    # В обсуждении проверять нечем: состав треда у API не спросить, а
    # родительский чат по треду не узнать. Поэтому здесь инструмент
    # отдаёт только сам тред — тот, где человек и так находится.
    if deps.chat_is_thread and target != deps.chat_id:
        return THREAD_SCOPE_ONLY
    if not await can_read_chat(deps, target):
        return NO_ACCESS
    if not await history_enabled(deps.session, target):
        return HISTORY_OFF

    repository = MessageRepository(deps.session)
    count = max(1, min(limit, MAX_LIMIT))
    if query.strip():
        rows = await repository.search(target, query.strip(), limit=count)
    elif since_days > 0:
        after = datetime.datetime.now(datetime.UTC) - datetime.timedelta(
            days=since_days
        )
        rows = await repository.in_range(target, after=after, limit=count)
    else:
        rows = await repository.recent(target, limit=count)

    if not rows:
        return NOTHING_RECORDED
    return await _render(deps, rows)


async def _render(deps: AgentDeps, rows: list[Message]) -> str:
    """Переписка в виде «время, автор, текст».

    Имена подтягиваются одним проходом: в истории лежит идентификатор, а
    показывать участника цифрами незачем.
    """
    users = ChatUserRepository(deps.session)
    names: dict[str, str] = {}
    for row in rows:
        if row.user_id and row.user_id not in names:
            user = await users.get_or_none(row.user_id)
            names[row.user_id] = user.display_name if user else row.user_id

    lines = []
    for row in rows:
        who = (
            "бот" if row.is_outgoing else names.get(row.user_id or "", "неизвестно кто")
        )
        stamp = row.ts.strftime("%d.%m %H:%M")
        edited = " (исправлено)" if row.edited_at else ""
        lines.append(f"[{stamp}] {who}: {row.text or ''}{edited}")
    return "\n".join(lines)
