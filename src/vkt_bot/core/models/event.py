"""Журнал доменных событий.

Это не логи приложения (те живут в stdout и Loki, см. `docs/logging.md`),
а то, что показывается в панели: кто что сделал, когда и в каком чате.
Общий у них только `trace_id` — по нему запись в панели связывается со
строками лога.
"""

import datetime
import enum

import sqlalchemy as sa
from sqlalchemy import orm

from vkt_bot.db.base import Model


class EventSource(enum.StrEnum):
    """Откуда пришло действие.

    Актор не отвечает на этот вопрос: один и тот же человек назначает роль
    и командой в чате, и кнопкой в панели.
    """

    PANEL = "panel"  # Панель управления
    COMMAND = "command"  # Команда боту в чате
    API = "api"  # Входящее событие из опроса VK Teams
    BOT = "bot"  # Действие самого бота
    WEBHOOK = "webhook"  # Входящий вызов вебхука
    PLUGIN = "plugin"  # Плагин
    SYSTEM = "system"  # Внутреннее действие без инициатора


class EventSeverity(enum.StrEnum):
    """Значимость события — ею подсвечивается строка в панели."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ActorType(enum.StrEnum):
    """Кто совершил действие."""

    USER = "user"  # Человек: панель или команда в чате
    BOT = "bot"  # Сам бот
    SYSTEM = "system"  # Внутренняя логика
    EXTERNAL = "external"  # Внешняя система: вебхук, GitLab


class EntityType(enum.StrEnum):
    """Словарь типов сущностей.

    В колонке лежит обычная строка: плагины заводят свои типы, не трогая
    миграции. Перечисление — только для удобства ядра.
    """

    USER = "user"
    CHAT_USER = "chat_user"
    ROLE = "role"
    CHAT = "chat"
    ROLE_ASSIGNMENT = "role_assignment"
    CHAT_MEMBERSHIP = "chat_membership"
    BOT_SETTINGS = "bot_settings"
    WEBHOOK = "webhook"
    MESSAGE = "message"
    THREAD = "thread"


def enum_column(enum_type: type[enum.Enum], length: int = 32) -> sa.Enum:
    """Перечисление как VARCHAR со значениями, а не именами.

    Нативный ENUM пришлось бы менять миграцией при каждом новом значении,
    а ``ALTER TYPE`` в PostgreSQL умеет далеко не всё. ``values_callable``
    заставляет писать ``panel``, а не ``PANEL``: по умолчанию SQLAlchemy
    хранит имя, и в базе оказалось бы не то, что отдаёт API и видно в
    Grafana.
    """
    return sa.Enum(
        enum_type,
        native_enum=False,
        length=length,
        values_callable=lambda members: [member.value for member in members],
    )


class EventRecord(Model):
    """Событие в системе.

    Класс называется не ``Event``, чтобы не путаться с событием VK Teams
    (``vkteams_client.types.Event``) — они встречаются в одних и тех же
    модулях.
    """

    __tablename__ = "events"
    __table_args__ = (
        # Запросы панели: лента чата, лента по типу, лента по актору.
        sa.Index("ix_events_chat_id_ts", "chat_id", "ts"),
        sa.Index("ix_events_type_ts", "type", "ts"),
        sa.Index("ix_events_actor_id_ts", "actor_id", "ts"),
    )

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)
    ts: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now(), index=True
    )

    #: Идентификатор вида ``role.assigned`` — см. ``core.events.registry``.
    type: orm.Mapped[str] = orm.mapped_column(sa.String(64), index=True)
    source: orm.Mapped[EventSource] = orm.mapped_column(
        enum_column(EventSource), index=True
    )
    severity: orm.Mapped[EventSeverity] = orm.mapped_column(
        enum_column(EventSeverity), default=EventSeverity.INFO
    )

    actor_type: orm.Mapped[ActorType] = orm.mapped_column(enum_column(ActorType))
    #: id ``ChatUser`` либо имя внешней системы. Внешнего ключа нет
    #: намеренно: у внешнего актора id в ``chat_users`` не существует.
    actor_id: orm.Mapped[str | None] = orm.mapped_column(index=True)

    #: Чат, к которому относится событие, — ключ к ленте на странице чата.
    #: Тоже без внешнего ключа: у обсуждения свой ``chatId``, которого в
    #: таблице ``chats`` нет.
    chat_id: orm.Mapped[str | None] = orm.mapped_column(index=True)

    entity_type: orm.Mapped[str | None] = orm.mapped_column(sa.String(64))
    entity_id: orm.Mapped[str | None]

    #: Готовая строка для панели: шаблон рендерится при записи, поэтому
    #: старые события переживают переименование типа.
    summary: orm.Mapped[str]
    payload: orm.Mapped[dict | None] = orm.mapped_column(type_=sa.JSON)

    #: Связь со строками лога в Grafana.
    trace_id: orm.Mapped[str | None] = orm.mapped_column(sa.String(64), index=True)

    def __repr__(self) -> str:
        return f"<EventRecord {self.id} {self.type}>"
