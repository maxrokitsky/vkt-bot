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

    Обе половины нужны только там, где нет Redis. С ним диалоги чистит
    ``taskiq scheduler``, а сессии крутятся в воркере — снимать при
    остановке бота нечего.
    """
    from vkt_bot.worker import distributed

    from .tasks import cancel_all

    if distributed():
        yield
        return

    task = asyncio.create_task(_retention_loop())
    try:
        yield
    finally:
        task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await task
        # Сессии здесь же, в процессе бота: висящий вызов модели не
        # должен удерживать процесс при остановке.
        await cancel_all()


def install() -> None:
    """Подключить плагин. Зовут все процессы: бот, веб, воркер.

    ``jobs`` импортируется ради побочного эффекта: задачи объявляются
    декоратором ``@broker.task``, и без импорта воркер о них не узнает.
    """
    from vkt_bot.core.lifespans import register

    from . import handlers, jobs, models  # noqa: F401
    from .agent import configured
    from .events import install_events

    install_events()
    register(lifespan)

    logger.info("plugin.installed", plugin="ai", configured=configured())


def install_api(webapp: FastAPI) -> None:
    """Отдать свои роутеры. Зовёт только веб-процесс."""
    from . import api

    webapp.include_router(api.router)
