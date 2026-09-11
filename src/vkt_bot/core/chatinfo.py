"""Обогащение чатов и участников через ``chats/getInfo``.

Метод закрывает главную дырку в учёте состава: ``chats/getMembers``
отдаёт голые идентификаторы, а событий по людям, вступившим до бота, уже
не будет — и участник оставался безымянным навсегда. ``getInfo`` по
``userId`` работает для любого участника группы, даже без личной
переписки с ботом, и приносит имя, ник, ``about`` и ссылку на аватар.

Стоит это ровно одного запроса на сущность, поэтому здесь же живут кэш и
лимиты: TTL по ``info_updated_at``, потолок на размер захода и семафор на
одновременные запросы. Сеть при этом идёт **вне** сессии БД: держать
соединение из пула на время пятидесяти HTTP-запросов нельзя.
"""

from __future__ import annotations

import asyncio
import datetime
from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING

import structlog

from vkteams_client.types import (
    ChannelChatInfo,
    GetChatInfoResponse,
    GroupChatInfo,
    PrivateChatInfo,
)
from vkt_bot.core.repositories.chat import ChatRepository
from vkt_bot.core.repositories.user import ChatUserRepository
from vkt_bot.db.session import async_session
from vkt_bot.utils.datetime import to_naive_utc, utcnow

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkteams_client import VKTeams

logger = structlog.get_logger("vkt_bot.chatinfo")

#: Сколько живёт обогащение. Имя, аватар и описание меняются редко, а
#: событий об этом API не присылает: ``changedChatInfo`` несёт только
#: название. Поэтому обновляемся по сроку, а не по поводу.
INFO_TTL = datetime.timedelta(days=7)

#: Сколько сущностей обогащаем за один заход. Ростер бывает и на 50+
#: человек; остальные подтянутся со своего первого сообщения или на
#: следующем заходе.
MAX_BATCH = 50

#: Одновременных запросов к API. Лимитов в спеке нет, поэтому берём
#: заведомо вежливое число: пятьдесят запросов по четыре в ряд — это
#: около секунды, а не пачка из пятидесяти разом.
CONCURRENCY = 4

#: Так API отвечает на ``chats/getInfo`` в обсуждении. Отказ ожидаем:
#: тред от обычной группы по ``chatId`` не отличить.
NOT_A_CHAT = "bad request"


def is_stale(moment: datetime.datetime | None) -> bool:
    """Пора ли спрашивать API. ``None`` — не спрашивали ни разу."""
    if moment is None:
        return True
    return to_naive_utc(moment) < utcnow() - INFO_TTL


async def fetch(bot: VKTeams, chat_id: str) -> GetChatInfoResponse | None:
    """Ответ ``chats/getInfo``; ``None`` — запрос не дошёл.

    Отказ API возвращается как есть: его надо запомнить, иначе спросим
    снова через минуту. А сетевую ошибку — наоборот, не запоминать: она
    про нас, а не про чат. Ровно поэтому ``None`` и ``ok: false`` здесь
    не сливаются в одно.
    """
    try:
        info = await bot.get_chat_info(chat_id=chat_id)
    except Exception:
        logger.warning("chatinfo.fetch_failed", chat_id=chat_id, exc_info=True)
        return None

    if info is None:
        # Подменённый клиент отдал заглушку — ответа нет.
        return None

    if not info.ok:
        reason = info.description or ""
        if NOT_A_CHAT in reason.lower():
            # Скорее всего обсуждение. Ожидаемо и не новость.
            logger.debug("chatinfo.not_a_chat", chat_id=chat_id)
        else:
            logger.warning("chatinfo.refused", chat_id=chat_id, reason=reason)
    return info


async def gather_infos(
    bot: VKTeams, chat_ids: Sequence[str]
) -> dict[str, GetChatInfoResponse | None]:
    """Запросы пачкой, но не залпом."""
    semaphore = asyncio.Semaphore(CONCURRENCY)

    async def one(chat_id: str) -> tuple[str, GetChatInfoResponse | None]:
        async with semaphore:
            return chat_id, await fetch(bot, chat_id)

    # ``fetch`` исключений не выпускает, поэтому ``return_exceptions``
    # не нужен: ни одна ветка не уронит остальные сорок девять.
    return dict(await asyncio.gather(*(one(chat_id) for chat_id in chat_ids)))


async def enrich_chat(bot: VKTeams, chat_id: str, *, force: bool = False) -> bool:
    """Дополнить чат: название, описание, правила, ссылка-приглашение.

    Возвращает, спрашивали ли API. ``force`` обходит TTL — он нужен на
    ``changedChatInfo``: событие несёт только название, а поменяться
    могли и описание с правилами.

    Личный чат — особый случай: там ``chat_id`` совпадает с ``userId``, и
    ответ приходит ``private``. Тогда обогащаем профиль участника, а
    ``chats.title`` не трогаем: у личного чата его нет и быть не должно.
    """
    async with async_session() as session:
        chat = await ChatRepository(session).get_or_none(chat_id)
        if chat is None:
            return False
        if not force and not is_stale(chat.info_updated_at):
            return False

    info = await fetch(bot, chat_id)
    if info is None:
        return True

    async with async_session() as session:
        chats = ChatRepository(session)
        chat = await chats.get_or_none(chat_id)
        if chat is None:
            return True
        if isinstance(info, GroupChatInfo | ChannelChatInfo):
            chats.apply_info(chat, info)
        else:
            # Личный чат или отказ: полей чата в ответе нет, но метку
            # ставим — иначе спросим снова на следующем сообщении.
            chats.touch_info(chat)
            if isinstance(info, PrivateChatInfo):
                await _apply_private(session, chat_id, info)
        await session.commit()
    return True


async def enrich_members(bot: VKTeams, user_ids: Iterable[str]) -> int:
    """Дополнить профили участников. Возвращает число запросов к API.

    Новых строк не создаёт: кто попадает в базу — решают хендлеры.
    """
    async with async_session() as session:
        users = await ChatUserRepository(session).list_by_ids(user_ids)
        stale = [user.id for user in users if is_stale(user.info_updated_at)]

    targets = stale[:MAX_BATCH]
    if not targets:
        return 0

    infos = await gather_infos(bot, targets)

    async with async_session() as session:
        for user_id, info in infos.items():
            if info is None:
                # Запрос не дошёл — метку не ставим, повторим позже.
                continue
            await _apply_private(session, user_id, info)
        await session.commit()
    return len(targets)


async def refresh_from_message(bot: VKTeams, chat_id: str, user_id: str) -> None:
    """Держать чат и отправителя обогащёнными.

    Зовётся на каждое сообщение, но к API ходит только по TTL. В личке
    чат и отправитель — одна и та же сущность, поэтому запрос там один.
    """
    if chat_id == user_id:
        await enrich_chat(bot, chat_id)
        return
    await enrich_chat(bot, chat_id)
    await enrich_members(bot, [user_id])


async def _apply_private(
    session: AsyncSession, user_id: str, info: GetChatInfoResponse
) -> None:
    """Применить ответ к профилю участника, если он нам известен."""
    users = ChatUserRepository(session)
    user = await users.get_or_none(user_id)
    if user is None:
        return
    if isinstance(info, PrivateChatInfo):
        users.apply_chat_info(user, info)
    else:
        # Отказ тоже запоминаем: иначе будем спрашивать без конца.
        users.touch_info(user)
