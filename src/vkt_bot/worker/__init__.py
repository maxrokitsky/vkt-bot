"""Очередь задач: то, что исполняется вне процесса бота.

Сам брокер сюда не реэкспортируется: имя ``broker`` затенило бы
одноимённый подмодуль, и ``vkt_bot.worker.broker`` перестало бы быть
модулем. Берите его как ``from vkt_bot.worker.broker import broker``.
"""

from .broker import broker_client, create_broker, distributed
from .retention import local_retention

__all__ = ("broker_client", "create_broker", "distributed", "local_retention")
