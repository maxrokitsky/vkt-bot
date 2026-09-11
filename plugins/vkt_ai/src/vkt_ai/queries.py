"""Фильтры для списка сессий агента."""

from __future__ import annotations

import datetime
from typing import Any

import sqlalchemy as sa

from vkt_bot.db.query import Query

from .models import AgentSession, SessionStatus

type Statement = sa.Select[Any]


class AgentSessionQuery(Query): ...


class FilterByUser(AgentSessionQuery):
    """Сессии одного участника."""

    user_id: str

    def apply(self, statement: Statement) -> Statement:
        return statement.where(AgentSession.user_id == self.user_id)


class FilterByChat(AgentSessionQuery):
    """Сессии одного чата или обсуждения."""

    chat_id: str

    def apply(self, statement: Statement) -> Statement:
        return statement.where(AgentSession.chat_id == self.chat_id)


class FilterByStatus(AgentSessionQuery):
    """Фильтр по состоянию сессии."""

    status: SessionStatus

    def apply(self, statement: Statement) -> Statement:
        return statement.where(AgentSession.status == self.status)


class FilterByDateRange(AgentSessionQuery):
    """Фильтр по времени начала диалога."""

    start_date: datetime.datetime | None = None
    end_date: datetime.datetime | None = None

    def apply(self, statement: Statement) -> Statement:
        if self.start_date:
            statement = statement.where(AgentSession.created_at >= self.start_date)
        if self.end_date:
            statement = statement.where(AgentSession.created_at <= self.end_date)
        return statement


class OrderByCreated(AgentSessionQuery):
    """Сортировка по времени начала."""

    descending: bool = True

    def apply(self, statement: Statement) -> Statement:
        column = (
            AgentSession.created_at.desc()
            if self.descending
            else AgentSession.created_at.asc()
        )
        # Вторым ключом id: у сессий одной секунды время совпадает, и без
        # него порядок между страницами плывёт — как в ленте событий.
        second = AgentSession.id.desc() if self.descending else AgentSession.id.asc()
        return statement.order_by(column, second)
