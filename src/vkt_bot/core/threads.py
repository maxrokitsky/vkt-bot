"""Обсуждения (треды).

У треда собственный ``chatId``, поэтому отдельного канала событий у
обсуждений нет: сообщения из треда приходят обычным ``newMessage`` с
``chatId`` треда — но только тем ботам, которые на тред подписаны.
Автоподписка (``threads/autosubscribe``) и делает бота таким подписчиком.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from vkt_bot.core.constants import THREADS_AUTOSUBSCRIBE_SETTING
from vkt_bot.core.repositories.bot_settings import BotSettingsRepository
from vkt_bot.db.session import async_session

if TYPE_CHECKING:
    from vkteams_client import VKTeams

logger = logging.getLogger("vkt_bot")


async def autosubscribe_enabled() -> bool:
    """Разрешена ли автоподписка на обсуждения настройками бота."""
    async with async_session() as session:
        return await BotSettingsRepository(session).get_bool(
            THREADS_AUTOSUBSCRIBE_SETTING, default=True
        )


async def set_thread_autosubscribe(
    bot: VKTeams,
    chat_id: str,
    *,
    enable: bool = True,
    with_existing: bool = True,
) -> bool:
    """Включить или выключить автоподписку бота на обсуждения чата.

    ``with_existing`` подписывает и на уже существующие треды — бота
    добавляют в живой чат, где обсуждения обычно уже есть.

    Ошибка API не должна ронять обработчик, поэтому результат возвращается
    флагом, а не исключением.
    """
    try:
        response = await bot.threads_autosubscribe(
            chat_id=chat_id,
            enable=enable,
            with_existing=with_existing,
        )
    except Exception:
        logger.exception("Failed to set thread autosubscribe for chat %s", chat_id)
        return False

    if response is not None and not response.ok:
        logger.warning("API refused thread autosubscribe for chat %s", chat_id)
        return False

    logger.info(
        "Thread autosubscribe for chat %s: enable=%s, with existing=%s.",
        chat_id,
        enable,
        with_existing,
    )
    return True
