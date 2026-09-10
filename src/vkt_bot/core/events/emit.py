"""Испускание события: строка в базе и строка в логе одним вызовом.

Запись идёт в ту же сессию, что и само действие, и без ``commit`` —
событие «роль назначена» не должно пережить откат назначения. Обратная
сторона: упавшая вставка утащила бы за собой действие, поэтому запись
сделана неспособной упасть — шаблон рендерится безопасно, ``payload``
приводится к JSON-совместимому виду, длинные строки обрезаются.
"""

from __future__ import annotations

import datetime
from typing import TYPE_CHECKING, Any

import structlog

from vkt_bot.core.events.registry import EventSpec, fallback_spec, get
from vkt_bot.core.models.event import (
    ActorType,
    EventRecord,
    EventSeverity,
    EventSource,
)

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

logger = structlog.get_logger("vkt_bot.events")

#: Длина ``summary``: строка показывается в ленте, а не читается целиком.
MAX_SUMMARY = 500
#: Предел вложенности ``payload`` при приведении к JSON.
MAX_PAYLOAD_DEPTH = 5


class Actor:
    """Кто совершил действие.

    Собирается фабриками, чтобы на месте вызова не пересобирать три поля
    руками — их легко перепутать местами.
    """

    __slots__ = ("display", "id", "type")

    def __init__(
        self, actor_type: ActorType, actor_id: str | None, display: str
    ) -> None:
        self.type = actor_type
        self.id = actor_id
        self.display = display

    def __repr__(self) -> str:
        return f"<Actor {self.type} {self.id}>"

    @classmethod
    def from_user(cls, user: Any) -> Actor:  # noqa: ANN401
        """Пользователь панели или чата (``ChatUser``)."""
        return cls(ActorType.USER, user.id, user.display_name)

    @classmethod
    def from_event(cls, event: Any) -> Actor:  # noqa: ANN401
        """Отправитель события VK Teams.

        Имя берётся из события: в базе оно может быть ещё неизвестно.
        """
        sender = getattr(event.payload, "sender", None)
        if sender is None:
            return cls.system()
        name = " ".join(
            part
            for part in (
                getattr(sender, "firstName", None),
                getattr(sender, "lastName", None),
            )
            if part
        )
        return cls(ActorType.USER, sender.userId, name or sender.userId)

    @classmethod
    def bot(cls) -> Actor:
        """Сам бот."""
        return cls(ActorType.BOT, None, "Бот")

    @classmethod
    def system(cls) -> Actor:
        """Действие без инициатора."""
        return cls(ActorType.SYSTEM, None, "Система")

    @classmethod
    def external(cls, name: str) -> Actor:
        """Внешняя система: вебхук, GitLab и подобное."""
        return cls(ActorType.EXTERNAL, name, name)


class SafeFormatMap(dict):
    """Подстановка, которая не падает на недостающем поле.

    Забытый ключ в шаблоне — повод показать прочерк, а не уронить
    действие, ради которого событие пишется.
    """

    def __missing__(self, key: str) -> str:
        return "—"


def jsonable(value: Any, depth: int = 0) -> Any:  # noqa: ANN401
    """Привести значение к тому, что переживёт сериализацию в JSON."""
    if depth >= MAX_PAYLOAD_DEPTH:
        return str(value)
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, dict):
        return {str(key): jsonable(val, depth + 1) for key, val in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [jsonable(item, depth + 1) for item in value]
    if isinstance(value, (datetime.datetime, datetime.date)):
        return value.isoformat()
    return str(value)


def render(spec: EventSpec, fields: dict[str, Any]) -> str:
    """Человекочитаемая строка события.

    Рендерится при записи: в базе лежит готовый текст, поэтому старые
    события переживают переименование и удаление типа.
    """
    try:
        summary = spec.template.format_map(SafeFormatMap(fields))
    except (ValueError, IndexError):
        # Кривой шаблон (например, незакрытая скобка) — не повод терять
        # событие целиком.
        logger.warning("events.bad_template", type=spec.type)
        summary = spec.title
    return summary[:MAX_SUMMARY]


async def emit(
    session: AsyncSession,
    event_type: str,
    *,
    actor: Actor | None = None,
    chat_id: str | None = None,
    entity: tuple[str, str] | None = None,
    payload: dict[str, Any] | None = None,
    source: EventSource | None = None,
    severity: EventSeverity | None = None,
    summary: str | None = None,
) -> EventRecord | None:
    """Записать событие и залогировать его.

    Возвращает строку журнала или ``None``, если тип помечен
    ``persist=False`` — такие события живут только в логах.

    Строка добавляется в сессию без ``commit``: фиксирует её вызывающий
    вместе со своим действием.
    """
    spec = get(event_type) or fallback_spec(str(event_type))
    actor = actor or Actor.system()
    entity_type, entity_id = entity if entity else (None, None)
    payload = {key: jsonable(value) for key, value in (payload or {}).items()}

    fields: dict[str, Any] = {
        **payload,
        "actor": actor.display,
        "actor_id": actor.id,
        "chat_id": chat_id,
        "entity_id": entity_id,
        "entity_type": entity_type,
    }
    text = summary[:MAX_SUMMARY] if summary else render(spec, fields)
    severity = severity or spec.severity
    source = source or spec.source
    trace_id = structlog.contextvars.get_contextvars().get("trace_id")

    getattr(logger, severity.value, logger.info)(
        str(event_type),
        chat_id=chat_id,
        actor_id=actor.id,
        entity_type=entity_type,
        entity_id=entity_id,
        source=source.value,
        **payload,
    )

    if not spec.persist:
        return None

    record = EventRecord(
        type=str(event_type),
        source=source,
        severity=severity,
        actor_type=actor.type,
        actor_id=actor.id,
        chat_id=chat_id,
        entity_type=entity_type,
        entity_id=str(entity_id) if entity_id is not None else None,
        summary=text,
        payload=payload or None,
        trace_id=trace_id,
    )
    session.add(record)
    return record
