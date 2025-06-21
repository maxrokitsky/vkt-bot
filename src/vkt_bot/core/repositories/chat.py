from typing import Any

from pydantic import BaseModel

from vkt_bot.bot_framework.bot.enums import ChatType
from vkt_bot.bot_framework.repository import AsyncRepository
from vkt_bot.core.models import Chat


class CreateChatSchema(BaseModel):
    """CreateChatSchema."""

    id: str
    type: ChatType


class ChatRepository(AsyncRepository[Chat, str, CreateChatSchema, Any]):
    """Chat Repository."""
