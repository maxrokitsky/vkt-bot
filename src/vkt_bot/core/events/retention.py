"""Суточная уборка: журнал событий и история сообщений.

Обе таблицы растут без остановки: поток чатов, вебхуков и команд идёт
постоянно, а сообщений — ещё быстрее. Старые рутинные записи журнала
удаляются, предупреждения и ошибки остаются: именно их ищут, когда
что-то пошло не так месяц назад. История сообщений чистится и по сроку
хранения, и по потолку строк на чат.

Задача одна на обе таблицы: уборка не срочная, и держать два одинаковых
цикла незачем.
"""

from __future__ import annotations

import asyncio
import contextlib
import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
import structlog

from vkt_bot.core.models.event import EventRecord, EventSeverity
from vkt_bot.db.session import async_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger("vkt_bot.events")

#: Как часто проверять. Раз в сутки: чистка — не срочная операция.
INTERVAL_SECONDS = 24 * 60 * 60

#: Что переживает чистку независимо от возраста.
KEPT_SEVERITIES = (EventSeverity.WARNING, EventSeverity.ERROR)


async def purge_old_events(session: AsyncSession, days: int) -> int:
    """Удалить рутинные события старше ``days``. Возвращает число строк.

    ``days <= 0`` выключает чистку — журнал хранится вечно.
    """
    if days <= 0:
        return 0

    edge = datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days)
    result = await session.execute(
        sa.delete(EventRecord).where(
            EventRecord.ts < edge,
            EventRecord.severity.notin_(KEPT_SEVERITIES),
        )
    )
    await session.commit()
    return result.rowcount or 0


async def run_retention_loop(interval: int = INTERVAL_SECONDS) -> None:
    """Чистить журнал раз в сутки, пока задачу не отменят.

    Сбой чистки не должен ронять бота: следующая попытка будет завтра.
    """
    from vkt_bot.config import get_settings
    from vkt_bot.core.messages import purge_history

    settings = get_settings()
    days = settings.events_retention_days
    while True:
        try:
            async with async_session() as session:
                removed = await purge_old_events(session, days)
            if removed:
                logger.info("events.purged", removed=removed, older_than_days=days)
        except Exception:
            logger.exception("events.purge_failed")
        try:
            async with async_session() as session:
                removed = await purge_history(
                    session,
                    days=settings.messages_retention_days,
                    max_per_chat=settings.messages_max_per_chat,
                )
            if removed:
                logger.info(
                    "messages.purged",
                    removed=removed,
                    older_than_days=settings.messages_retention_days,
                )
        except Exception:
            logger.exception("messages.purge_failed")
        await asyncio.sleep(interval)


@contextlib.asynccontextmanager
async def retention_task(interval: int = INTERVAL_SECONDS):  # noqa: ANN201
    """Фоновая чистка на время работы бота."""
    task = asyncio.create_task(run_retention_loop(interval))
    try:
        yield task
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
