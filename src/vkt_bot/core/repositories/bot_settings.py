from pydantic import BaseModel

from vkt_bot.db.repository import AsyncRepository
from vkt_bot.core.models.bot_settings import BotSettings


class CreateBotSettingsSchema(BaseModel):
    """CreateBotSettingsSchema."""

    key: str
    value: str
    description: str | None = None


class UpdateBotSettingsSchema(BaseModel):
    """UpdateBotSettingsSchema."""

    value: str
    description: str | None = None


class BotSettingsRepository(
    AsyncRepository[BotSettings, str, CreateBotSettingsSchema, UpdateBotSettingsSchema]
):
    """Bot Settings Repository."""

    async def get_by_key(self, key: str) -> BotSettings | None:
        """Получить настройку по ключу."""
        return await self.get_or_none(key)

    async def set_value(
        self, key: str, value: str, description: str | None = None
    ) -> BotSettings:
        """Установить или обновить значение настройки."""
        existing = await self.get_by_key(key)
        if existing:
            return await self.update(
                key, UpdateBotSettingsSchema(value=value, description=description)
            )
        return await self.create(
            CreateBotSettingsSchema(key=key, value=value, description=description)
        )
