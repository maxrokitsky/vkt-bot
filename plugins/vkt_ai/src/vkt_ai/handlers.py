"""Как с агентом заговаривают: команда, упоминание, продолжение.

Хендлеры делают только дешёвую часть: проверяют, что агент включён и что
лимит не исчерпан, отвечают «думаю…» и ставят фоновую задачу. Ждать
модель внутри хендлера нельзя — пока агент думает, ``start_polling``
не забирает новые события, и бот молчит во всех чатах сразу.
"""

from __future__ import annotations

from typing import Any, ClassVar

import structlog

from vkteams_client import VKTeams
from vkteams_client.enums import ChatType
from vkteams_client.types import Bot, Event, GetSelfResponse, NewMessageEvent
from sqlalchemy.ext.asyncio import AsyncSession

from vkt_bot.app import dispatcher
from vkt_bot.core.events import Actor, emit
from vkt_bot.core.threads import is_thread
from vkt_bot.db.session import async_session
from vkt_bot.utils.message import mention
from vkt_dispatcher import Dispatcher
from vkt_dispatcher.handlers import CommandHandler, MessageHandler

from . import events as ai_events
from .agent import agent_enabled, configured
from .config import AiSettings, get_ai_settings
from .mentions import mentions_bot, spans_of, strip_mention
from .repositories import AgentSessionRepository
from .session import SessionRequest, day_start, run_session
from .tasks import spawn

logger = structlog.get_logger("vkt_ai.handlers")

HELP = """
Спроси меня о том, что бот знает: роли, состав чатов, журнал событий,
переписка этого чата.

`/ai кто дежурный и в каких он чатах?`
`о чём тут договорились?` — с упоминанием бота, команда не нужна
`/ai что происходило в этом чате вчера?`

Обращаться можно и без команды — просто упомяни меня. Отвечаю в
обсуждении под своим сообщением, там же можно продолжить разговор.
Чужую переписку не покажу: вижу только чаты, где ты состоишь.
""".strip()

DISABLED = "Агент сейчас выключен."


async def over_budget(db: AsyncSession, user_id: str) -> bool:
    """Исчерпан ли суточный бюджет токенов у этого участника.

    Считается по обоим направлениям сразу: платят и за вход, и за выход.
    """
    budget = get_ai_settings().daily_token_budget
    if budget <= 0:
        return False
    spent = await AgentSessionRepository(db).tokens_since(user_id, day_start())
    return spent >= budget


@dispatcher.register_handler
class AskAgentHandler(CommandHandler):
    """/ai — вопрос агенту."""

    commands: ClassVar[list[str]] = ["ai", "спроси"]
    description = "/ai `вопрос` - Спросить ИИ-агента"

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        payload = event.payload
        chat_id = payload.chat.chatId
        question = (payload.text or "").partition(" ")[2].strip()

        if not question:
            await bot.send_text(chat_id, HELP, parse_mode="MarkdownV2")
            return

        async with async_session() as db:
            if not await agent_enabled(db):
                await bot.send_text(chat_id, DISABLED)
                return
            exhausted = await over_budget(db, payload.sender.userId)
            if exhausted:
                await emit(
                    db,
                    ai_events.LIMIT_EXCEEDED,
                    actor=Actor.from_event(event),
                    chat_id=chat_id,
                    payload={"reason": "суточный бюджет токенов"},
                )
                await db.commit()
                await bot.send_text(
                    chat_id,
                    f"{mention(payload.sender.userId)}, на сегодня лимит "
                    "запросов к агенту исчерпан. Попробуй завтра.",
                )
                return

        # Проверка стоит запроса к API, но делается один раз на сессию:
        # от неё зависит, можно ли вообще выходить за пределы этого чата.
        chat_is_thread = await is_thread(bot, chat_id)

        # Ничего не отвечаем: пока агент думает, в чате висит
        # «печатает…». Сообщение-заглушка выглядело бы как ответ,
        # которым не является.
        spawn(
            run_session(
                bot,
                SessionRequest(
                    chat_id=chat_id,
                    user_id=payload.sender.userId,
                    question=question,
                    question_msg_id=payload.msgId,
                    chat_is_thread=chat_is_thread,
                    trace_id=structlog.contextvars.get_contextvars().get("trace_id"),
                ),
            )
        )


@dispatcher.register_handler
class AgentConversationHandler(MessageHandler):
    """Разговор с агентом без команды.

    Три повода ответить, в порядке проверки:

    1. сообщение в обсуждении активной сессии — продолжение диалога;
    2. бота упомянули (`@бот`) — новый вопрос;
    3. личка, если включено `AI_REPLY_IN_PRIVATE`, — там собеседник один.

    Поводы объединены в один обработчик намеренно. Двумя они срабатывали
    бы оба на «@бот» внутри треда сессии: два вопроса, два ответа, двойной
    расход. Заодно на каждое сообщение чата приходится один запрос к базе,
    а не два.

    ``handle`` переопределён вместо ``callback``: нужен ``dispatcher`` —
    в нём лежит ``info`` с идентификатором и ником самого бота, а без них
    упоминание не с чем сравнивать.
    """

    async def handle(self, event: Event, dispatcher: Dispatcher) -> None:
        if not isinstance(event, NewMessageEvent):
            return
        payload = event.payload
        text = (payload.text or "").strip()
        # Команды разбирают свои обработчики; пустое сообщение — вложение.
        if not text or text.startswith("/"):
            return
        # Своим и чужим ботам не отвечаем: два бота, упомянувшие друг
        # друга, устроят бесконечную переписку за наш счёт.
        if isinstance(payload.sender, Bot):
            return

        bot = dispatcher.bot
        me = dispatcher.info
        settings = get_ai_settings()

        async with async_session() as db:
            session_row = await AgentSessionRepository(db).active_by_thread(
                payload.chat.chatId
            )
            if session_row is None and not self.addressed(event, me, settings):
                return
            if not await agent_enabled(db):
                return
            session_id = session_row.id if session_row else None
            exhausted = await over_budget(db, payload.sender.userId)

        if exhausted:
            await bot.send_text(
                payload.chat.chatId,
                f"{mention(payload.sender.userId)}, на сегодня лимит запросов "
                "к агенту исчерпан. Попробуй завтра.",
            )
            return

        question = (
            strip_mention(text, **self.identity(event, me))
            if session_id is None
            else text
        )
        if not question:
            # Позвали, но ничего не спросили — рассказываем, о чём можно.
            await bot.send_text(payload.chat.chatId, HELP, parse_mode="MarkdownV2")
            return

        spawn(
            run_session(
                bot,
                SessionRequest(
                    chat_id=payload.chat.chatId,
                    user_id=payload.sender.userId,
                    question=question,
                    question_msg_id=payload.msgId,
                    # Продолжение всегда идёт в треде; новый вопрос по
                    # упоминанию — там, где его задали.
                    chat_is_thread=session_id is not None,
                    session_id=session_id,
                    trace_id=structlog.contextvars.get_contextvars().get("trace_id"),
                ),
            )
        )

    def identity(
        self, event: NewMessageEvent, me: GetSelfResponse | None
    ) -> dict[str, Any]:
        """По чему бот узнаёт обращение к себе.

        Идентификаторы из частей сообщения — точный источник; разметка и
        текст остаются на случай, когда частей нет (ник напечатали руками).
        """
        return {
            "user_id": me.userId if me else None,
            "nick": me.nick if me else None,
            "first_name": me.firstName if me else None,
            "spans": spans_of(event.payload.format),
            "mentioned_ids": [m.userId for m in event.payload.mentions],
        }

    def addressed(
        self,
        event: NewMessageEvent,
        me: GetSelfResponse | None,
        settings: AiSettings,
    ) -> bool:
        """Обращаются ли к боту.

        Проверка дешёвая и без сети: идентификатор и ник бота уже лежат в
        ``dispatcher.info`` с момента старта.
        """
        if settings.reply_in_private and event.payload.chat.type is ChatType.PRIVATE:
            return True
        if not settings.reply_on_mention or me is None:
            return False
        return mentions_bot(event.payload.text or "", **self.identity(event, me))


def install_handlers() -> None:
    """Заглушка для симметрии с остальными частями плагина.

    Хендлеры регистрируются самим импортом модуля — как в ядре.
    """
    if not configured():
        logger.info("agent.not_configured")
