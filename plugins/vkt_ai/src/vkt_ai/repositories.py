"""Репозитории агента."""

from __future__ import annotations

import datetime
import uuid
from typing import Any

import sqlalchemy as sa
from pydantic import BaseModel

from vkt_bot.db.repository import AsyncRepository

from .models import AgentMessage, AgentSession, AgentToolCall, SessionStatus


class CreateAgentSessionSchema(BaseModel):
    """CreateAgentSessionSchema."""

    chat_id: str
    user_id: str
    thread_id: str | None = None
    anchor_msg_id: str | None = None


class CreateAgentMessageSchema(BaseModel):
    """CreateAgentMessageSchema."""

    session_id: uuid.UUID
    role: str
    content: str | None = None
    tool_name: str | None = None
    usage: dict | None = None
    raw: list | None = None


class AgentSessionRepository(
    AsyncRepository[AgentSession, uuid.UUID, CreateAgentSessionSchema, Any]
):
    """AgentSession Repository."""

    async def active_by_thread(self, thread_id: str) -> AgentSession | None:
        """Живая сессия обсуждения.

        Проверка дешёвая — один запрос по индексу, — поэтому продолжение
        диалога ищется здесь, а не через ``threads/subscribers/get``:
        тот стоит запроса к API на каждое сообщение.
        """
        stmt = (
            sa.select(AgentSession)
            .where(
                AgentSession.thread_id == thread_id,
                AgentSession.status.in_(
                    (
                        SessionStatus.ACTIVE,
                        SessionStatus.WAITING_APPROVAL,
                        SessionStatus.DONE,
                    )
                ),
            )
            .order_by(AgentSession.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def active_by_anchor(self, chat_id: str, msg_id: str) -> AgentSession | None:
        """Живая сессия, чей ответ процитировали.

        Второй путь к тому же разговору: в обсуждении его находит
        ``active_by_thread``, а в личке обсуждений нет — там ответ на
        сообщение единственный способ продолжить начатое.

        Запрос идёт только для сообщений с ответом нашему боту, поэтому
        своего индекса не заслуживает: отбор по ``chat_id`` индекс уже
        имеет, а сессий на чат считанные единицы.
        """
        stmt = (
            sa.select(AgentSession)
            .where(
                AgentSession.chat_id == chat_id,
                AgentSession.anchor_msg_id == msg_id,
                AgentSession.status.in_(
                    (
                        SessionStatus.ACTIVE,
                        SessionStatus.WAITING_APPROVAL,
                        SessionStatus.DONE,
                    )
                ),
            )
            .order_by(AgentSession.created_at.desc())
            .limit(1)
        )
        return await self.session.scalar(stmt)

    async def finish(
        self,
        session_id: uuid.UUID,
        status: SessionStatus,
        *,
        tokens_in: int = 0,
        tokens_out: int = 0,
    ) -> AgentSession | None:
        """Закрыть сессию и досчитать расход токенов.

        Начисление идёт отдельным ``UPDATE`` со сложением на стороне базы:
        продолжения одного диалога уходят в разные фоновые задачи, а
        семафор ограничивает их общее число, но не сериализует одну
        сессию. Чтение-изменение-запись в Python потеряло бы начисление
        соседней задачи — а это деньги.
        """
        if tokens_in or tokens_out:
            await self.session.execute(
                sa.update(AgentSession)
                .where(AgentSession.id == session_id)
                .values(
                    tokens_in=AgentSession.tokens_in + tokens_in,
                    tokens_out=AgentSession.tokens_out + tokens_out,
                )
            )
        row = await self.get_or_none(session_id)
        if row is None:
            return None
        row.status = status
        self.session.add(row)
        # Счётчики поменяла база, а не сессия: перечитываем, иначе
        # вызывающий увидит старые значения.
        await self.session.refresh(row, ["tokens_in", "tokens_out"])
        return row

    async def tokens_since(self, user_id: str, since: datetime.datetime) -> int:
        """Сколько токенов пользователь потратил с указанного момента.

        Суточный бюджет считается по обоим направлениям сразу: платят и
        за вход, и за выход.
        """
        stmt = sa.select(
            sa.func.coalesce(
                sa.func.sum(AgentSession.tokens_in + AgentSession.tokens_out), 0
            )
        ).where(AgentSession.user_id == user_id, AgentSession.created_at >= since)
        return int(await self.session.scalar(stmt) or 0)


class AgentMessageRepository(
    AsyncRepository[AgentMessage, int, CreateAgentMessageSchema, Any]
):
    """AgentMessage Repository."""

    async def history(self, session_id: uuid.UUID) -> list[AgentMessage]:
        """Сообщения диалога в хронологическом порядке."""
        stmt = (
            sa.select(AgentMessage)
            .where(AgentMessage.session_id == session_id)
            .order_by(AgentMessage.created_at.asc(), AgentMessage.id.asc())
        )
        return list((await self.session.scalars(stmt)).all())


class AgentToolCallRepository(
    AsyncRepository[AgentToolCall, uuid.UUID, BaseModel, Any]
):
    """AgentToolCall Repository."""
