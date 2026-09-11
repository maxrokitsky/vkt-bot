"""Сборка агента и выключатели.

``AgentRunner`` собирается один раз на процесс: системный промпт и список
инструментов не меняются, а стабильный префикс — условие того, что
кэширование на шлюзе вообще работает.
"""

from __future__ import annotations

import functools
from typing import TYPE_CHECKING

import structlog

from vkt_agent import AgentRunner, openai_compatible_model
from vkt_bot.core.constants import AI_ENABLED_SETTING
from vkt_bot.core.repositories.bot_settings import BotSettingsRepository

from .config import get_ai_settings
from .prompts import SYSTEM_PROMPT
from .tools import registry

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger("vkt_ai")


@functools.lru_cache(maxsize=1)
def get_runner() -> AgentRunner:
    """Агент со всеми инструментами."""
    settings = get_ai_settings()
    return AgentRunner(
        openai_compatible_model(
            settings.model,
            api_key=settings.api_key,
            base_url=settings.base_url,
        ),
        registry=registry,
        instructions=SYSTEM_PROMPT,
        max_steps=settings.max_steps,
        timeout=settings.timeout_seconds,
    )


def configured() -> bool:
    """Хватает ли настроек, чтобы вообще запускать агента."""
    settings = get_ai_settings()
    return bool(settings.enabled and settings.api_key and settings.model)


async def agent_enabled(session: AsyncSession) -> bool:
    """Включён ли агент — в ``.env`` и в настройках бота.

    Настройка в базе гасит агента без перезапуска: у шлюза бывают
    внезапные лимиты, и ждать релиза в такой момент неудобно.
    """
    if not configured():
        return False
    return await BotSettingsRepository(session).get_bool(
        AI_ENABLED_SETTING, default=True
    )
