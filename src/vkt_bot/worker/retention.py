"""Уборка без планировщика.

С Redis чистку раскладывает по времени ``taskiq scheduler``. Без него
планировщика нет вовсе, поэтому старый цикл внутри процесса бота
остаётся — но только в этом режиме: держать оба значило бы удалять одно
и то же дважды и объяснять в журнале две записи ``events.purged``.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

from vkt_bot.core.events.retention import retention_task
from vkt_bot.worker.broker import distributed

if TYPE_CHECKING:
    from collections.abc import AsyncIterator


@contextlib.asynccontextmanager
async def local_retention() -> AsyncIterator[None]:
    """Суточная уборка в процессе бота — пока нет планировщика."""
    if distributed():
        yield
        return
    async with retention_task():
        yield
