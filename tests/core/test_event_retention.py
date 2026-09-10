"""Чистка журнала событий."""

from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING

import pytest

from vkt_bot.core.events.retention import (
    purge_old_events,
    retention_task,
    run_retention_loop,
)
from vkt_bot.core.models.event import (
    ActorType,
    EventRecord,
    EventSeverity,
    EventSource,
)
from vkt_bot.core.repositories.event import EventRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession


def old_event(
    days: int, severity: EventSeverity = EventSeverity.INFO, summary: str = "x"
) -> EventRecord:
    """Событие, записанное ``days`` дней назад."""
    return EventRecord(
        ts=datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=days),
        type="role.created",
        source=EventSource.PANEL,
        severity=severity,
        actor_type=ActorType.SYSTEM,
        summary=summary,
    )


class TestPurge:
    """``purge_old_events``."""

    async def test_removes_old_routine_events(self, session: AsyncSession) -> None:
        session.add_all(
            [old_event(100, summary="старое"), old_event(1, summary="свежее")]
        )
        await session.commit()

        removed = await purge_old_events(session, days=90)

        assert removed == 1
        assert [row.summary for row in await EventRepository(session).list()] == [
            "свежее"
        ]

    async def test_warnings_and_errors_survive(self, session: AsyncSession) -> None:
        """Именно их ищут, когда разбираются в старом инциденте."""
        session.add_all(
            [
                old_event(100, EventSeverity.WARNING, "предупреждение"),
                old_event(100, EventSeverity.ERROR, "ошибка"),
                old_event(100, EventSeverity.DEBUG, "отладка"),
            ]
        )
        await session.commit()

        removed = await purge_old_events(session, days=90)

        assert removed == 1
        assert {row.summary for row in await EventRepository(session).list()} == {
            "предупреждение",
            "ошибка",
        }

    async def test_zero_days_disables_the_purge(self, session: AsyncSession) -> None:
        session.add(old_event(1000))
        await session.commit()

        assert await purge_old_events(session, days=0) == 0
        assert len(list(await EventRepository(session).list())) == 1

    async def test_empty_table(self, session: AsyncSession) -> None:
        assert await purge_old_events(session, days=90) == 0


class TestLoop:
    """Фоновая задача."""

    async def test_calls_purge_and_stops_on_cancel(
        self, monkeypatch: pytest.MonkeyPatch, settings: object
    ) -> None:
        """Задача чистит журнал при старте и снимается вместе с ботом.

        Саму чистку здесь подменяем: тестовая сессия сидит на одном
        соединении с внешней транзакцией, и второй параллельный запрос
        по нему ломает изоляцию тестов.
        """
        import vkt_bot.core.events.retention as retention

        calls: list[int] = []

        async def spy(session: object, days: int) -> int:
            calls.append(days)
            return 0

        monkeypatch.setattr(retention, "purge_old_events", spy)

        async with retention_task(interval=3600) as task:
            for _ in range(5):
                await asyncio.sleep(0)

        assert calls == [settings.events_retention_days]
        assert task.cancelled() or task.done()

    async def test_failure_does_not_kill_the_loop(
        self,
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Сбой чистки не должен ронять бота — попробуем завтра."""
        import vkt_bot.core.events.retention as retention

        async def boom(*args: object, **kwargs: object) -> int:
            msg = "боом"
            raise RuntimeError(msg)

        monkeypatch.setattr(retention, "purge_old_events", boom)

        with caplog.at_level("ERROR", logger="vkt_bot.events"):
            task = asyncio.create_task(run_retention_loop(interval=3600))
            for _ in range(5):
                await asyncio.sleep(0)
            task.cancel()

        assert "events.purge_failed" in caplog.text
