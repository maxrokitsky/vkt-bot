"""Сессия агента: то, что происходит в фоне.

Задача живёт вне хендлера, поэтому у неё своя сессия БД и свой контекст
логирования: копия контекста снимается в момент ``create_task``, и
``trace_id`` приходится прокидывать явно — иначе связь записи в панели с
логами рвётся.

Любое исключение здесь превращается в сообщение пользователю «не смог,
вот причина», а не в тишину.
"""

from __future__ import annotations

import dataclasses
import datetime
import uuid
from typing import TYPE_CHECKING, Any

import sqlalchemy as sa
import structlog
from pydantic_ai.messages import ModelMessagesTypeAdapter, ModelRequest, TextPart

from vkt_agent import AgentActor, AgentDeps
from vkt_bot.core.events import Actor, emit
from vkt_bot.core.messages import history_enabled
from vkt_bot.core.models.role import Role, RoleAssignment
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.core.threads import get_or_create_thread
from vkt_bot.db.session import async_session

from . import events as ai_events
from .agent import get_runner
from .config import get_ai_settings
from .context import build_context
from .models import AgentMessage, AgentSession, SessionStatus
from .activity import ChatActivity
from .prompts import build_prompt
from .repositories import (
    AgentMessageRepository,
    AgentSessionRepository,
    CreateAgentMessageSchema,
)
from .tasks import concurrency_limiter

if TYPE_CHECKING:
    from collections.abc import Mapping

    from pydantic_ai.messages import ModelMessage
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkteams_client import VKTeams

logger = structlog.get_logger("vkt_ai.session")


@dataclasses.dataclass(slots=True)
class SessionRequest:
    """Всё, что нужно фоновой задаче, чтобы отработать вопрос."""

    #: Чат, где задан вопрос. У обсуждения это ``chatId`` треда.
    chat_id: str
    #: Кто спрашивает.
    user_id: str
    question: str
    #: Сообщение с вопросом: из автоконтекста его убираем, чтобы не
    #: дублировать.
    question_msg_id: str | None = None
    #: Вопрос задан внутри обсуждения.
    chat_is_thread: bool = False
    #: Сообщение, на которое отвечали, — «Пётр Петров: текст». Без него
    #: «о чём это?» ответом на чужую реплику для модели бессмысленно.
    quoted: str | None = None
    #: Продолжение уже начатого диалога.
    session_id: uuid.UUID | None = None
    trace_id: str | None = None

    def as_payload(self) -> dict[str, Any]:
        """Запрос как JSON-совместимый словарь: он поедет через Redis.

        ``uuid`` приводится к строке руками: taskiq гонит аргумент через
        ``json.dumps``, а тот на ``UUID`` падает — причём падает уже
        внутри ``kiq()``, то есть в хендлере.
        """
        data = dataclasses.asdict(self)
        data["session_id"] = str(self.session_id) if self.session_id else None
        return data

    @classmethod
    def from_payload(cls, data: Mapping[str, Any]) -> SessionRequest:
        """Собрать запрос обратно.

        Неизвестные ключи отбрасываются намеренно: во время выкладки в
        очереди лежат сообщения, собранные предыдущей версией, и
        появившееся поле не должно ронять воркер.
        """
        known = {field.name for field in dataclasses.fields(cls)}
        kwargs = {key: value for key, value in data.items() if key in known}
        if kwargs.get("session_id"):
            kwargs["session_id"] = uuid.UUID(str(kwargs["session_id"]))
        return cls(**kwargs)


async def run_session(bot: VKTeams, request: SessionRequest) -> None:
    """Отработать вопрос и ответить в чат."""
    limiter = concurrency_limiter(get_ai_settings().max_concurrent)
    context = {"chat_id": request.chat_id, "user_id": request.user_id}
    if request.trace_id:
        context["trace_id"] = request.trace_id

    with structlog.contextvars.bound_contextvars(**context):
        async with limiter:
            try:
                await _run(bot, request)
            except Exception:
                logger.exception("agent.session_failed", chat_id=request.chat_id)
                await _say(
                    bot,
                    request,
                    "Не получилось ответить: внутренняя ошибка. Она записана в журнал.",
                )


async def _run(bot: VKTeams, request: SessionRequest) -> None:
    settings = get_ai_settings()

    async with async_session() as db:
        sessions = AgentSessionRepository(db)
        messages = AgentMessageRepository(db)

        row = await _session_row(db, request)
        actor = await _actor(db, request.user_id)
        history = await messages.history(row.id)

        deps = AgentDeps(
            session=db,
            actor=actor,
            chat_id=request.chat_id,
            bot=bot,
            thread_id=row.thread_id,
            chat_is_thread=request.chat_is_thread,
            history_enabled=await history_enabled(db, request.chat_id),
        )

        # Автоконтекст нужен только в начале разговора: дальше история
        # диалога уже несёт всё, что модель успела узнать.
        prompt = request.question
        if not history:
            chat_history = (
                await build_context(
                    db,
                    request.chat_id,
                    limit=settings.context_messages,
                    max_chars=settings.context_chars,
                    skip_msg_id=request.question_msg_id,
                )
                if deps.history_enabled
                else None
            )
            prompt = build_prompt(request.question, chat_history, request.quoted)

        # Индикатор «печатает…» держится ровно столько, сколько агент
        # работает, и гаснет сам на выходе из блока.
        async with ChatActivity(bot, request.chat_id) as activity:
            result = await get_runner().run(
                deps,
                prompt,
                message_history=_restore(history),
                on_step=activity.on_step,
            )

        for message in result.messages:
            db.add(_stored(row.id, message))
        await sessions.finish(
            row.id,
            SessionStatus.FAILED if result.error else SessionStatus.DONE,
            tokens_in=result.input_tokens,
            tokens_out=result.output_tokens,
        )

        if result.tools:
            await emit(
                db,
                ai_events.TOOL_CALLED,
                actor=Actor.external("agent"),
                chat_id=request.chat_id,
                entity=(ai_events.ENTITY_AGENT_SESSION, str(row.id)),
                payload={"tools": ", ".join(dict.fromkeys(result.tools))},
            )
        if result.error:
            await emit(
                db,
                ai_events.FAILED,
                chat_id=request.chat_id,
                entity=(ai_events.ENTITY_AGENT_SESSION, str(row.id)),
                payload={"reason": result.error},
            )
        else:
            await emit(
                db,
                ai_events.ANSWERED,
                chat_id=request.chat_id,
                entity=(ai_events.ENTITY_AGENT_SESSION, str(row.id)),
                payload={"tokens": result.input_tokens + result.output_tokens},
            )
        await db.commit()

        thread_id = row.thread_id
        session_id = row.id

    answer_msg_id = await _say(bot, request, result.output)

    # Тред заводится на сообщении-ответе: продолжение разговора уходит
    # туда, а в общем чате не появляется вторая ветка обсуждения.
    if thread_id is None and answer_msg_id and not request.chat_is_thread:
        await _open_thread(bot, request, session_id, answer_msg_id)


async def _session_row(db: AsyncSession, request: SessionRequest) -> AgentSession:
    """Строка сессии: продолжение существующей или новая."""
    sessions = AgentSessionRepository(db)
    if request.session_id is not None:
        row = await sessions.get_or_none(request.session_id)
        if row is not None:
            row.status = SessionStatus.ACTIVE
            db.add(row)
            return row

    # Внешний ключ на ``chat_users``: поток сообщений строк там не
    # создаёт, поэтому участника заводим сами.
    user = await ChatUserRepository(db).get_or_create(request.user_id)
    # Своим flush, до вставки сессии. Порядок вставок SQLAlchemy выводит из
    # связей между моделями, а связи здесь нет — только колонка с внешним
    # ключом, — и обе строки уходили одним flush в произвольном порядке.
    # На SQLite это проходило (внешние ключи там по умолчанию не
    # проверяются), а PostgreSQL отвечал ForeignKeyViolation: первый же
    # вопрос от незнакомого участника срывался.
    await db.flush()

    row = await sessions.create(
        {
            "chat_id": request.chat_id,
            "user_id": request.user_id,
            "thread_id": request.chat_id if request.chat_is_thread else None,
        }
    )
    await db.flush()
    await emit(
        db,
        ai_events.SESSION_STARTED,
        actor=Actor.from_user(user),
        chat_id=request.chat_id,
        entity=(ai_events.ENTITY_AGENT_SESSION, str(row.id)),
        payload={"question": request.question[:200]},
    )
    return row


async def _actor(db: AsyncSession, user_id: str) -> AgentActor:
    """Актор с уже вычисленными правами.

    Права считаются один раз и здесь, по той же семантике, что у
    ``AdminRequiredMixin``: владелец бота, ``is_superuser`` или роль
    ``admin``. Инструменту остаётся прочитать флаг — модель на него
    повлиять не может.
    """
    from vkt_bot.config import get_settings

    user = await ChatUserRepository(db).get_or_create(user_id)
    owner_id = get_settings().owner_id
    is_admin = bool(owner_id and user_id == owner_id) or user.is_superuser
    if not is_admin:
        is_admin = await _has_admin_role(db, user_id)
    return AgentActor(
        user_id=user_id, display_name=user.display_name, is_admin=is_admin
    )


async def _has_admin_role(db: AsyncSession, user_id: str) -> bool:
    """Есть ли у участника роль ``admin``."""
    stmt = (
        sa.select(RoleAssignment.id)
        .join(Role, Role.id == RoleAssignment.role_id)
        .where(
            RoleAssignment.user_id == user_id,
            sa.func.lower(Role.name) == "admin",
        )
        .limit(1)
    )
    return bool(await db.scalar(stmt))


def _restore(rows: list[AgentMessage]) -> list[ModelMessage]:
    """Собрать историю диалога для модели.

    Одного текста мало: в нём нет ни вызовов инструментов, ни их
    результатов, и на следующем шаге модель не помнила бы, что уже
    выяснила. Поэтому храним сообщение целиком.
    """
    restored: list[ModelMessage] = []
    for row in rows:
        if not row.raw:
            continue
        try:
            restored.extend(ModelMessagesTypeAdapter.validate_python(row.raw))
        except Exception:
            logger.warning("agent.history_unreadable", message_id=row.id)
    return restored


def _stored(session_id: uuid.UUID, message: ModelMessage) -> AgentMessage:
    """Сообщение диалога для базы."""
    role = "user" if isinstance(message, ModelRequest) else "assistant"
    texts = [
        part.content
        for part in message.parts
        if isinstance(part, TextPart) and part.content
    ]
    return AgentMessage(
        **CreateAgentMessageSchema(
            session_id=session_id,
            role=role,
            content="\n".join(texts) or None,
            raw=ModelMessagesTypeAdapter.dump_python([message], mode="json"),
        ).model_dump()
    )


async def _say(bot: VKTeams, request: SessionRequest, text: str) -> str | None:
    """Ответить в чат. Возвращает id сообщения — он же якорь обсуждения."""
    response = await bot.send_text(chat_id=request.chat_id, text=text)
    return response.msgId if response else None


async def _open_thread(
    bot: VKTeams,
    request: SessionRequest,
    session_id: uuid.UUID,
    anchor_msg_id: str,
) -> None:
    """Завести обсуждение на ответе — там продолжится разговор.

    ``threads/add`` работает как get-or-create, но не только читает: у
    сообщения без обсуждения он его создаст. Поэтому вызывается он строго
    на нашем сообщении-якоре и ни на каком другом.
    """
    thread_id = await get_or_create_thread(bot, request.chat_id, anchor_msg_id)
    async with async_session() as db:
        row = await AgentSessionRepository(db).get_or_none(session_id)
        if row is None:
            return
        # Якорь запоминаем в любом случае: по нему тред можно завести и
        # позже, а ``threads/add`` на том же сообщении вернёт тот же id.
        row.anchor_msg_id = anchor_msg_id
        if thread_id is not None:
            row.thread_id = thread_id
        db.add(row)
        await db.commit()


def day_start() -> datetime.datetime:
    """Начало текущих суток UTC — граница суточного бюджета."""
    now = datetime.datetime.now(datetime.UTC)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)
