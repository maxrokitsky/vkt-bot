from typing import Any
import uuid
from pydantic import BaseModel

from bot_framework.repository import AsyncRepository
from gitlab_plugin.models import GlWebhook


class CreateGlWebhookSchema(BaseModel):
    """CreateGlWebhookSchema."""

    id: str | uuid.UUID | None = None
    hashed_secret: str
    chat_id: str
    created_by_id: str


class GlWebhookRepository(
    AsyncRepository[GlWebhook, uuid.UUID, CreateGlWebhookSchema, Any]
):
    """GlWebhook Repository."""
