"""Фоновые задачи, прогресс и чистка диалогов."""

from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING

import pytest
from vkteams_client.enums import ChatAction

from vkt_agent import Step, StepKind
from vkt_ai import activity as activity_module
from vkt_ai.activity import ChatActivity
from vkt_ai.models import AgentMessage, AgentSession
from vkt_ai.repositories import AgentSessionRepository
from vkt_ai.retention import purge_old_sessions
from vkt_ai.tasks import cancel_all, concurrency_limiter, spawn

from tests.conftest import table_count
from tests.factories import create_chat_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from tests.conftest import FakeBot

CHAT = "681869378@chat.agent"


class TestSpawn:
    """``spawn``."""

    async def test_runs_in_background(self) -> None:
        done = asyncio.Event()

        async def work() -> None:
            done.set()

        task = spawn(work())
        await task

        assert done.is_set()

    async def test_failure_is_logged_not_swallowed(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Тишина вместо ответа — худший исход, поэтому сбой видно в логах."""

        async def boom() -> None:
            msg = "упал"
            raise RuntimeError(msg)

        with caplog.at_level("ERROR", logger="vkt_ai.tasks"):
            task = spawn(boom())
            await asyncio.gather(task, return_exceptions=True)
            await asyncio.sleep(0)

        assert "agent.task_failed" in caplog.text

    async def test_cancel_all_stops_pending(self) -> None:
        """На остановке бота висящий вызов модели не должен держать процесс."""
        started = asyncio.Event()

        async def forever() -> None:
            started.set()
            await asyncio.sleep(3600)

        task = spawn(forever())
        await started.wait()

        await cancel_all()

        assert task.cancelled()

    def test_limiter_is_rebuilt_when_limit_changes(self) -> None:
        first = concurrency_limiter(2)
        assert concurrency_limiter(2) is first
        assert concurrency_limiter(3) is not first


class TestActivity:
    """Индикатор «печатает…» вместо сообщения-заглушки."""

    async def test_holds_typing_while_working(self, fake_bot: FakeBot) -> None:
        async with ChatActivity(fake_bot, CHAT):
            await _tick()

        calls = fake_bot.calls_of("send_actions")
        assert calls[0].args[1:] == (ChatAction.TYPING,)

    async def test_clears_actions_on_exit(self, fake_bot: FakeBot) -> None:
        """Пустые действия — «закончил». Спека просит сказать это один раз."""
        async with ChatActivity(fake_bot, CHAT):
            await _tick()

        last = fake_bot.calls_of("send_actions")[-1]
        assert last.args[1:] == ()
        assert [c.args[1:] for c in fake_bot.calls_of("send_actions")].count(()) == 1

    async def test_switches_to_looking_on_tool_call(self, fake_bot: FakeBot) -> None:
        """`looking` — пока агент ходит за данными, `typing` — пока отвечает."""
        async with ChatActivity(fake_bot, CHAT) as activity:
            await _tick()
            await activity.on_step(Step(kind=StepKind.TOOL_CALL, tool="user_roles"))
            await activity.on_step(Step(kind=StepKind.TOOL_RESULT, tool="user_roles"))

        sent = [c.args[1:] for c in fake_bot.calls_of("send_actions")]
        assert (ChatAction.LOOKING,) in sent
        assert sent.index((ChatAction.LOOKING,)) < sent.index(())

    async def test_same_action_is_not_resent_immediately(
        self, fake_bot: FakeBot
    ) -> None:
        """Спека просит слать при смене действия — а не на каждый шаг."""
        async with ChatActivity(fake_bot, CHAT) as activity:
            await _tick()
            before = len(fake_bot.calls_of("send_actions"))
            await activity.on_step(Step(kind=StepKind.TOOL_CALL, tool="a"))
            await activity.on_step(Step(kind=StepKind.TOOL_CALL, tool="b"))

        during = len(fake_bot.calls_of("send_actions")) - before
        # Одна смена на `looking` и одно гашение на выходе.
        assert during == 2

    async def test_repeats_while_working(
        self, fake_bot: FakeBot, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Сервер держит состояние недолго — его надо повторять."""
        monkeypatch.setattr(activity_module, "INTERVAL", 0)

        async with ChatActivity(fake_bot, CHAT):
            for _ in range(20):
                await asyncio.sleep(0)

        assert len(fake_bot.calls_of("send_actions")) > 2

    async def test_api_failure_does_not_break_the_session(
        self, fake_bot: FakeBot
    ) -> None:
        """Индикатор — украшение: не показать его хуже, чем не ответить."""
        fake_bot.errors["send_actions"] = RuntimeError("сеть")

        async with ChatActivity(fake_bot, CHAT) as activity:
            await _tick()
            await activity.on_step(Step(kind=StepKind.TOOL_CALL, tool="a"))

        assert fake_bot.calls_of("send_actions")


async def _tick() -> None:
    """Дать фоновой задаче индикатора отправить первое состояние."""
    for _ in range(5):
        await asyncio.sleep(0)


class TestRetention:
    """Чистка диалогов."""

    async def make_session(self, session: AsyncSession, days_ago: int) -> AgentSession:
        await create_chat_user(session, "u1")
        row = await AgentSessionRepository(session).create(
            {"chat_id": CHAT, "user_id": "u1"}
        )
        await session.flush()
        row.created_at = datetime.datetime.now(datetime.UTC).replace(
            tzinfo=None
        ) - datetime.timedelta(days=days_ago)
        session.add(row)
        session.add(AgentMessage(session_id=row.id, role="user", content="вопрос"))
        await session.commit()
        return row

    async def test_removes_old_dialogs(self, session: AsyncSession) -> None:
        await self.make_session(session, days_ago=100)

        removed = await purge_old_sessions(session, days=30)

        assert removed == 1
        assert await table_count(session, AgentSession) == 0

    async def test_messages_go_with_the_session(self, session: AsyncSession) -> None:
        """Сообщения без своей сессии смысла не имеют."""
        await self.make_session(session, days_ago=100)

        await purge_old_sessions(session, days=30)

        assert await table_count(session, AgentMessage) == 0

    async def test_fresh_dialogs_survive(self, session: AsyncSession) -> None:
        await self.make_session(session, days_ago=1)

        assert await purge_old_sessions(session, days=30) == 0
        assert await table_count(session, AgentSession) == 1

    async def test_zero_days_disables_purge(self, session: AsyncSession) -> None:
        await self.make_session(session, days_ago=999)

        assert await purge_old_sessions(session, days=0) == 0

    async def test_empty_table(self, session: AsyncSession) -> None:
        assert await purge_old_sessions(session, days=30) == 0
