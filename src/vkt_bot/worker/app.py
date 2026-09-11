"""Цель для ``taskiq worker`` и ``taskiq scheduler``.

Импорт модуля собирает приложение целиком. Так, а не обработчиком
``WORKER_STARTUP``: taskiq строит карту задач сразу после импорта цели, а
``LabelScheduleSource`` читает метки ``schedule=`` один раз — задача,
зарегистрированная позже, в расписание не попадёт, и чистки просто не
запустятся, молча.

Запускается CLI, а не своей точкой входа: программный запуск требует
полуприватного ``taskiq.cli.worker.run`` и теряет ``--reload``, форк
процессов и обработку сигналов. Это та же схема, по которой uvicorn
поднимает ``create_app``.
"""

from __future__ import annotations

from vkt_bot.bootstrap import bootstrap, check_settings

# До импорта брокера: он читает настройки на импорте, и без проверки
# пользователь получил бы трейсбек pydantic вместо списка переменных.
check_settings()

from taskiq import TaskiqEvents, TaskiqScheduler, TaskiqState  # noqa: E402
from taskiq.schedule_sources import LabelScheduleSource  # noqa: E402

from vkt_bot.worker import tasks  # noqa: E402, F401 — задачи ядра
from vkt_bot.worker.broker import broker  # noqa: E402

# Хендлеры, модели, типы событий и задачи плагинов. Без этого воркер не
# знает ни одной задачи агента, а бот в нём — без ``event_sink``.
bootstrap()

scheduler = TaskiqScheduler(broker, sources=[LabelScheduleSource(broker)])


@broker.on_event(TaskiqEvents.WORKER_SHUTDOWN)
async def _close_bot(state: TaskiqState) -> None:  # noqa: ARG001
    """Закрыть HTTP-сессию бота: её открыл этот процесс, ему и закрывать."""
    from vkt_bot.app import bot

    await bot.close()
