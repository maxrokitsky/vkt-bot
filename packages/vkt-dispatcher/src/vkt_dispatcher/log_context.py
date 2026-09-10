"""Контекст логирования входящего события.

Всё, что бот делает, он делает из-за какого-то события. Поля отсюда
привязываются к контексту на время обработки, поэтому каждая строка лога —
своя, чужая, из библиотеки — отвечает на вопрос «в рамках чего это».
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from vkteams_client.types import Event


def attribute(obj: Any, name: str) -> Any:  # noqa: ANN401
    """Достать поле у pydantic-модели или у словаря.

    У части событий ``payload`` описан как ``Any`` и приезжает обычным
    словарём (ROADMAP 3.5), поэтому оба варианта равноправны.
    """
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def event_context(event: Event) -> dict[str, Any]:
    """Поля, которыми помечается обработка одного события.

    Поля достаются защитно: у событий разные payload'ы, и отсутствие
    ``chat_id`` не повод ронять обработку.
    """
    payload = attribute(event, "payload")
    # У callbackQuery чат лежит в сообщении, к которому нажали кнопку.
    chat = attribute(payload, "chat") or attribute(
        attribute(payload, "message"), "chat"
    )
    sender = attribute(payload, "sender") or attribute(
        attribute(payload, "message"), "sender"
    )

    context: dict[str, Any] = {
        # Свой идентификатор, а не eventId: он же уедет в строку таблицы
        # events и склеит запись в панели с логами в Grafana.
        "trace_id": uuid.uuid4().hex,
        "event_id": attribute(event, "eventId"),
        "event_type": str(attribute(event, "type") or "") or None,
    }
    if chat_id := attribute(chat, "chatId"):
        context["chat_id"] = chat_id
    if user_id := attribute(sender, "userId"):
        context["user_id"] = user_id
    return context
