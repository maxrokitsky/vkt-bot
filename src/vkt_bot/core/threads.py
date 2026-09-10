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

from typing import TYPE_CHECKING

import structlog

from vkt_bot.core.constants import THREADS_AUTOSUBSCRIBE_SETTING
from vkt_bot.core.repositories.bot_settings import BotSettingsRepository
from vkt_bot.db.session import async_session

if TYPE_CHECKING:
    from vkteams_client import VKTeams

logger = structlog.get_logger("vkt_bot.threads")

#: Так API отвечает на ``threads/subscribers/get`` для обычного чата.
NOT_A_THREAD = "incorrect threadid"


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
        logger.exception("thread.autosubscribe_failed", chat_id=chat_id)
        return False

    if response is not None and not response.ok:
        logger.warning("thread.autosubscribe_refused", chat_id=chat_id)
        return False

    logger.info(
        "thread.autosubscribed",
        chat_id=chat_id,
        enable=enable,
        with_existing=with_existing,
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
        logger.exception("thread.add_failed", chat_id=chat_id, msg_id=msg_id)
        return None

    if response is None or not response.ok or not response.threadId:
        logger.warning(
            "thread.add_refused",
            chat_id=chat_id,
            msg_id=msg_id,
            reason=getattr(response, "description", None),
        )
        return None

    logger.info(
        "thread.resolved",
        thread_id=response.threadId,
        chat_id=chat_id,
        msg_id=msg_id,
    )
    return response.threadId


async def is_thread(bot: VKTeams, chat_id: str) -> bool:
    """Обсуждение ли этот чат.

    По виду ``chatId`` тред от группы не отличить; единственная проверка
    — ответ API: для обычного чата ``threads/subscribers/get`` отказывает
    с ``Incorrect threadId``. Сам список подписчиков не нужен, поэтому
    просим одну страницу, а не обходим все.

    Этот отказ ожидаем — через проверку идёт каждое сообщение обычного
    чата. Всё остальное — сбой: сеть, права или ошибка в нашем коде.
    Различать их важно, иначе поломка выглядит как обычный чат и молча
    уходит в debug. При сбое отвечаем «обычный чат»: проверка по членству
    строже, и ошибаться лучше в эту сторону.
    """
    try:
        page = await bot.threads_subscribers_get(chat_id, page_size=1)
    except Exception:
        logger.warning("thread.check_failed", chat_id=chat_id, exc_info=True)
        return False

    if page.ok:
        return True

    description = page.description or ""
    if NOT_A_THREAD in description.lower():
        logger.debug("thread.check_not_a_thread", chat_id=chat_id)
    else:
        logger.warning("thread.check_refused", chat_id=chat_id, reason=description)
    return False
