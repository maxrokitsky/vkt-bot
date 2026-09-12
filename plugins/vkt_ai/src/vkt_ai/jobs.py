"""Задачи агента: то, что исполняется в отдельном процессе.

Причина, по которой сессия вообще живёт вне хендлера, не изменилась:
``Dispatcher.start_polling`` делает ``await self.trigger(event)`` в цикле
по пачке событий, а ``trigger`` ждёт закрытия ``TaskGroup``. Вызов модели
на тридцать секунд внутри хендлера останавливает опрос событий для
**всех** чатов. Изменилось другое: теперь это не ``asyncio``-задача
рядом с опросом, а сообщение в очереди, которое разбирает воркер.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import structlog

from vkt_bot.db.session import async_session
from vkt_bot.worker.broker import broker

from .config import get_ai_settings
from .retention import purge_old_sessions
from .session import SessionRequest, run_session

if TYPE_CHECKING:
    from vkteams_client import VKTeams

logger = structlog.get_logger("vkt_ai.jobs")


@broker.task(task_name="vkt_ai.run_session")
async def run_session_task(payload: dict[str, Any]) -> None:
    """Отработать вопрос агенту.

    Бот берётся из ``vkt_bot.app`` и **внутри** функции: в воркере это
    свой экземпляр со своей ``aiohttp``-сессией, привязанной к его циклу,
    а импорт на уровне модуля прибил бы к задаче тот объект, который
    существовал на импорте, — мимо подмены в тестах.
    """
    from vkt_bot.app import bot

    await run_session(bot, SessionRequest.from_payload(payload))


@broker.task(
    task_name="vkt_ai.purge_sessions",
    # Полчаса после уборки ядра: две тяжёлые чистки не должны бить по
    # базе одновременно.
    schedule=[{"cron": "40 3 * * *"}],
    retry_on_error=True,
    max_retries=2,
)
async def purge_sessions() -> None:
    """Суточная чистка диалогов с агентом."""
    async with async_session() as session:
        await purge_old_sessions(session, get_ai_settings().retention_days)


async def enqueue_session(bot: VKTeams, request: SessionRequest) -> None:
    """Поставить вопрос в очередь.

    Отказ брокера — не повод промолчать: тишина вместо ответа худший из
    исходов, а необъяснённая тишина — тем более. Поэтому исключение
    превращается в сообщение «не смог», как это делает сама сессия.
    """
    try:
        await run_session_task.kiq(request.as_payload())
    except Exception:
        logger.exception("agent.enqueue_failed", chat_id=request.chat_id)
        await bot.send_text(
            request.chat_id,
            "Не получилось принять вопрос: очередь задач недоступна. "
            "Попробуй через пару минут.",
        )
