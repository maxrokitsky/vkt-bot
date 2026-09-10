"""Обсуждения (треды).

У треда собственный ``chatId``, поэтому отдельного канала событий у
обсуждений нет: сообщения из треда приходят обычным ``newMessage`` с
``chatId`` треда — но только тем ботам, которые на тред подписаны.
Автоподписка (``threads/autosubscribe``) и делает бота таким подписчиком.

Отличить тред от обычного чата по виду ``chatId`` нельзя: у треда он
такой же, как у группы (``693938330@chat.agent`` при родителе
``694348323@chat.agent``). Единственная проверка — ответ API:
``threads/subscribers/get`` для обычного чата отказывает с
``Incorrect threadId``.
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


async def get_or_create_thread(
    bot: VKTeams,
    chat_id: str,
    msg_id: str,
) -> str | None:
    """Id обсуждения у сообщения; если обсуждения нет — оно создаётся.

    ``threads/add`` работает как get-or-create: повторный вызов на том же
    сообщении отдаёт тот же ``threadId``. Поэтому хранить соответствие
    «сообщение → тред» у себя не нужно — достаточно помнить ``msg_id``
    сообщения-якоря, а id треда спрашивать у API. Двух тредов на одно
    сообщение не появится даже при гонке.

    Из этого же следует, что «узнать» и «создать» — одна операция: для
    сообщения без обсуждения вызов его создаст.

    ``None`` — либо API отказал (внутри треда вложенное обсуждение
    завести нельзя), либо запрос не дошёл. Ошибка не должна ронять
    обработчик, поэтому наружу она не поднимается.
    """
    try:
        response = await bot.threads_add(chat_id=chat_id, msg_id=msg_id)
    except Exception:
        logger.exception("Failed to get thread for message %s in %s", msg_id, chat_id)
        return None

    if response is None or not response.ok or not response.threadId:
        logger.warning(
            "API refused thread for message %s in chat %s: %s",
            msg_id,
            chat_id,
            getattr(response, "description", None),
        )
        return None

    logger.info(
        "Thread %s for message %s in chat %s.",
        response.threadId,
        msg_id,
        chat_id,
    )
    return response.threadId
