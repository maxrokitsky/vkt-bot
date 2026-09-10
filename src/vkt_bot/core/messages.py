"""История сообщений: запись и выключатели.

Сообщения записываются ядром, а не плагином: они нужны не только агенту
(поиск, панель), и плагину нечего дописывать в core-middleware.

Хранить тексты всех чатов — отдельное решение, поэтому у записи два
выключателя, по образцу автоподписки на обсуждения: глобальный
``messages_history`` в ``bot_settings`` и команда ``/history off`` на
отдельный чат.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import structlog

from vkt_bot.core.constants import (
    CHAT_HISTORY_SETTING_PREFIX,
    MESSAGES_HISTORY_SETTING,
)
from vkt_bot.core.repositories.bot_settings import BotSettingsRepository
from vkt_bot.core.repositories.message import MessageRepository
from vkt_bot.db.session import async_session

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkteams_client.types import Bot, User

logger = structlog.get_logger("vkt_bot.messages")

#: Текста у сообщения может не быть вовсе: файлы, стикеры, голосовые.
#: ``NewMessagePayload`` не разбирает ``parts``, поэтому на месте
#: вложения в истории остаётся заглушка.
ATTACHMENT_PLACEHOLDER = "[вложение]"


def chat_history_key(chat_id: str) -> str:
    """Ключ настройки «история в этом чате»."""
    return f"{CHAT_HISTORY_SETTING_PREFIX}{chat_id}"


async def history_enabled(session: AsyncSession, chat_id: str | None = None) -> bool:
    """Разрешена ли запись истории — глобально и в конкретном чате.

    Выключенная запись означает, что ни автоконтекста, ни инструмента
    ``chat_messages`` в этом чате нет; агент об этом сообщает.
    """
    settings = BotSettingsRepository(session)
    if not await settings.get_bool(MESSAGES_HISTORY_SETTING, default=True):
        return False
    if chat_id is None:
        return True
    return await settings.get_bool(chat_history_key(chat_id), default=True)


async def set_chat_history(
    session: AsyncSession, chat_id: str, *, enabled: bool
) -> None:
    """Включить или выключить запись истории в конкретном чате."""
    await BotSettingsRepository(session).set_value(
        chat_history_key(chat_id),
        "true" if enabled else "false",
        description=f"История сообщений чата {chat_id}",
    )


async def record_incoming(
    session: AsyncSession,
    chat_id: str,
    msg_id: str,
    *,
    sender: User | Bot | None = None,
    text: str | None = None,
    ts: datetime.datetime | None = None,
) -> None:
    """Записать входящее сообщение, если запись разрешена.

    Автор пишется идентификатором как есть: строки ``ChatUser`` заводит
    поток событий о составе чата, а не поток сообщений, и автор реплики
    в обсуждении вполне может быть ещё неизвестен.
    """
    if not await history_enabled(session, chat_id):
        return

    await MessageRepository(session).record(
        chat_id,
        msg_id,
        user_id=sender.userId if sender is not None else None,
        text=text if text else ATTACHMENT_PLACEHOLDER,
        ts=ts,
    )


async def record_outgoing(chat_id: str, msg_id: str, text: str) -> None:
    """Записать сообщение, отправленное ботом.

    В поток событий свои сообщения не возвращаются, поэтому без этой
    записи история читается с дырами: вопрос есть, ответа нет.

    Своя сессия и подавленная ошибка: запись истории не повод не
    доставить текст пользователю.
    """
    try:
        async with async_session() as session:
            if not await history_enabled(session, chat_id):
                return
            await MessageRepository(session).record(
                chat_id, msg_id, text=text, is_outgoing=True
            )
            await session.commit()
    except Exception:
        logger.exception("message.record_failed", chat_id=chat_id, msg_id=msg_id)


async def purge_history(session: AsyncSession, *, days: int, max_per_chat: int) -> int:
    """Почистить историю: по сроку хранения и по потолку на чат.

    Эта таблица — самая быстрорастущая в системе: поток сообщений идёт
    постоянно, и без чистки она обгонит журнал событий в разы.
    """
    repository = MessageRepository(session)
    removed = await repository.purge_older_than(days)
    removed += await repository.enforce_chat_limit(max_per_chat)
    if removed:
        await session.commit()
    return removed
