"""Задачи ядра.

Раньше уборка была ``asyncio.sleep(24h)`` внутри процесса бота: отсчёт
начинался заново при каждом перезапуске, и на стенде, где бота
перезапускают чаще раза в сутки, она не случалась никогда. Cron от этого
избавляет.
"""

from __future__ import annotations

from vkt_bot.core.events.retention import purge_once
from vkt_bot.worker.broker import broker


@broker.task(
    task_name="vkt_bot.retention",
    # Время UTC. Ночью: удаление идёт большими пачками и держит блокировки.
    schedule=[{"cron": "10 3 * * *"}],
    retry_on_error=True,
    max_retries=2,
)
async def retention() -> None:
    """Суточная уборка журнала событий и истории сообщений."""
    await purge_once()
