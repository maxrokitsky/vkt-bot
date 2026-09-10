"""Схемы журнала событий."""

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict

from vkt_bot.core.models.event import (
    ActorType,
    EventSeverity,
    EventSource,
)


class EventResponse(BaseModel):
    """Событие в ленте."""

    id: int
    ts: datetime.datetime
    type: str
    source: EventSource
    severity: EventSeverity
    actor_type: ActorType
    actor_id: str | None
    chat_id: str | None
    entity_type: str | None
    entity_id: str | None
    summary: str
    payload: dict[str, Any] | None
    trace_id: str | None

    model_config = ConfigDict(from_attributes=True)


class EventFilters(BaseModel):
    """Фильтры ленты событий."""

    #: Точный тип (``role.assigned``) или домен целиком (``role.*``).
    type: str | None = None
    source: EventSource | None = None
    severity: EventSeverity | None = None
    actor_id: str | None = None
    chat_id: str | None = None
    entity_type: str | None = None
    entity_id: str | None = None
    start_date: datetime.datetime | None = None
    end_date: datetime.datetime | None = None
    search_query: str | None = None


class PaginatedEventsResponse(BaseModel):
    """Постраничный ответ ленты."""

    items: list[EventResponse]
    total: int
    page: int
    size: int
    pages: int


class EventTypeResponse(BaseModel):
    """Тип события из реестра — панель строит по нему подписи и фильтры."""

    type: str
    title: str
    source: EventSource
    severity: EventSeverity
    persist: bool
    chat_scoped: bool
