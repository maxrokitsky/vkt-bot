from typing import Any
import uuid
from pydantic import BaseModel

from vkt_bot.db.repository import AsyncRepository
from vkt_gitlab.models import GlWebhook


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
