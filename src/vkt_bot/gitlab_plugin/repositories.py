from typing import Any
import uuid
from pydantic import BaseModel

from vkt_bot.bot_framework.repository import AsyncRepository
from vkt_bot.gitlab_plugin.models import GlWebhook


class CreateGlWebhookSchema(BaseModel):
    """CreateGlWebhookSchema."""

    id: str | uuid.UUID | None = None
    name: str = ""
    hashed_secret: str
    chat_id: str
    created_by_id: str


class GlWebhookRepository(
    AsyncRepository[GlWebhook, uuid.UUID, CreateGlWebhookSchema, Any]
):
    """GlWebhook Repository."""
