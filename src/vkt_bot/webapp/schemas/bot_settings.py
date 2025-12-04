from datetime import datetime

from pydantic import BaseModel, ConfigDict


class BotSettingsResponse(BaseModel):
    """Bot settings response schema."""

    key: str
    value: str
    description: str | None = None
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)


class UpdateBotSettingsRequest(BaseModel):
    """Update bot settings request schema."""

    value: str
    description: str | None = None
