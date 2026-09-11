"""Цель для ``taskiq worker`` и ``taskiq scheduler``."""

from __future__ import annotations

import pytest
from taskiq import TaskiqScheduler


@pytest.fixture(autouse=True)
def _built(app: object) -> None:  # noqa: ARG001
    """Собрать приложение до импорта цели.

    ``vkt_bot.worker.app`` зовёт ``bootstrap()`` на импорте, а тот
    настраивает логирование по-боевому и утащил бы за собой вывод pytest.
    Фикстура ``app`` делает сборку заранее и с заглушкой вместо
    ``init_logging``; повторный вызов ничего не делает.
    """


class TestWorkerApp:
    """Импорт модуля собирает приложение целиком."""

    async def test_scheduler_sees_the_cron_tasks(self) -> None:
        """Импорт — и есть вся подготовка воркера.

        Сборка стоит на уровне модуля, а не в ``WORKER_STARTUP``: taskiq
        строит карту задач сразу после импорта цели, а
        ``LabelScheduleSource`` читает метки один раз. Задача,
        зарегистрированная позже, в расписание не попала бы — молча.
        """
        from vkt_bot.worker import app as worker_app

        assert isinstance(worker_app.scheduler, TaskiqScheduler)

        source = worker_app.scheduler.sources[0]
        await source.startup()

        names = {task.task_name for task in await source.get_schedules()}
        assert {"vkt_bot.retention", "vkt_ai.purge_sessions"} <= names

    async def test_shutdown_closes_the_bot(self) -> None:
        """HTTP-сессию открыл этот процесс — ему и закрывать."""
        from vkt_bot.worker import app as worker_app

        closed: list[str] = []

        class Spy:
            async def close(self) -> None:
                closed.append("closed")

        import vkt_bot.app as app_module

        original = app_module.bot
        app_module.bot = Spy()  # type: ignore[assignment]
        try:
            await worker_app._close_bot(None)
        finally:
            app_module.bot = original

        assert closed == ["closed"]
