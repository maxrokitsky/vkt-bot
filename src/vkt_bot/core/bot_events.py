"""Действия самого бота как доменные события.

``vkteams_client`` в базу не ходит — иначе пакет перестал бы быть
самостоятельным. Вместо этого у клиента есть ``event_sink``, куда
приложение подставляет функцию отсюда.
"""

from typing import Any

from vkt_bot.core.events import Actor, emit
from vkt_bot.db.session import async_session


async def record_bot_action(event_type: str, fields: dict[str, Any]) -> None:
    """Записать то, что сделал бот.

    Сессия открывается на каждое действие, но соединение SQLAlchemy берёт
    только под настоящий запрос: у типов с ``persist=False``
    (``message.sent``) до базы дело не доходит.
    """
    fields = dict(fields)
    chat_id = fields.pop("chat_id", None)
    async with async_session() as session:
        await emit(
            session,
            event_type,
            actor=Actor.bot(),
            chat_id=chat_id,
            payload={key: value for key, value in fields.items() if value is not None},
        )
        await session.commit()
