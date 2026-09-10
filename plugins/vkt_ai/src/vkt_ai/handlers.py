"""Команды и продолжение диалога.

Хендлеры делают только дешёвую часть: проверяют, что агент включён и что
лимит не исчерпан, отвечают «думаю…» и ставят фоновую задачу. Ждать
модель внутри хендлера нельзя — пока агент думает, ``start_polling``
не забирает новые события, и бот молчит во всех чатах сразу.
"""

from __future__ import annotations

from typing import ClassVar

import structlog

from vkteams_client import VKTeams
from vkteams_client.types import NewMessageEvent
from vkt_bot.app import dispatcher
from vkt_bot.core.events import Actor, emit
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.core.threads import is_thread
from vkt_bot.db.session import async_session
from vkt_bot.utils.message import mention
from vkt_dispatcher.handlers import CommandHandler, MessageHandler

from . import events as ai_events
from .agent import agent_enabled, configured
from .config import get_ai_settings
from .repositories import AgentSessionRepository
from .session import SessionRequest, day_start, run_session
from .tasks import spawn

logger = structlog.get_logger("vkt_ai.handlers")

THINKING = "🤔 думаю…"

HELP = """
Спроси меня о том, что бот знает: роли, состав чатов, журнал событий,
переписка этого чата.

`/ai кто дежурный и в каких он чатах?`
`/ai о чём тут договорились?`
`/ai что происходило в этом чате вчера?`

Отвечаю в обсуждении под своим сообщением — там же можно продолжить
разговор, уже без команды. Чужую переписку не покажу: вижу только чаты,
где ты состоишь.
""".strip()

DISABLED = "Агент сейчас выключен."


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
            over_budget = await self.over_budget(db, payload.sender.userId)
            if over_budget:
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

        response = await bot.send_text(chat_id, THINKING)
        spawn(
            run_session(
                bot,
                SessionRequest(
                    chat_id=chat_id,
                    user_id=payload.sender.userId,
                    question=question,
                    progress_msg_id=response.msgId if response else None,
                    question_msg_id=payload.msgId,
                    chat_is_thread=chat_is_thread,
                    trace_id=structlog.contextvars.get_contextvars().get("trace_id"),
                ),
            )
        )

    async def over_budget(self, db, user_id: str) -> bool:  # noqa: ANN001
        """Исчерпан ли суточный бюджет токенов у этого пользователя."""
        budget = get_ai_settings().daily_token_budget
        if budget <= 0:
            return False
        spent = await AgentSessionRepository(db).tokens_since(user_id, day_start())
        return spent >= budget


@dispatcher.register_handler
class AgentReplyHandler(MessageHandler):
    """Сообщение в обсуждении активной сессии продолжает разговор.

    Фильтр дешёвый — один запрос по индексу ``thread_id``, — в отличие от
    ``threads/subscribers/get``, который стоил бы запроса к API на каждое
    сообщение в любом чате.
    """

    async def callback(self, bot: VKTeams, event: NewMessageEvent) -> None:
        payload = event.payload
        text = (payload.text or "").strip()
        if not text or text.startswith("/"):
            return

        async with async_session() as db:
            session_row = await AgentSessionRepository(db).active_by_thread(
                payload.chat.chatId
            )
            if session_row is None:
                return
            # Свои же сообщения в тред не должны заводить новый круг.
            author = await ChatUserRepository(db).get_or_none(payload.sender.userId)
            if author is not None and author.is_bot:
                return
            if not await agent_enabled(db):
                return
            session_id = session_row.id

        response = await bot.send_text(payload.chat.chatId, THINKING)
        spawn(
            run_session(
                bot,
                SessionRequest(
                    chat_id=payload.chat.chatId,
                    user_id=payload.sender.userId,
                    question=text,
                    progress_msg_id=response.msgId if response else None,
                    question_msg_id=payload.msgId,
                    chat_is_thread=True,
                    session_id=session_id,
                    trace_id=structlog.contextvars.get_contextvars().get("trace_id"),
                ),
            )
        )


def install_handlers() -> None:
    """Заглушка для симметрии с остальными частями плагина.

    Хендлеры регистрируются самим импортом модуля — как в ядре.
    """
    if not configured():
        logger.info("agent.not_configured")
