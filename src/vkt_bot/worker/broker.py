"""Брокер фоновых задач.

Живёт в ядре и знает только про настройки: задачи объявляют те, кому они
нужны, — ядро в ``worker/tasks.py``, плагины у себя. Импортировать отсюда
что-либо из плагинов нельзя, иначе ядро начнёт зависеть от подключаемого.

Без ``REDIS_URL`` собирается ``InMemoryBroker``: ``kiq()`` заводит
``asyncio``-задачу в текущем процессе — ровно то, что раньше делал
``vkt_ai.tasks.spawn``. Это режим локальной разработки и тестов, а не
запасной путь для прода, поэтому он громкий.
"""

from __future__ import annotations

import contextlib
from typing import TYPE_CHECKING

import structlog
from taskiq import AsyncBroker, InMemoryBroker, SimpleRetryMiddleware

from vkt_bot.config import get_settings

if TYPE_CHECKING:
    from collections.abc import AsyncIterator

logger = structlog.get_logger("vkt_bot.worker")


def create_broker() -> AsyncBroker:
    """Брокер по настройкам."""
    settings = get_settings()
    if settings.redis_url is None:
        logger.warning("broker.in_memory", reason="REDIS_URL не задан")
        return InMemoryBroker()

    # Импорт внутри: без Redis тащить клиента на импорте незачем.
    from taskiq_redis import ListQueueBroker

    logger.info("broker.redis", queue=settings.task_queue)
    return ListQueueBroker(
        str(settings.redis_url),
        queue_name=settings.task_queue,
        # ``listen()`` висит на ``brpop`` без таймаута — ждёт задачу
        # столько, сколько нужно. А redis-py с восьмой версии ставит
        # ``socket_timeout=5`` по умолчанию, и чтение обрывается через
        # пять секунд. ``TimeoutError`` брокер не ловит (только
        # ``ConnectionError``), поэтому воркер падал и перезапускался по
        # кругу — а вместе с ним терялась задача, которую он в этот
        # момент выполнял: подтверждений у списка нет.
        socket_timeout=None,
        # Взамен таймаута — TCP-keepalive и проверка живости: иначе
        # молча оборванное соединение повесило бы воркер навсегда.
        socket_keepalive=True,
        health_check_interval=30,
    ).with_middlewares(
        # Действует только на задачи с меткой ``retry_on_error=True``.
        # Сессию агента она не тронет намеренно: повтор вызова модели —
        # это второй ответ в чат и второй счёт за токены.
        SimpleRetryMiddleware(default_retry_count=2),
    )


#: Брокер процесса. Собирается на импорте: ``taskiq`` CLI ищет его как
#: атрибут модуля, а ``@broker.task`` прибивает задачу к экземпляру.
broker: AsyncBroker = create_broker()


def distributed() -> bool:
    """Задачи уходят в отдельный процесс, а не исполняются здесь же."""
    return not isinstance(broker, InMemoryBroker)


@contextlib.asynccontextmanager
async def broker_client() -> AsyncIterator[AsyncBroker]:
    """Брокер со стороны отправителя.

    ``is_worker_process = False`` обязателен: иначе taskiq на старте
    поднимет приёмник, и процесс бота начнёт разбирать собственную
    очередь — ровно то, от чего мы уходим.
    """
    broker.is_worker_process = False
    await broker.startup()
    try:
        yield broker
    finally:
        await broker.shutdown()
