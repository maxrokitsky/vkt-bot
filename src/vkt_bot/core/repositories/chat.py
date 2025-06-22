from typing import Any

from pydantic import BaseModel

from vkteams_client.enums import ChatType
from vkt_bot.db.repository import AsyncRepository
from vkt_bot.core.models import Chat


class CreateChatSchema(BaseModel):
    """CreateChatSchema."""

    id: str
    type: ChatType


class ChatRepository(AsyncRepository[Chat, str, CreateChatSchema, Any]):
    """Chat Repository."""
