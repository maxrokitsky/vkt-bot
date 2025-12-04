from typing import Any

from pydantic import BaseModel

from vkt_bot.core.models.log_entry import ActionType, ActorType, EntityType, LogEntry
from vkt_bot.db.repository import AsyncRepository


class CreateLogEntrySchema(BaseModel):
    """Схема создания записи лога."""

    actor_type: ActorType
    actor_id: str | None
    action_type: ActionType
    entity_type: EntityType
    entity_id: str
    description: str | None = None
    details: dict | None = None
    web_user_username: str | None = None
    bot_user_id: str | None = None


class LogEntryRepository(
    AsyncRepository[LogEntry, int, CreateLogEntrySchema, Any]
):
    """Репозиторий для работы с логами аудита."""

    pass
