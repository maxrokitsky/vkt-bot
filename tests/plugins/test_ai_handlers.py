"""Команда ``/ai``, фоновый запуск и продолжение диалога."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest
from pydantic_ai.messages import ModelResponse, TextPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from vkteams_client.enums import ChatAction

from vkt_agent import AgentRunner
from vkt_ai import agent as agent_module
from vkt_ai import handlers as handlers_module
from vkt_ai import session as session_module
from vkt_ai.events import install_events
from vkt_ai.handlers import AgentConversationHandler, AskAgentHandler
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
BOT_ID = "1011835311"


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
def asked(monkeypatch: pytest.MonkeyPatch) -> list[SessionRequest]:
    """Что хендлер отправил в фоновую задачу.

    Сама задача не запускается: хендлер отвечает за решение — кому, о чём
    и продолжаем ли начатое, — а не за сессию. Запустить её здесь и нельзя:
    тестовая сессия сидит на одном соединении с внешней транзакцией, и
    второй параллельный запрос по нему вешает тест.

    Заодно проверяется главное: ждать задачу внутри хендлера нельзя — пока
    агент думает, опрос событий стоит и бот молчит во всех чатах.
    """
    captured: list[SessionRequest] = []

    def record(bot: Any, request: SessionRequest) -> Coroutine[Any, Any, None]:  # noqa: ARG001
        captured.append(request)

        async def noop() -> None: ...

        return noop()

    monkeypatch.setattr(handlers_module, "run_session", record)
    monkeypatch.setattr(handlers_module, "spawn", lambda coro: coro.close())
    return captured


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
        self, fake_bot: FakeBot, asked: list[SessionRequest]
    ) -> None:
        await AskAgentHandler.callback(fake_bot, ai_event("/ai"))

        assert "Спроси меня" in fake_bot.texts[0]
        assert asked == []

    async def test_spawns_without_answering(
        self, fake_bot: FakeBot, asked: list[SessionRequest]
    ) -> None:
        """Пока агент думает, в чате висит «печатает…».

        Сообщение-заглушка выглядело бы как ответ, которым не является, —
        и оставалась бы в переписке навсегда.
        """
        await AskAgentHandler.callback(fake_bot, ai_event())

        assert fake_bot.texts == []
        assert len(asked) == 1

    async def test_disabled_agent_says_so(
        self,
        fake_bot: FakeBot,
        asked: list[SessionRequest],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setattr(agent_module, "configured", lambda: False)

        await AskAgentHandler.callback(fake_bot, ai_event())

        assert "выключен" in fake_bot.texts[0]
        assert asked == []

    async def test_daily_budget_refuses(
        self,
        session: AsyncSession,
        fake_bot: FakeBot,
        asked: list[SessionRequest],
        monkeypatch: pytest.MonkeyPatch,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Превышение суточного бюджета — отказ и предупреждение в журнал."""
        monkeypatch.setattr(handlers_module, "over_budget", _always_over)

        with caplog.at_level("WARNING", logger="vkt_bot.events"):
            await AskAgentHandler.callback(fake_bot, ai_event())

        assert "лимит" in fake_bot.texts[0]
        assert asked == []
        assert "agent.limit_exceeded" in caplog.text


async def _always_over(db: Any, user_id: str) -> bool:  # noqa: ARG001
    """Бюджет исчерпан."""
    return True


@pytest.mark.usefixtures("enabled", "runner")
class TestSession:
    """Фоновая сессия."""

    async def test_answers_with_a_message(
        self, session: AsyncSession, fake_bot: FakeBot
    ) -> None:
        await run_session(
            fake_bot,
            SessionRequest(chat_id=CHAT, user_id=USER, question="кто дежурный?"),
        )

        assert fake_bot.texts == ["Дежурный — Иван."]

    async def test_holds_the_typing_indicator(
        self, session: AsyncSession, fake_bot: FakeBot
    ) -> None:
        """Индикатор поднимается на время работы и гасится после."""
        await run_session(
            fake_bot,
            SessionRequest(chat_id=CHAT, user_id=USER, question="кто дежурный?"),
        )

        actions = [call.args[1:] for call in fake_bot.calls_of("send_actions")]
        assert actions[0] == (ChatAction.TYPING,)
        assert actions[-1] == ()

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
            fake_bot, SessionRequest(chat_id=CHAT, user_id=USER, question="?")
        )

        # Якорь — сообщение с ответом: продолжение уходит в обсуждение
        # под ним, а не отдельной веткой в общем чате.
        assert fake_bot.calls_of("threads_add")[0].kwargs["msg_id"] == "bot-msg-1"
        row = (await AgentSessionRepository(session).list())[0]
        assert row.thread_id == "999@chat.agent"

    async def test_no_thread_inside_a_thread(
        self, session: AsyncSession, fake_bot: FakeBot
    ) -> None:
        """Вложенных обсуждений не бывает — вызывать ``threads/add`` незачем."""
        await run_session(
            fake_bot,
            SessionRequest(
                chat_id=CHAT, user_id=USER, question="?", chat_is_thread=True
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


@pytest.fixture
def bot_dispatcher(fake_bot: FakeBot) -> Any:
    """Диспетчер, знающий, как зовут самого бота.

    Без ``info`` упоминание не с чем сравнивать: там лежат ``userId`` и
    ``nick``, которые бот узнаёт у API при старте.
    """
    from vkteams_client.types import GetSelfResponse
    from vkt_dispatcher import Dispatcher

    dispatcher = Dispatcher(bot=fake_bot)  # type: ignore[arg-type]
    dispatcher.info = GetSelfResponse(
        ok=True, firstName="Бот", nick="max_test_bot", userId=BOT_ID
    )
    return dispatcher


@pytest.mark.usefixtures("enabled", "runner", "session_factory")
class TestConversation:
    """Разговор без команды: продолжение в треде и обращение по упоминанию."""

    async def test_message_in_active_thread_continues(
        self,
        session: AsyncSession,
        bot_dispatcher: Any,
        asked: list[SessionRequest],
    ) -> None:
        await create_chat_user(session, USER)
        row = await AgentSessionRepository(session).create(
            {"chat_id": CHAT, "user_id": USER, "thread_id": "999@chat.agent"}
        )
        await session.commit()

        await AgentConversationHandler.handle(
            make_event("new_message", chat={"chatId": "999@chat.agent"}, text="а ещё?"),
            bot_dispatcher,
        )

        assert len(asked) == 1
        assert row.id is not None

    async def test_plain_message_elsewhere_is_ignored(
        self, bot_dispatcher: Any, fake_bot: FakeBot, asked: list[SessionRequest]
    ) -> None:
        await AgentConversationHandler.handle(make_event("new_message"), bot_dispatcher)

        assert asked == []
        assert fake_bot.calls == []

    async def test_mention_by_id_starts_a_session(
        self, bot_dispatcher: Any, fake_bot: FakeBot, asked: list[SessionRequest]
    ) -> None:
        """Команда — барьер: боту пишут как человеку, через `@`."""
        await AgentConversationHandler.handle(
            make_event("new_message", text=f"@[{BOT_ID}] кто дежурный?"),
            bot_dispatcher,
        )

        assert fake_bot.texts == []
        assert len(asked) == 1

    async def test_mention_by_nick_starts_a_session(
        self, bot_dispatcher: Any, asked: list[SessionRequest]
    ) -> None:
        """Ник печатают руками, не выбирая из списка — скобок тогда нет."""
        await AgentConversationHandler.handle(
            make_event("new_message", text="@max_test_bot, кто дежурный?"),
            bot_dispatcher,
        )

        assert len(asked) == 1

    async def test_mention_by_markup_starts_a_session(
        self, bot_dispatcher: Any, asked: list[SessionRequest]
    ) -> None:
        """Разметка `format.mention` не зависит от вида упоминания в тексте."""
        await AgentConversationHandler.handle(
            make_event(
                "new_message",
                text="Бот Ассистент, кто дежурный?",
                format={"mention": [{"offset": 0, "length": 13}]},
            ),
            bot_dispatcher,
        )

        assert len(asked) == 1
        assert asked[0].question == "кто дежурный?"

    async def test_mention_of_a_similar_nick_is_not_ours(
        self, bot_dispatcher: Any, asked: list[SessionRequest]
    ) -> None:
        """`@max_test_bot2` — сосед, а не мы."""
        await AgentConversationHandler.handle(
            make_event("new_message", text="@max_test_bot2 привет"), bot_dispatcher
        )

        assert asked == []

    async def test_mention_is_stripped_from_the_question(
        self, bot_dispatcher: Any, asked: list[SessionRequest]
    ) -> None:
        """Модель не должна разбираться, что значит `@[1011835311]`."""
        await AgentConversationHandler.handle(
            make_event("new_message", text=f"@[{BOT_ID}], кто дежурный?"),
            bot_dispatcher,
        )

        assert asked[0].question == "кто дежурный?"

    async def test_mention_without_a_question_shows_help(
        self, bot_dispatcher: Any, fake_bot: FakeBot, asked: list[SessionRequest]
    ) -> None:
        """Позвали и ничего не спросили — рассказываем, о чём можно."""
        await AgentConversationHandler.handle(
            make_event("new_message", text=f"@[{BOT_ID}]"), bot_dispatcher
        )

        assert "Спроси меня" in fake_bot.texts[0]
        assert asked == []

    async def test_commands_are_left_to_their_handlers(
        self,
        session: AsyncSession,
        bot_dispatcher: Any,
        asked: list[SessionRequest],
    ) -> None:
        """Команда внутри треда сессии — команда, а не реплика агенту."""
        await create_chat_user(session, USER)
        await AgentSessionRepository(session).create(
            {"chat_id": CHAT, "user_id": USER, "thread_id": "999@chat.agent"}
        )
        await session.commit()

        await AgentConversationHandler.handle(
            make_event("new_message", chat={"chatId": "999@chat.agent"}, text="/help"),
            bot_dispatcher,
        )

        assert asked == []

    async def test_other_bots_are_ignored(
        self, bot_dispatcher: Any, asked: list[SessionRequest]
    ) -> None:
        """Два бота, упомянувшие друг друга, переписывались бы вечно."""
        await AgentConversationHandler.handle(
            make_event("new_message_from_bot", text=f"@[{BOT_ID}] кто дежурный?"),
            bot_dispatcher,
        )

        assert asked == []

    async def test_private_chat_is_off_by_default(
        self, bot_dispatcher: Any, asked: list[SessionRequest]
    ) -> None:
        """Иначе каждая реплика в личке — оплаченный вызов модели."""
        await AgentConversationHandler.handle(
            make_event("new_message_private", text="просто вопрос"), bot_dispatcher
        )

        assert asked == []

    async def test_private_chat_when_enabled(
        self,
        bot_dispatcher: Any,
        asked: list[SessionRequest],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from vkt_ai import config

        settings = config.get_ai_settings().model_copy(
            update={"reply_in_private": True}
        )
        monkeypatch.setattr(handlers_module, "get_ai_settings", lambda: settings)

        await AgentConversationHandler.handle(
            make_event("new_message_private", text="просто вопрос"), bot_dispatcher
        )

        assert len(asked) == 1

    async def test_mention_ignored_when_agent_disabled(
        self,
        bot_dispatcher: Any,
        asked: list[SessionRequest],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """Выключенный агент молчит, а не отвечает «выключен» на каждый `@`."""
        monkeypatch.setattr(agent_module, "configured", lambda: False)

        await AgentConversationHandler.handle(
            make_event("new_message", text=f"@[{BOT_ID}] кто дежурный?"),
            bot_dispatcher,
        )

        assert asked == []

    async def test_budget_refuses(
        self,
        bot_dispatcher: Any,
        fake_bot: FakeBot,
        asked: list[SessionRequest],
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        async def spent(db: Any, user_id: str) -> bool:  # noqa: ARG001
            return True

        monkeypatch.setattr(handlers_module, "over_budget", spent)

        await AgentConversationHandler.handle(
            make_event("new_message", text=f"@[{BOT_ID}] кто дежурный?"),
            bot_dispatcher,
        )

        assert "лимит" in fake_bot.texts[0]
        assert asked == []
