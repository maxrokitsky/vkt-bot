"""Автоконтекст: последние сообщения чата в промпт.

Без него агент отвечает на реплику вне разговора и переспрашивает
очевидное. В обсуждении выборка сходится сама: у треда свой ``chatId``.

Потолок двойной — и по числу сообщений, и по объёму: один болтливый чат
иначе съедает весь бюджет токенов.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from vkt_bot.core.messages import history_enabled
from vkt_bot.core.repositories.message import MessageRepository
from vkt_bot.core.repositories.user import ChatUserRepository

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

#: Длинное сообщение обрезается до этого, а не выбрасывается целиком:
#: начало реплики обычно и несёт смысл.
MAX_MESSAGE_CHARS = 500
TRUNCATED = "…"


async def build_context(
    session: AsyncSession,
    chat_id: str,
    *,
    limit: int,
    max_chars: int,
    skip_msg_id: str | None = None,
) -> str | None:
    """История чата для промпта или ``None``, если её нет.

    ``skip_msg_id`` убирает из контекста сам вопрос: он и так уедет в
    промпт отдельной строкой, и дублировать его незачем.
    """
    if not await history_enabled(session, chat_id):
        return None

    rows = await MessageRepository(session).recent(chat_id, limit=limit)
    rows = [row for row in rows if row.msg_id != skip_msg_id]
    if not rows:
        return None

    users = ChatUserRepository(session)
    names: dict[str, str] = {}
    for row in rows:
        if row.user_id and row.user_id not in names:
            user = await users.get_or_none(row.user_id)
            names[row.user_id] = user.display_name if user else row.user_id

    # Собираем с конца: если объём кончится, обрезать надо старое, а не
    # последнюю реплику, ради которой всё и затевалось.
    lines: list[str] = []
    total = 0
    for row in reversed(rows):
        who = "бот" if row.is_outgoing else names.get(row.user_id or "", "участник")
        text = row.text or ""
        if len(text) > MAX_MESSAGE_CHARS:
            text = text[:MAX_MESSAGE_CHARS] + TRUNCATED
        line = f"{who}: {text}"
        if total + len(line) > max_chars:
            break
        lines.append(line)
        total += len(line)

    if not lines:
        return None
    lines.reverse()
    return "\n".join(lines)
