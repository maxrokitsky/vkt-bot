from pydantic import BaseModel

from vkt_bot.db.repository import AsyncRepository
from vkt_bot.core.models.bot_settings import BotSettings

TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


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

    async def get_bool(self, key: str, *, default: bool) -> bool:
        """Булева настройка.

        Значения хранятся строками, поэтому распознаём привычные написания.
        Отсутствующая или непонятная запись даёт значение по умолчанию.
        """
        setting = await self.get_by_key(key)
        if setting is None:
            return default
        value = setting.value.strip().lower()
        if value in TRUE_VALUES:
            return True
        if value in FALSE_VALUES:
            return False
        return default

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
