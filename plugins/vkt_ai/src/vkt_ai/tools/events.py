"""Инструмент про журнал событий."""

from __future__ import annotations

import sqlalchemy as sa
from pydantic_ai import RunContext

from vkt_agent import AgentDeps
from vkt_bot.core.models.event import EventRecord
from vkt_bot.utils.datetime import localize_datetime
from vkt_bot.webapp.api.events import TEXT_FIELDS

from . import registry
from .access import THREAD_SCOPE_ONLY, can_read_chat

#: Столько строк умещается в ответе, не съедая бюджет токенов.
MAX_LIMIT = 30


@registry.tool
async def recent_events(
    ctx: RunContext[AgentDeps], chat_id: str = "", limit: int = 10
) -> str:
    """Последние события чата: кто что сделал с ролями, чатами и вебхуками.

    Это журнал действий, а не переписка. Тексты сообщений из него вырезаны
    — те же правила, что у ленты событий в панели.

    Args:
        chat_id: идентификатор чата; пусто — текущий чат.
        limit: сколько последних событий показать.
    """
    deps = ctx.deps
    target = chat_id.strip() or deps.chat_id
    if deps.chat_is_thread and target != deps.chat_id:
        return THREAD_SCOPE_ONLY
    if not await can_read_chat(deps, target):
        return "Нет доступа: спрашивающий не состоит в этом чате."

    stmt = (
        sa.select(EventRecord)
        .where(EventRecord.chat_id == target)
        .order_by(EventRecord.ts.desc(), EventRecord.id.desc())
        .limit(max(1, min(limit, MAX_LIMIT)))
    )
    rows = list((await deps.session.scalars(stmt)).all())
    if not rows:
        return "В этом чате событий не записано."
    rows.reverse()
    return "\n".join(
        f"{localize_datetime(row.ts)}: {row.summary}{_extra(row)}" for row in rows
    )


def _extra(row: EventRecord) -> str:
    """Полезное из ``payload`` — без полей с перепиской."""
    payload = {
        key: value
        for key, value in (row.payload or {}).items()
        if key not in TEXT_FIELDS
    }
    if not payload:
        return ""
    return " (" + ", ".join(f"{key}: {value}" for key, value in payload.items()) + ")"
