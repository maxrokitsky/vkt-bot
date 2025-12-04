import datetime
from typing import Any

import sqlalchemy as sa

from vkt_bot.core.models.log_entry import ActionType, ActorType, EntityType, LogEntry
from vkt_bot.db.query import Query

type Statement = sa.Select[Any]


class LogEntryQuery(Query): ...


class FilterByActorType(LogEntryQuery):
    """Фильтр по типу актора."""

    actor_type: ActorType

    def apply(self, statement: Statement) -> Statement:
        return statement.where(LogEntry.actor_type == self.actor_type)


class FilterByActorId(LogEntryQuery):
    """Фильтр по ID актора."""

    actor_id: str

    def apply(self, statement: Statement) -> Statement:
        return statement.where(LogEntry.actor_id == self.actor_id)


class FilterByActionType(LogEntryQuery):
    """Фильтр по типу действия."""

    action_type: ActionType

    def apply(self, statement: Statement) -> Statement:
        return statement.where(LogEntry.action_type == self.action_type)


class FilterByEntityType(LogEntryQuery):
    """Фильтр по типу сущности."""

    entity_type: EntityType

    def apply(self, statement: Statement) -> Statement:
        return statement.where(LogEntry.entity_type == self.entity_type)


class FilterByEntityId(LogEntryQuery):
    """Фильтр по ID сущности."""

    entity_id: str

    def apply(self, statement: Statement) -> Statement:
        return statement.where(LogEntry.entity_id == self.entity_id)


class FilterByDateRange(LogEntryQuery):
    """Фильтр по диапазону дат."""

    start_date: datetime.datetime | None = None
    end_date: datetime.datetime | None = None

    def apply(self, statement: Statement) -> Statement:
        if self.start_date:
            statement = statement.where(LogEntry.timestamp >= self.start_date)
        if self.end_date:
            statement = statement.where(LogEntry.timestamp <= self.end_date)
        return statement


class SearchByDescription(LogEntryQuery):
    """Поиск по описанию."""

    search_query: str

    def apply(self, statement: Statement) -> Statement:
        search_pattern = f"%{self.search_query}%"
        return statement.where(LogEntry.description.ilike(search_pattern))


class OrderByTimestamp(LogEntryQuery):
    """Сортировка по времени."""

    descending: bool = True

    def apply(self, statement: Statement) -> Statement:
        if self.descending:
            return statement.order_by(LogEntry.timestamp.desc())
        return statement.order_by(LogEntry.timestamp.asc())
