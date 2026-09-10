"""Реестр типов событий.

Тип события — стабильный идентификатор ``<домен>.<действие>``. У каждого
есть спецификация: как называется в панели, как пересказывается человеку,
откуда обычно приходит, писать ли его в базу и показывать ли на странице
чата.

Плагины добавляют свои типы вызовом ``register`` из ``install()`` —
менять перечисления в ядре и накатывать миграции для этого не нужно,
колонка ``type`` хранит обычную строку.
"""

from __future__ import annotations

import dataclasses
import enum

import structlog

from vkt_bot.core.models.event import EventSeverity, EventSource

logger = structlog.get_logger("vkt_bot.events")


class EventType(enum.StrEnum):
    """Типы событий ядра.

    Плагины пользуются обычными строками — реестр принимает и то, и
    другое.
    """

    BOT_STARTED = "bot.started"
    BOT_POLLING_FAILED = "bot.polling_failed"

    MESSAGE_SENT = "message.sent"
    MESSAGE_SEND_FAILED = "message.send_failed"

    CHAT_REGISTERED = "chat.registered"
    CHAT_BOT_ADDED = "chat.bot_added"
    CHAT_BOT_REMOVED = "chat.bot_removed"
    CHAT_MEMBER_JOINED = "chat.member_joined"
    CHAT_MEMBER_LEFT = "chat.member_left"
    CHAT_INFO_CHANGED = "chat.info_changed"

    THREAD_AUTOSUBSCRIBE_CHANGED = "thread.autosubscribe_changed"

    ROLE_CREATED = "role.created"
    ROLE_UPDATED = "role.updated"
    ROLE_DELETED = "role.deleted"
    ROLE_ASSIGNED = "role.assigned"
    ROLE_UNASSIGNED = "role.unassigned"
    ROLE_MENTIONED = "role.mentioned"

    WEBHOOK_CREATED = "webhook.created"
    WEBHOOK_UPDATED = "webhook.updated"
    WEBHOOK_DELETED = "webhook.deleted"
    WEBHOOK_KEY_REGENERATED = "webhook.key_regenerated"
    WEBHOOK_CALLED = "webhook.called"
    WEBHOOK_FAILED = "webhook.failed"

    AUTH_LOGIN_REQUESTED = "auth.login_requested"
    AUTH_LOGIN_SUCCEEDED = "auth.login_succeeded"
    AUTH_LOGIN_FAILED = "auth.login_failed"
    AUTH_SUPERUSER_GRANTED = "auth.superuser_granted"

    CHAT_USER_UPDATED = "chat_user.updated"
    SETTINGS_CHANGED = "settings.changed"


@dataclasses.dataclass(frozen=True, slots=True)
class EventSpec:
    """Описание типа события."""

    type: str
    #: Подпись в панели: «Роль назначена».
    title: str
    #: Шаблон человекочитаемой строки. Подставляются поля ``payload``
    #: плюс ``actor``, ``actor_id``, ``chat_id``, ``entity_id``.
    #: Недостающее поле не ломает рендер — вместо него будет «—».
    template: str
    #: Источник по умолчанию; на месте вызова его можно переопределить
    #: (роль назначают и из панели, и командой).
    source: EventSource
    severity: EventSeverity = EventSeverity.INFO
    #: Писать ли в базу. ``False`` — событие видно только в логах: так
    #: живут потоковые вещи вроде каждого входящего события API.
    persist: bool = True
    #: Показывать ли в ленте на странице чата.
    chat_scoped: bool = False


_REGISTRY: dict[str, EventSpec] = {}


def register(*specs: EventSpec) -> None:
    """Зарегистрировать типы событий.

    Повторная регистрация того же типа — ошибка: молча перетёртый тип
    искали бы долго.
    """
    for spec in specs:
        if spec.type in _REGISTRY and _REGISTRY[spec.type] != spec:
            msg = f"Тип события {spec.type!r} уже зарегистрирован"
            raise ValueError(msg)
        _REGISTRY[spec.type] = spec


def get(event_type: str) -> EventSpec | None:
    """Спецификация типа или ``None``, если тип неизвестен."""
    return _REGISTRY.get(str(event_type))


def all_specs() -> list[EventSpec]:
    """Все зарегистрированные типы, отсортированные по идентификатору."""
    return sorted(_REGISTRY.values(), key=lambda spec: spec.type)


def fallback_spec(event_type: str) -> EventSpec:
    """Спецификация для незарегистрированного типа.

    Терять событие из-за забытой регистрации хуже, чем показать его
    сырым идентификатором.
    """
    logger.warning("events.unknown_type", type=event_type)
    return EventSpec(
        type=event_type,
        title=event_type,
        template=event_type,
        source=EventSource.SYSTEM,
    )


CORE_EVENTS = (
    # --- жизненный цикл бота ---
    EventSpec(
        type=EventType.BOT_STARTED,
        title="Бот запущен",
        template="Бот {nick} запущен",
        source=EventSource.BOT,
    ),
    EventSpec(
        type=EventType.BOT_POLLING_FAILED,
        title="Опрос событий не удался",
        template="Опрос событий не удался (попытка {attempt})",
        source=EventSource.BOT,
        severity=EventSeverity.WARNING,
    ),
    # --- сообщения ---
    EventSpec(
        type=EventType.MESSAGE_SENT,
        title="Сообщение отправлено",
        template="Отправлено сообщение в чат {chat_id}",
        source=EventSource.BOT,
        # Поток сообщений в базе не нужен: он есть в логах, а таблицу
        # раздувает быстрее всего остального вместе взятого.
        persist=False,
        chat_scoped=True,
    ),
    EventSpec(
        type=EventType.MESSAGE_SEND_FAILED,
        title="Сообщение не отправлено",
        template="Сообщение в чат {chat_id} не отправлено: {reason}",
        source=EventSource.BOT,
        severity=EventSeverity.ERROR,
        chat_scoped=True,
    ),
    # --- чаты ---
    EventSpec(
        type=EventType.CHAT_REGISTERED,
        title="Чат добавлен",
        template="Чат {chat_id} записан в базу",
        source=EventSource.API,
        chat_scoped=True,
    ),
    EventSpec(
        type=EventType.CHAT_BOT_ADDED,
        title="Бота добавили в чат",
        template="Бота добавили в чат, участников: {members}",
        source=EventSource.API,
        chat_scoped=True,
    ),
    EventSpec(
        type=EventType.CHAT_BOT_REMOVED,
        title="Бота удалили из чата",
        template="Бота удалили из чата",
        source=EventSource.API,
        severity=EventSeverity.WARNING,
        chat_scoped=True,
    ),
    EventSpec(
        type=EventType.CHAT_MEMBER_JOINED,
        title="Участник вошёл",
        template="{members} вошли в чат",
        source=EventSource.API,
        chat_scoped=True,
    ),
    EventSpec(
        type=EventType.CHAT_MEMBER_LEFT,
        title="Участник вышел",
        template="{members} покинули чат",
        source=EventSource.API,
        chat_scoped=True,
    ),
    EventSpec(
        type=EventType.CHAT_INFO_CHANGED,
        title="Чат изменён",
        template="Название чата изменено на «{title}»",
        source=EventSource.API,
        chat_scoped=True,
    ),
    # --- обсуждения ---
    EventSpec(
        type=EventType.THREAD_AUTOSUBSCRIBE_CHANGED,
        title="Автоподписка на обсуждения",
        template="{actor} переключил автоподписку на обсуждения: {enabled}",
        source=EventSource.COMMAND,
        chat_scoped=True,
    ),
    # --- роли ---
    EventSpec(
        type=EventType.ROLE_CREATED,
        title="Роль создана",
        template="{actor} создал роль {role}",
        source=EventSource.PANEL,
    ),
    EventSpec(
        type=EventType.ROLE_UPDATED,
        title="Роль изменена",
        template="{actor} изменил роль {role}",
        source=EventSource.PANEL,
    ),
    EventSpec(
        type=EventType.ROLE_DELETED,
        title="Роль удалена",
        template="{actor} удалил роль {role}",
        source=EventSource.PANEL,
    ),
    EventSpec(
        type=EventType.ROLE_ASSIGNED,
        title="Роль назначена",
        template="{actor} назначил роль {role} участнику {target}",
        source=EventSource.PANEL,
        chat_scoped=True,
    ),
    EventSpec(
        type=EventType.ROLE_UNASSIGNED,
        title="Роль снята",
        template="{actor} снял роль {role} с участника {target}",
        source=EventSource.PANEL,
        chat_scoped=True,
    ),
    EventSpec(
        type=EventType.ROLE_MENTIONED,
        title="Призыв по роли",
        template="{actor} призвал роль {role}: уведомлений — {notified}",
        source=EventSource.COMMAND,
        chat_scoped=True,
    ),
    # --- вебхуки ---
    EventSpec(
        type=EventType.WEBHOOK_CREATED,
        title="Вебхук создан",
        template="{actor} создал вебхук {name}",
        source=EventSource.PANEL,
        chat_scoped=True,
    ),
    EventSpec(
        type=EventType.WEBHOOK_UPDATED,
        title="Вебхук изменён",
        template="{actor} изменил вебхук {name}",
        source=EventSource.PANEL,
        chat_scoped=True,
    ),
    EventSpec(
        type=EventType.WEBHOOK_DELETED,
        title="Вебхук удалён",
        template="{actor} удалил вебхук {name}",
        source=EventSource.PANEL,
        chat_scoped=True,
    ),
    EventSpec(
        type=EventType.WEBHOOK_KEY_REGENERATED,
        title="Ключ вебхука обновлён",
        template="{actor} перевыпустил ключ вебхука {name}",
        source=EventSource.PANEL,
        severity=EventSeverity.WARNING,
        chat_scoped=True,
    ),
    EventSpec(
        type=EventType.WEBHOOK_CALLED,
        title="Вебхук вызван",
        template="Вебхук {name} доставил сообщение в чат",
        source=EventSource.WEBHOOK,
        chat_scoped=True,
    ),
    EventSpec(
        type=EventType.WEBHOOK_FAILED,
        title="Вебхук не доставил сообщение",
        template="Вебхук {name} не смог отправить сообщение: {reason}",
        source=EventSource.WEBHOOK,
        severity=EventSeverity.ERROR,
        chat_scoped=True,
    ),
    # --- вход в панель ---
    EventSpec(
        type=EventType.AUTH_LOGIN_REQUESTED,
        title="Запрошен вход",
        template="{actor} запросил ссылку для входа в панель",
        source=EventSource.COMMAND,
    ),
    EventSpec(
        type=EventType.AUTH_LOGIN_SUCCEEDED,
        title="Вход в панель",
        template="{actor} вошёл в панель",
        source=EventSource.PANEL,
    ),
    EventSpec(
        type=EventType.AUTH_LOGIN_FAILED,
        title="Неудачный вход",
        template="Неудачная попытка входа: {reason}",
        source=EventSource.PANEL,
        severity=EventSeverity.WARNING,
    ),
    EventSpec(
        type=EventType.AUTH_SUPERUSER_GRANTED,
        title="Выданы права администратора",
        template="{actor} получил права администратора",
        source=EventSource.SYSTEM,
        severity=EventSeverity.WARNING,
    ),
    # --- прочее ---
    EventSpec(
        type=EventType.CHAT_USER_UPDATED,
        title="Участник изменён",
        template="{actor} изменил участника {target}",
        source=EventSource.PANEL,
    ),
    EventSpec(
        type=EventType.SETTINGS_CHANGED,
        title="Настройка изменена",
        template="{actor} изменил настройку {key} на «{value}»",
        source=EventSource.PANEL,
    ),
)

register(*CORE_EVENTS)
