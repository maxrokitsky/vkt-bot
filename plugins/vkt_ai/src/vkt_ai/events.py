"""Типы событий агента.

Регистрируются из ``install()``: колонка ``type`` хранит строку, миграции
для своих типов не нужны. ``EntityType`` — тоже строка, поэтому
``agent_session`` добавляется просто значением.

А вот ``EventSource`` своим значением плагину не расширить, хотя план это
предполагал: колонка объявлена как ``enum_column(EventSource)``, и
SQLAlchemy сверяет значение с перечислением ещё до базы. Поэтому события
агента идут с источником ``system`` — он их и правда порождает сам, без
человека за кнопкой.
"""

from vkt_bot.core.events import EventSpec, register
from vkt_bot.core.models.event import EventSeverity, EventSource

#: Сущность, к которой относятся события агента.
ENTITY_AGENT_SESSION = "agent_session"

SESSION_STARTED = "agent.session_started"
TOOL_CALLED = "agent.tool_called"
TOOL_DENIED = "agent.tool_denied"
ANSWERED = "agent.answered"
LIMIT_EXCEEDED = "agent.limit_exceeded"
FAILED = "agent.failed"

SPECS = (
    EventSpec(
        type=SESSION_STARTED,
        title="Вопрос агенту",
        template="{actor} спросил агента: {question}",
        source=EventSource.COMMAND,
        chat_scoped=True,
    ),
    EventSpec(
        type=TOOL_CALLED,
        title="Агент вызвал инструмент",
        template="Агент вызвал инструменты: {tools}",
        source=EventSource.SYSTEM,
        chat_scoped=True,
    ),
    EventSpec(
        type=TOOL_DENIED,
        title="Действие агента отклонено",
        template="{actor} отклонил вызов {tool}",
        source=EventSource.COMMAND,
        chat_scoped=True,
    ),
    EventSpec(
        type=ANSWERED,
        title="Агент ответил",
        template="Агент ответил в чате {chat_id}",
        source=EventSource.SYSTEM,
        # Поток ответов раздул бы таблицу так же, как поток сообщений.
        persist=False,
        chat_scoped=True,
    ),
    EventSpec(
        type=LIMIT_EXCEEDED,
        title="Лимит агента исчерпан",
        template="{actor}: лимит агента исчерпан ({reason})",
        source=EventSource.SYSTEM,
        severity=EventSeverity.WARNING,
        chat_scoped=True,
    ),
    EventSpec(
        type=FAILED,
        title="Агент не справился",
        template="Сессия агента сорвалась: {reason}",
        source=EventSource.SYSTEM,
        severity=EventSeverity.ERROR,
        chat_scoped=True,
    ),
)


def install_events() -> None:
    """Зарегистрировать типы событий плагина."""
    register(*SPECS)
