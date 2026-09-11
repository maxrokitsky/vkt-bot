"""Суточная уборка по расписанию."""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import pytest
from taskiq.schedule_sources import LabelScheduleSource

from vkt_ai.jobs import purge_sessions
from vkt_bot.core.events.retention import purge_once
from vkt_bot.core.models.event import (
    ActorType,
    EventRecord,
    EventSeverity,
    EventSource,
)
from vkt_bot.worker.broker import broker
from vkt_bot.worker.retention import local_retention
from vkt_bot.worker.tasks import retention

from tests.conftest import table_count

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def old_event(days: int) -> EventRecord:
    return EventRecord(
        ts=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days),
        type="chat.registered",
        source=EventSource.BOT,
        severity=EventSeverity.INFO,
        actor_type=ActorType.SYSTEM,
        summary="старое",
    )


class TestSchedule:
    """Когда задачи просыпаются."""

    def test_core_cleanup_runs_at_night(self) -> None:
        """Удаление идёт большими пачками и держит блокировки."""
        assert retention.labels["schedule"] == [{"cron": "10 3 * * *"}]

    def test_agent_cleanup_does_not_collide(self) -> None:
        """Две тяжёлые чистки не должны бить по базе одновременно."""
        assert purge_sessions.labels["schedule"] == [{"cron": "40 3 * * *"}]

    async def test_scheduler_sees_both(self) -> None:
        """Забытый импорт — самый тихий способ потерять уборку.

        Всё зелёное, задача объявлена, а ночью ничего не происходит:
        ``LabelScheduleSource`` читает метки только у тех задач, которые
        успели зарегистрироваться.
        """
        source = LabelScheduleSource(broker)
        await source.startup()

        names = {task.task_name for task in await source.get_schedules()}

        assert {retention.task_name, purge_sessions.task_name} <= names


@pytest.mark.usefixtures("session_factory")
class TestRetentionTask:
    """Тело задачи уборки."""

    async def test_removes_old_events(self, session: AsyncSession) -> None:
        """Задачу можно позвать напрямую: декоратор оставляет функцию.

        Раньше здесь приходилось подменять чистку шпионом — вечный цикл
        ходил в базу параллельно тесту.
        """
        session.add(old_event(days=1000))
        await session.commit()

        await retention()

        assert await table_count(session, EventRecord) == 0

    async def test_failure_does_not_escape(
        self, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Сбой уборки — запись в журнал, а не падение: завтра ещё раз."""
        import vkt_bot.core.events.retention as retention_module

        async def boom(*args: object, **kwargs: object) -> int:
            msg = "база отвалилась"
            raise RuntimeError(msg)

        monkeypatch.setattr(retention_module, "purge_old_events", boom)

        with caplog.at_level("ERROR", logger="vkt_bot.events"):
            await purge_once()

        assert "events.purge_failed" in caplog.text


class TestLocalRetention:
    """Уборка в процессе бота — только там, где нет планировщика."""

    async def test_skipped_when_a_scheduler_is_around(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Иначе одно и то же удалялось бы дважды."""
        import vkt_bot.worker.retention as module

        started: list[str] = []
        monkeypatch.setattr(module, "distributed", lambda: True)
        monkeypatch.setattr(module, "retention_task", lambda: started.append("started"))

        async with local_retention():
            pass

        assert started == []

    async def test_runs_without_a_broker(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Без Redis планировщика нет вовсе — чистит сам бот."""
        import contextlib

        import vkt_bot.worker.retention as module

        started: list[str] = []

        @contextlib.asynccontextmanager
        async def fake_task():  # noqa: ANN202
            started.append("started")
            yield

        monkeypatch.setattr(module, "distributed", lambda: False)
        monkeypatch.setattr(module, "retention_task", fake_task)

        async with local_retention():
            pass

        assert started == ["started"]
