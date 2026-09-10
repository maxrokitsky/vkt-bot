"""Таблицы агента: сессия, её сообщения и вызовы инструментов."""

from __future__ import annotations

import datetime
import enum
import uuid

import sqlalchemy as sa
from sqlalchemy import orm

from vkt_bot.core.models.event import enum_column
from vkt_bot.db.base import Model


class SessionStatus(enum.StrEnum):
    """Состояние сессии."""

    ACTIVE = "active"
    #: Агент упёрся в мутирующий инструмент и ждёт кнопки. Задача при
    #: этом **завершается**: пользователь может не нажать никогда.
    WAITING_APPROVAL = "waiting_approval"
    DONE = "done"
    FAILED = "failed"
    CANCELED = "canceled"


class ToolCallStatus(enum.StrEnum):
    """Состояние вызова инструмента."""

    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"
    EXECUTED = "executed"
    FAILED = "failed"


class AgentSession(Model):
    """Диалог с агентом.

    Ключ диалога — обсуждение: у треда свой ``chatId``, и в групповом
    чате это снимает вопрос «кому бот сейчас отвечает». В личке треда
    нет, поэтому сессия ключуется по ``chat_id``.
    """

    __tablename__ = "agent_sessions"

    id: orm.Mapped[uuid.UUID] = orm.mapped_column(primary_key=True, default=uuid.uuid4)
    #: Чат, где задан вопрос. Без внешнего ключа: у обсуждения свой
    #: ``chatId``, которого в ``chats`` нет.
    chat_id: orm.Mapped[str] = orm.mapped_column(index=True)
    user_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("chat_users.id"))
    #: Обсуждение, в котором идёт разговор.
    thread_id: orm.Mapped[str | None] = orm.mapped_column(index=True, default=None)
    #: Сообщение-якорь треда: ``threads/add`` по нему вернёт тот же
    #: ``threadId``, поэтому соответствие хранить не нужно.
    anchor_msg_id: orm.Mapped[str | None] = orm.mapped_column(default=None)
    status: orm.Mapped[SessionStatus] = orm.mapped_column(
        enum_column(SessionStatus), default=SessionStatus.ACTIVE
    )
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now(), index=True
    )
    updated_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now(), onupdate=sa.func.now()
    )
    tokens_in: orm.Mapped[int] = orm.mapped_column(default=0, server_default="0")
    tokens_out: orm.Mapped[int] = orm.mapped_column(default=0, server_default="0")

    messages: orm.Mapped[list[AgentMessage]] = orm.relationship(
        back_populates="session", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<AgentSession {self.id} {self.status}>"


class AgentMessage(Model):
    """Сообщение диалога.

    ``content`` — человекочитаемый текст для панели, ``raw`` — то же
    сообщение в формате pydantic-ai. Одного текста для продолжения
    разговора не хватает: в нём нет ни вызовов инструментов, ни их
    результатов, и модель на следующем шаге не помнила бы, что уже
    выяснила.
    """

    __tablename__ = "agent_messages"
    __table_args__ = (
        sa.Index("ix_agent_messages_session_created", "session_id", "created_at"),
    )

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)
    session_id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"), index=True
    )
    session: orm.Mapped[AgentSession] = orm.relationship(back_populates="messages")
    role: orm.Mapped[str] = orm.mapped_column(sa.String(16))
    content: orm.Mapped[str | None] = orm.mapped_column(sa.Text, default=None)
    tool_name: orm.Mapped[str | None] = orm.mapped_column(sa.String(64), default=None)
    usage: orm.Mapped[dict | None] = orm.mapped_column(sa.JSON, default=None)
    raw: orm.Mapped[list | None] = orm.mapped_column(sa.JSON, default=None)
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now()
    )


class AgentToolCall(Model):
    """Вызов инструмента: ожидающий подтверждения и уже исполненный.

    Аргументы здесь лежат, а в журнал событий не уходят: там оказались бы
    тексты и идентификаторы, а ``/api/events`` обычному участнику
    отдаётся без текстов сообщений — второй канал утечки не нужен.
    """

    __tablename__ = "agent_tool_calls"

    id: orm.Mapped[uuid.UUID] = orm.mapped_column(primary_key=True, default=uuid.uuid4)
    session_id: orm.Mapped[uuid.UUID] = orm.mapped_column(
        sa.ForeignKey("agent_sessions.id", ondelete="CASCADE"), index=True
    )
    tool_name: orm.Mapped[str] = orm.mapped_column(sa.String(64))
    args: orm.Mapped[dict | None] = orm.mapped_column(sa.JSON, default=None)
    status: orm.Mapped[ToolCallStatus] = orm.mapped_column(
        enum_column(ToolCallStatus), default=ToolCallStatus.PENDING
    )
    result: orm.Mapped[str | None] = orm.mapped_column(sa.Text, default=None)
    error: orm.Mapped[str | None] = orm.mapped_column(sa.Text, default=None)
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now()
    )
    decided_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(default=None)
    decided_by: orm.Mapped[str | None] = orm.mapped_column(default=None)
