"""Фоновые задачи, прогресс и чистка диалогов."""

from __future__ import annotations

import asyncio
import datetime
from typing import TYPE_CHECKING

import pytest
from vkteams_client.types import MsgResponse

from vkt_agent import Step, StepKind
from vkt_ai.models import AgentMessage, AgentSession
from vkt_ai.progress import MIN_INTERVAL, Progress
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


class TestProgress:
    """Правка одного сообщения по ходу работы."""

    async def test_first_step_is_shown(self, fake_bot: FakeBot) -> None:
        progress = Progress(fake_bot, CHAT, "msg-1")

        await progress.on_step(Step(kind=StepKind.TOOL_CALL, tool="chat_messages"))

        assert "читаю переписку" in fake_bot.calls_of("edit_text")[0].kwargs["text"]

    async def test_edits_are_throttled(self, fake_bot: FakeBot) -> None:
        """Чаще раза в две секунды правка упрётся в лимиты API."""
        progress = Progress(fake_bot, CHAT, "msg-1")

        await progress.on_step(Step(kind=StepKind.TOOL_CALL, tool="user_roles"))
        await progress.on_step(Step(kind=StepKind.TOOL_CALL, tool="find_chats"))

        assert len(fake_bot.calls_of("edit_text")) == 1
        assert MIN_INTERVAL > 0

    async def test_results_do_not_trigger_edits(self, fake_bot: FakeBot) -> None:
        progress = Progress(fake_bot, CHAT, "msg-1")

        await progress.on_step(Step(kind=StepKind.TOOL_RESULT, tool="user_roles"))

        assert fake_bot.calls_of("edit_text") == []

    async def test_without_message_nothing_is_edited(self, fake_bot: FakeBot) -> None:
        """Отправить «думаю…» могло не получиться — править тогда нечего."""
        progress = Progress(fake_bot, CHAT, None)

        await progress.edit("ответ")

        assert fake_bot.calls == []

    async def test_refusal_is_logged(
        self, fake_bot: FakeBot, caplog: pytest.LogCaptureFixture
    ) -> None:
        """``ok: false`` исключением не является — в логах это был бы успех."""
        fake_bot.results["edit_text"] = MsgResponse(ok=False, description="too old")
        progress = Progress(fake_bot, CHAT, "msg-1")

        with caplog.at_level("WARNING", logger="vkt_ai.progress"):
            await progress.edit("ответ")

        assert "agent.progress_edit_refused" in caplog.text


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
