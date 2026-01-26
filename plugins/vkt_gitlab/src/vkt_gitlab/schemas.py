import datetime
import uuid
from pydantic import BaseModel


class GlWebhookBase(BaseModel):
    """Base GitLab Webhook schema."""

    name: str = ""


class GlWebhookCreate(GlWebhookBase):
    """Create GitLab Webhook schema."""

    secret: str
    chat_id: str


class GlWebhookUpdate(BaseModel):
    """Update GitLab Webhook schema."""

    name: str | None = None


class GlWebhookRead(GlWebhookBase):
    """Read GitLab Webhook schema."""

    id: uuid.UUID
    chat_id: str
    chat_title: str | None = None
    created_by_id: str
    created_by_name: str | None = None
    last_used_at: datetime.datetime | None
    created_at: datetime.datetime
    updated_at: datetime.datetime

    class Config:
        from_attributes = True


class GlWebhookListResponse(BaseModel):
    """List response for webhooks."""

    items: list[GlWebhookRead]
    total: int
    page: int
    size: int
    pages: int
