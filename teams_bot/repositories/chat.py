from typing import Any

from pydantic import BaseModel

from bot_framework.bot.enums import ChatType
from bot_framework.repository import AsyncRepository
from teams_bot.models import Chat


class CreateChatSchema(BaseModel):
    """CreateChatSchema."""

    id: str
    type: ChatType


class ChatRepository(AsyncRepository[Chat, str, CreateChatSchema, Any]):
    """Chat Repository."""
