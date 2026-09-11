"""Чистка диалогов с агентом.

Тексты промптов и ответов — чувствительные данные: в них попадает и
переписка чатов, и то, что человек спросил. Поэтому они чистятся тем же
механизмом, что журнал событий, и обычно с более коротким сроком.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
import structlog

from .models import AgentSession

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger("vkt_ai.retention")


async def purge_old_sessions(session: AsyncSession, days: int) -> int:
    """Удалить диалоги старше ``days``. ``days <= 0`` выключает чистку.

    Сообщения и вызовы инструментов уходят каскадом: они не имеют смысла
    без сессии, к которой относятся.

    Срок считается от последней активности, а не от начала: диалог,
    начатый месяц назад и продолженный вчера, — живой, и сносить его
    вместе со всей перепиской было бы неожиданно.
    """
    if days <= 0:
        return 0
    edge = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days)
    stale = (
        await session.scalars(
            sa.select(AgentSession.id).where(AgentSession.updated_at < edge)
        )
    ).all()
    if not stale:
        return 0
    for row in stale:
        obj = await session.get(AgentSession, row)
        if obj is not None:
            await session.delete(obj)
    await session.commit()
    logger.info("agent.sessions_purged", removed=len(stale), older_than_days=days)
    return len(stale)
