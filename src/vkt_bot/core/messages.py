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
from collections.abc import Sequence
from typing import TYPE_CHECKING, Any

import structlog

from vkteams_client.enums import Parts, PayLoadFileType

from vkt_bot.core.constants import (
    CHAT_HISTORY_SETTING_PREFIX,
    MESSAGES_HISTORY_SETTING,
)
from vkt_bot.core.repositories.bot_settings import BotSettingsRepository
from vkt_bot.core.repositories.message import MessageRepository
from vkt_bot.db.session import async_session
from vkt_bot.utils.message import sender_name

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkteams_client.types import Bot, User

logger = structlog.get_logger("vkt_bot.messages")

#: Совсем ничего: ни текста, ни узнаваемых частей.
ATTACHMENT_PLACEHOLDER = "[вложение]"

#: Как называть вложение в истории. Текста у сообщения может не быть
#: вовсе — файлы, стикеры и голосовые приходят без него, — и без пометки
#: в истории на их месте зияла бы дыра.
PART_LABELS = {
    PayLoadFileType.IMAGE: "изображение",
    PayLoadFileType.VIDEO: "видео",
    PayLoadFileType.AUDIO: "аудио",
}

#: Сколько символов цитаты оставлять от пересланного сообщения. Целиком
#: пересылают и простыни, а история и так самая большая таблица.
QUOTE_LIMIT = 200


def describe_parts(parts: Sequence[Any]) -> list[str]:
    """Человекочитаемые пометки о вложениях сообщения.

    Упоминания сюда не попадают: они и так видны в тексте как ``@[id]``.
    """
    notes: list[str] = []
    for part in parts:
        payload = part.payload
        if part.type == Parts.FILE:
            kind = PART_LABELS.get(payload.type, "файл")
            caption = f": {payload.caption}" if payload.caption else ""
            notes.append(f"[{kind}{caption}]")
        elif part.type == Parts.STICKER:
            notes.append("[стикер]")
        elif part.type == Parts.VOICE:
            notes.append("[голосовое сообщение]")
        elif part.type in (Parts.FORWARD, Parts.REPLY):
            notes.append(_quote(part.type, payload.message))
    return notes


def _quote(kind: str, message: Any) -> str:
    """Пометка о пересланном сообщении или ответе.

    Текст цитаты в истории нужен: без него «о чём тут договорились» по
    пересланной переписке не ответить.
    """
    who = sender_name(message.sender) if message.sender else "неизвестно кто"
    label = "переслано от" if kind == Parts.FORWARD else "в ответ на"
    text = (message.text or "").strip()
    if not text:
        return f"[{label} {who}]"
    return f"[{label} {who}: {text[:QUOTE_LIMIT]}]"


def message_text(text: str | None, parts: Sequence[Any] = ()) -> str:
    """Что записать в историю: текст плюс пометки о вложениях."""
    notes = describe_parts(parts)
    parts_text = " ".join(notes)
    if text and parts_text:
        return f"{text} {parts_text}"
    return text or parts_text or ATTACHMENT_PLACEHOLDER


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
    parts: Sequence[Any] = (),
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
        text=message_text(text, parts),
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
