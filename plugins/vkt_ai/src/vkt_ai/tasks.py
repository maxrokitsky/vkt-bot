"""Фоновые задачи агента.

Главное ограничение всей затеи: ``Dispatcher.start_polling`` вызывает
``await self.trigger(event)`` в цикле по пачке событий, а ``trigger`` ждёт
закрытия ``TaskGroup``. Значит, вызов модели на тридцать секунд внутри
хендлера останавливает опрос событий для **всех** чатов. Поэтому хендлер
только ставит задачу и сразу возвращает управление.
"""

from __future__ import annotations

import asyncio
import contextlib
from collections.abc import Coroutine
from typing import Any

import structlog

logger = structlog.get_logger("vkt_ai.tasks")

#: Ссылки на живые задачи. Без них ``create_task`` отдаёт задачу сборщику
#: мусора прямо посреди работы — про это сказано в документации asyncio.
_tasks: set[asyncio.Task[Any]] = set()

_semaphore: asyncio.Semaphore | None = None
_semaphore_limit = 0


def concurrency_limiter(limit: int) -> asyncio.Semaphore:
    """Семафор на одновременные сессии.

    Создаётся лениво: ``asyncio.Semaphore`` привязывается к текущему
    событийному циклу, а модуль импортируется раньше, чем цикл появится.
    """
    global _semaphore, _semaphore_limit  # noqa: PLW0603
    if _semaphore is None or _semaphore_limit != limit:
        _semaphore = asyncio.Semaphore(max(1, limit))
        _semaphore_limit = limit
    return _semaphore


def spawn(coro: Coroutine[Any, Any, Any]) -> asyncio.Task[Any]:
    """Запустить корутину в фоне и не потерять её."""
    task = asyncio.create_task(coro)
    _tasks.add(task)
    task.add_done_callback(_finished)
    return task


def _finished(task: asyncio.Task[Any]) -> None:
    _tasks.discard(task)
    if task.cancelled():
        return
    if (exc := task.exception()) is not None:
        # Сюда попадает только то, что не поймал сам ``run_session``:
        # тишина вместо ответа — худший из возможных исходов.
        logger.error("agent.task_failed", error=str(exc), exc_info=exc)


async def cancel_all() -> None:
    """Снять все задачи — бот останавливается."""
    tasks = list(_tasks)
    for task in tasks:
        task.cancel()
    for task in tasks:
        with contextlib.suppress(asyncio.CancelledError, Exception):
            await task


@contextlib.asynccontextmanager
async def agent_tasks():  # noqa: ANN201
    """Жизненный цикл фоновых задач на время работы бота."""
    try:
        yield
    finally:
        await cancel_all()
