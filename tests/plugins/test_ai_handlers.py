"""Команда ``/ai``, фоновый запуск и продолжение диалога."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from vkt_agent import AgentRunner
from vkt_ai import agent as agent_module
from vkt_ai import handlers as handlers_module
from vkt_ai import session as session_module
from vkt_ai.events import install_events
from vkt_ai.handlers import AgentReplyHandler, AskAgentHandler
from vkt_ai.models import AgentMessage, AgentSession, SessionStatus
from vkt_ai.repositories import AgentSessionRepository
from vkt_ai.session import SessionRequest, run_session
from vkt_ai.tools import registry

from tests.conftest import table_count
from tests.factories import create_chat_user, make_event

# Типы событий плагина регистрирует ``install()``; здесь приложение
# целиком не поднимается, поэтому регистрируем их сами.
install_events()

if TYPE_CHECKING:
    from collections.abc import Coroutine

    from sqlalchemy.ext.asyncio import AsyncSession

    from tests.conftest import FakeBot

CHAT = "681869378@chat.agent"
USER = "1234567890"


def answering(text: str = "Дежурный — Иван.") -> AgentRunner:
    """Раннер, который сразу отвечает текстом: сети в тестах нет.

    Стрим здесь обязателен: прогресс в чате переводит запрос в
    потоковый режим, и обычной ``FunctionModel`` этого мало.
    """

    def reply(messages: list[Any], info: AgentInfo) -> ModelResponse:  # noqa: ARG001
        return ModelResponse(parts=[TextPart(text)])

    async def stream(messages: list[Any], info: AgentInfo):  # noqa: ANN202, ARG001
        yield text

    return AgentRunner(
        FunctionModel(reply, stream_function=stream),
        registry=registry,
        instructions="Ты бот",
    )


@pytest.fixture
def spawned(monkeypatch: pytest.MonkeyPatch) -> list[Coroutine[Any, Any, Any]]:
    """Перехватить фоновые задачи: хендлер обязан только их ставить.

    Ждать задачу внутри хендлера нельзя — пока агент думает, опрос
    событий стоит, и бот молчит во всех чатах.
    """
    tasks: list[Coroutine[Any, Any, Any]] = []
    monkeypatch.setattr(handlers_module, "spawn", tasks.append)
    return tasks


@pytest.fixture
def enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Агент настроен и включён."""
    monkeypatch.setattr(agent_module, "configured", lambda: True)


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> AgentRunner:
    """Подменить агента отвечающей заглушкой."""
    stub = answering()
    monkeypatch.setattr(session_module, "get_runner", lambda: stub)
    return stub


def ai_event(text: str = "/ai кто дежурный?") -> Any:
    return make_event("new_message", text=text)


@pytest.mark.usefixtures("enabled", "session_factory")
class TestAskCommand:
    """``/ai``."""

    async def test_without_question_shows_help(
        self, fake_bot: FakeBot, spawned: list[Any]
    ) -> None:
        await AskAgentHandler.callback(fake_bot, ai_event("/ai"))

        assert "Спроси меня" in fake_bot.texts[0]
        assert spawned == []

    async def test_answers_immediately_and_spawns(
        self, fake_bot: FakeBot, spawned: list[Any]
    ) -> None:
        await AskAgentHandler.callback(fake_bot, ai_event())

        assert fake_bot.texts == ["🤔 думаю…"]
        assert len(spawned) == 1
        spawned[0].close()

    async def test_disabled_agent_says_so(
        self,
        fake_bot: FakeBot,
        spawned: list[Any],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(agent_module, "configured", lambda: False)

        await AskAgentHandler.callback(fake_bot, ai_event())

        assert "выключен" in fake_bot.texts[0]
        assert spawned == []

    async def test_daily_budget_refuses(
        self,
        session: AsyncSession,
        fake_bot: FakeBot,
        spawned: list[Any],
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Превышение суточного бюджета — отказ и предупреждение в журнал."""
        monkeypatch.setattr(
            handlers_module.AskAgentHandler, "over_budget", _always_over
        )

        with caplog.at_level("WARNING", logger="vkt_bot.events"):
            await AskAgentHandler.callback(fake_bot, ai_event())

        assert "лимит" in fake_bot.texts[0]
        assert spawned == []
        assert "agent.limit_exceeded" in caplog.text


async def _always_over(db: Any, user_id: str) -> bool:  # noqa: ARG001
    """Бюджет исчерпан. Подменяется у экземпляра, поэтому без ``self``."""
    return True


@pytest.mark.usefixtures("enabled", "runner")
class TestSession:
    """Фоновая сессия."""

    async def test_answers_by_editing_the_message(
        self, session: AsyncSession, fake_bot: FakeBot
    ) -> None:
        await run_session(
            fake_bot,
            SessionRequest(
                chat_id=CHAT,
                user_id=USER,
                question="кто дежурный?",
                progress_msg_id="msg-1",
            ),
        )

        edits = fake_bot.calls_of("edit_text")
        assert edits
        assert edits[-1].kwargs["text"] == "Дежурный — Иван."

    async def test_writes_session_and_messages(
        self, session: AsyncSession, fake_bot: FakeBot
    ) -> None:
        await run_session(
            fake_bot,
            SessionRequest(chat_id=CHAT, user_id=USER, question="кто дежурный?"),
        )

        assert await table_count(session, AgentSession) == 1
        assert await table_count(session, AgentMessage) > 0
        row = (await AgentSessionRepository(session).list())[0]
        assert row.status is SessionStatus.DONE
        assert row.tokens_in > 0

    async def test_creates_chat_user_for_unknown_author(
        self, session: AsyncSession, fake_bot: FakeBot
    ) -> None:
        """Внешний ключ на ``chat_users``: строку заводим сами."""
        from vkt_bot.core.repositories.user import ChatUserRepository

        await run_session(
            fake_bot,
            SessionRequest(chat_id=CHAT, user_id="newbie@example.com", question="?"),
        )

        assert await ChatUserRepository(session).get_or_none("newbie@example.com")

    async def test_opens_thread_for_follow_ups(
        self, session: AsyncSession, fake_bot: FakeBot
    ) -> None:
        """Тред заводится на сообщении-ответе — там продолжится разговор."""
        from vkteams_client.types import ThreadAddResponse

        fake_bot.results["threads_add"] = ThreadAddResponse(
            ok=True, threadId="999@chat.agent"
        )

        await run_session(
            fake_bot,
            SessionRequest(
                chat_id=CHAT, user_id=USER, question="?", progress_msg_id="msg-1"
            ),
        )

        assert fake_bot.calls_of("threads_add")[0].kwargs["msg_id"] == "msg-1"
        row = (await AgentSessionRepository(session).list())[0]
        assert row.thread_id == "999@chat.agent"

    async def test_no_thread_inside_a_thread(
        self, session: AsyncSession, fake_bot: FakeBot
    ) -> None:
        """Вложенных обсуждений не бывает — вызывать ``threads/add`` незачем."""
        await run_session(
            fake_bot,
            SessionRequest(
                chat_id=CHAT,
                user_id=USER,
                question="?",
                progress_msg_id="msg-1",
                chat_is_thread=True,
            ),
        )

        assert fake_bot.calls_of("threads_add") == []

    async def test_failure_becomes_a_message(
        self,
        session: AsyncSession,
        fake_bot: FakeBot,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Тишина вместо ответа — худший исход."""

        def boom() -> AgentRunner:
            msg = "шлюз лёг"
            raise RuntimeError(msg)

        monkeypatch.setattr(session_module, "get_runner", boom)

        await run_session(
            fake_bot, SessionRequest(chat_id=CHAT, user_id=USER, question="?")
        )

        assert any("ошибка" in text for text in fake_bot.texts)


@pytest.mark.usefixtures("enabled", "runner", "session_factory")
class TestReplyInThread:
    """Продолжение диалога."""

    async def test_message_in_active_thread_continues(
        self, session: AsyncSession, fake_bot: FakeBot, spawned: list[Any]
    ) -> None:
        await create_chat_user(session, USER)
        row = await AgentSessionRepository(session).create(
            {"chat_id": CHAT, "user_id": USER, "thread_id": "999@chat.agent"}
        )
        await session.commit()

        await AgentReplyHandler.callback(
            fake_bot,
            make_event("new_message", chat={"chatId": "999@chat.agent"}, text="а ещё?"),
        )

        assert len(spawned) == 1
        spawned[0].close()
        assert row.id is not None

    async def test_message_elsewhere_is_ignored(
        self, session: AsyncSession, fake_bot: FakeBot, spawned: list[Any]
    ) -> None:
        await AgentReplyHandler.callback(fake_bot, make_event("new_message"))

        assert spawned == []
        assert fake_bot.calls == []

    async def test_commands_are_left_to_their_handlers(
        self, session: AsyncSession, fake_bot: FakeBot, spawned: list[Any]
    ) -> None:
        await create_chat_user(session, USER)
        await AgentSessionRepository(session).create(
            {"chat_id": CHAT, "user_id": USER, "thread_id": "999@chat.agent"}
        )
        await session.commit()

        await AgentReplyHandler.callback(
            fake_bot,
            make_event("new_message", chat={"chatId": "999@chat.agent"}, text="/help"),
        )

        assert spawned == []
