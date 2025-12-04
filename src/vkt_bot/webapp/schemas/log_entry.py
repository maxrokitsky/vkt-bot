import datetime

from pydantic import BaseModel, ConfigDict

from vkt_bot.core.models.log_entry import ActionType, ActorType, EntityType


class LogEntryResponse(BaseModel):
    """Ответ с записью лога."""

    id: int
    timestamp: datetime.datetime
    actor_type: ActorType
    actor_id: str | None
    action_type: ActionType
    entity_type: EntityType
    entity_id: str
    description: str | None
    details: dict | None
    web_user_username: str | None
    bot_user_id: str | None

    model_config = ConfigDict(from_attributes=True)


class LogEntryFilters(BaseModel):
    """Фильтры для поиска логов."""

    actor_type: ActorType | None = None
    actor_id: str | None = None
    action_type: ActionType | None = None
    entity_type: EntityType | None = None
    entity_id: str | None = None
    start_date: datetime.datetime | None = None
    end_date: datetime.datetime | None = None
    search_query: str | None = None


class PaginatedLogEntriesResponse(BaseModel):
    """Постраничный ответ с логами."""

    items: list[LogEntryResponse]
    total: int
    page: int
    size: int
    pages: int
