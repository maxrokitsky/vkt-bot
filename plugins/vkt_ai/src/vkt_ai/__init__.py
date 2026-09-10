"""ИИ-агент в чате.

Подключается entry point'ом, отключается снятием зависимости. Ядро о нём
не знает: всё, что плагину нужно от приложения, он берёт публичными
средствами — репозиториями, реестром событий и реестром фоновых задач.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import AsyncIterator

import structlog
from fastapi import FastAPI

logger = structlog.get_logger("vkt_ai")

#: Как часто чистить старые диалоги. Раз в сутки: операция не срочная.
RETENTION_INTERVAL = 24 * 60 * 60


async def _retention_loop(interval: int = RETENTION_INTERVAL) -> None:
    """Чистить диалоги раз в сутки, пока задачу не отменят."""
    from vkt_bot.db.session import async_session

    from .config import get_ai_settings
    from .retention import purge_old_sessions

    days = get_ai_settings().retention_days
    while True:
        try:
            async with async_session() as session:
                await purge_old_sessions(session, days)
        except Exception:
            logger.exception("agent.purge_failed")
        await asyncio.sleep(interval)


@contextlib.asynccontextmanager
async def lifespan() -> AsyncIterator[None]:
    """Фоновая работа агента на время жизни бота.

    Задачи сессий снимаются здесь же: висящий вызов модели не должен
    удерживать процесс при остановке.
    """
    from .tasks import cancel_all

    task = asyncio.create_task(_retention_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        await cancel_all()


def install(webapp: FastAPI) -> None:  # noqa: ARG001
    """Подключить плагин."""
    from vkt_bot.core.lifespans import register

    from . import handlers, models  # noqa: F401
    from .agent import configured
    from .events import install_events

    install_events()
    register(lifespan)

    logger.info("plugin.installed", plugin="ai", configured=configured())
