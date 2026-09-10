"""Фильтры для журнала событий."""

import datetime
from typing import Any

import sqlalchemy as sa

from vkt_bot.core.models.chat import ChatMembership
from vkt_bot.core.models.event import EventRecord, EventSeverity, EventSource
from vkt_bot.db.query import Query

type Statement = sa.Select[Any]


class EventQuery(Query): ...


class FilterByType(EventQuery):
    """Фильтр по типу.

    ``role.*`` отбирает весь домен: в панели фильтруют скорее по домену,
    чем по конкретному действию.
    """

    type: str

    def apply(self, statement: Statement) -> Statement:
        if self.type.endswith(".*"):
            return statement.where(EventRecord.type.startswith(self.type[:-1]))
        return statement.where(EventRecord.type == self.type)


class FilterByTypes(EventQuery):
    """Фильтр по списку типов."""

    types: list[str]

    def apply(self, statement: Statement) -> Statement:
        return statement.where(EventRecord.type.in_(self.types))


class FilterBySource(EventQuery):
    """Фильтр по источнику действия."""

    source: EventSource

    def apply(self, statement: Statement) -> Statement:
        return statement.where(EventRecord.source == self.source)


class FilterBySeverity(EventQuery):
    """Фильтр по значимости."""

    severity: EventSeverity

    def apply(self, statement: Statement) -> Statement:
        return statement.where(EventRecord.severity == self.severity)


class FilterByActorId(EventQuery):
    """Фильтр по актору."""

    actor_id: str

    def apply(self, statement: Statement) -> Statement:
        return statement.where(EventRecord.actor_id == self.actor_id)


class FilterByChatId(EventQuery):
    """Фильтр по чату."""

    chat_id: str

    def apply(self, statement: Statement) -> Statement:
        return statement.where(EventRecord.chat_id == self.chat_id)


class FilterByEntity(EventQuery):
    """Фильтр по сущности."""

    entity_type: str | None = None
    entity_id: str | None = None

    def apply(self, statement: Statement) -> Statement:
        if self.entity_type:
            statement = statement.where(EventRecord.entity_type == self.entity_type)
        if self.entity_id:
            statement = statement.where(EventRecord.entity_id == self.entity_id)
        return statement


class FilterByDateRange(EventQuery):
    """Фильтр по диапазону дат."""

    start_date: datetime.datetime | None = None
    end_date: datetime.datetime | None = None

    def apply(self, statement: Statement) -> Statement:
        if self.start_date:
            statement = statement.where(EventRecord.ts >= self.start_date)
        if self.end_date:
            statement = statement.where(EventRecord.ts <= self.end_date)
        return statement


class SearchBySummary(EventQuery):
    """Поиск по человекочитаемой строке."""

    search_query: str

    def apply(self, statement: Statement) -> Statement:
        return statement.where(EventRecord.summary.ilike(f"%{self.search_query}%"))


class VisibleToUser(EventQuery):
    """События чатов, в которых состоит пользователь.

    Фильтр идёт подзапросом, а не отбором в Python: иначе ``total`` в
    пагинации считал бы отброшенные строки. События без чата (создание
    роли, вход в панель) обычному пользователю не показываются — у них
    нет чата, по которому можно решить, что он имеет к ним отношение.
    """

    user_id: str

    def apply(self, statement: Statement) -> Statement:
        chats = sa.select(ChatMembership.chat_id).where(
            ChatMembership.user_id == self.user_id
        )
        return statement.where(EventRecord.chat_id.in_(chats))


class OrderByTs(EventQuery):
    """Сортировка по времени."""

    descending: bool = True

    def apply(self, statement: Statement) -> Statement:
        column = EventRecord.ts.desc() if self.descending else EventRecord.ts.asc()
        # Вторым ключом id: у событий одной транзакции время совпадает
        # до микросекунды, и без него порядок между страницами плывёт.
        second = EventRecord.id.desc() if self.descending else EventRecord.id.asc()
        return statement.order_by(column, second)
