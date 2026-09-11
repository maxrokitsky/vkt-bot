"""Вопрос агенту едет через очередь."""

from __future__ import annotations

import json
import uuid
from typing import TYPE_CHECKING, Any

import pytest

from vkt_ai import jobs as jobs_module
from vkt_ai.jobs import enqueue_session, purge_sessions, run_session_task
from vkt_ai.models import AgentSession
from vkt_ai.repositories import AgentSessionRepository
from vkt_ai.session import SessionRequest

from tests.conftest import table_count
from tests.factories import create_chat_user

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from tests.conftest import FakeBot

CHAT = "681869378@chat.agent"
USER = "1234567890"


def a_request(**fields: Any) -> SessionRequest:  # noqa: ANN401
    base: dict[str, Any] = {
        "chat_id": CHAT,
        "user_id": USER,
        "question": "кто дежурный?",
    }
    return SessionRequest(**(base | fields))


class TestPayload:
    """Запрос уезжает в другой процесс — значит, через JSON."""

    def test_round_trip_keeps_every_field(self) -> None:
        request = a_request(
            question_msg_id="msg-1",
            chat_is_thread=True,
            quoted="Пётр Петров: переносим релиз",
            session_id=uuid.uuid4(),
            trace_id="deadbeef",
        )

        payload = request.as_payload()

        assert json.loads(json.dumps(payload)) == payload
        assert SessionRequest.from_payload(payload) == request

    def test_uuid_becomes_a_string(self) -> None:
        """``json.dumps`` на ``UUID`` падает, и падает внутри ``kiq()``."""
        payload = a_request(session_id=uuid.uuid4()).as_payload()

        assert isinstance(payload["session_id"], str)
        assert isinstance(SessionRequest.from_payload(payload).session_id, uuid.UUID)

    def test_unknown_field_does_not_break_the_worker(self) -> None:
        """Во время выкладки в очереди лежат сообщения прошлой версии."""
        payload = a_request().as_payload() | {"mood": "весёлый"}

        assert SessionRequest.from_payload(payload) == a_request()


@pytest.mark.usefixtures("session_factory")
class TestEnqueue:
    """``enqueue_session``."""

    async def test_the_task_gets_the_same_request(
        self, monkeypatch: pytest.MonkeyPatch, patched_bot: FakeBot
    ) -> None:
        """Путь тот же, что в боевом брокере: dataclass → JSON → задача."""
        seen: list[tuple[Any, SessionRequest]] = []

        async def spy(bot: Any, request: SessionRequest) -> None:  # noqa: ANN401
            seen.append((bot, request))

        monkeypatch.setattr(jobs_module, "run_session", spy)
        request = a_request(session_id=uuid.uuid4(), trace_id="deadbeef")

        await enqueue_session(patched_bot, request)

        assert [r for _, r in seen] == [request]

    async def test_the_bot_is_taken_in_the_worker(
        self, monkeypatch: pytest.MonkeyPatch, patched_bot: FakeBot
    ) -> None:
        """Клиента задача берёт при выполнении, а не на импорте.

        Импорт на уровне модуля прибил бы к задаче тот экземпляр, который
        существовал на импорте, — мимо подмены и мимо своего цикла.
        """
        seen: list[Any] = []

        async def spy(bot: Any, request: SessionRequest) -> None:  # noqa: ANN401, ARG001
            seen.append(bot)

        monkeypatch.setattr(jobs_module, "run_session", spy)

        await run_session_task(a_request().as_payload())

        assert seen == [patched_bot]

    async def test_a_dead_queue_is_not_silence(
        self,
        monkeypatch: pytest.MonkeyPatch,
        fake_bot: FakeBot,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Тишина вместо ответа — худший исход, необъяснённая тем более."""

        async def boom(*args: object, **kwargs: object) -> None:
            msg = "redis лёг"
            raise ConnectionError(msg)

        monkeypatch.setattr(run_session_task, "kiq", boom)

        with caplog.at_level("ERROR", logger="vkt_ai.jobs"):
            await enqueue_session(fake_bot, a_request())

        assert "agent.enqueue_failed" in caplog.text
        assert "очередь задач недоступна" in fake_bot.texts[0]


@pytest.mark.usefixtures("session_factory")
class TestPurgeSessions:
    """Суточная чистка диалогов — теперь задача, а не вечный цикл."""

    async def test_removes_old_dialogs(self, session: AsyncSession) -> None:
        """Раньше отсчёт начинался заново при каждом перезапуске бота."""
        import datetime

        await create_chat_user(session, USER)
        row = await AgentSessionRepository(session).create(
            {"chat_id": CHAT, "user_id": USER}
        )
        await session.flush()
        long_ago = datetime.datetime.now(datetime.UTC).replace(
            tzinfo=None
        ) - datetime.timedelta(days=1000)
        row.created_at = long_ago
        row.updated_at = long_ago
        session.add(row)
        await session.commit()

        await purge_sessions()

        assert await table_count(session, AgentSession) == 0
