import datetime
import enum

import sqlalchemy as sa
from sqlalchemy import orm

from vkt_bot.db.base import Model


class ActionType(str, enum.Enum):
    """Типы действий в системе."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    ASSIGN = "assign"
    UNASSIGN = "unassign"


class ActorType(str, enum.Enum):
    """Тип актора, совершившего действие."""

    WEB_USER = "web_user"  # Пользователь панели управления
    BOT_USER = "bot_user"  # Пользователь бота (ChatUser)
    SYSTEM = "system"  # Системное действие


class EntityType(str, enum.Enum):
    """Типы сущностей в системе."""

    USER = "user"
    CHAT_USER = "chat_user"
    ROLE = "role"
    CHAT = "chat"
    ROLE_ASSIGNMENT = "role_assignment"
    CHAT_MEMBERSHIP = "chat_membership"
    BOT_SETTINGS = "bot_settings"


class LogEntry(Model):
    """Запись аудита действий в системе."""

    __tablename__ = "log_entries"

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)
    timestamp: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now(), index=True
    )

    # Тип актора и его идентификатор
    actor_type: orm.Mapped[ActorType] = orm.mapped_column(index=True)
    actor_id: orm.Mapped[str | None] = orm.mapped_column(
        index=True
    )  # username для web_user, id для bot_user

    # Тип действия
    action_type: orm.Mapped[ActionType] = orm.mapped_column(index=True)

    # Сущность, над которой произведено действие
    entity_type: orm.Mapped[EntityType] = orm.mapped_column(index=True)
    entity_id: orm.Mapped[str]  # ID сущности

    # Дополнительная информация
    description: orm.Mapped[str | None]  # Человекочитаемое описание действия
    details: orm.Mapped[dict | None] = orm.mapped_column(
        type_=sa.JSON
    )  # Дополнительные детали (например, измененные поля)

    # Foreign keys для удобства (optional, но ускоряет поиск)
    web_user_username: orm.Mapped[str | None] = orm.mapped_column(
        sa.ForeignKey("users.username", ondelete="SET NULL"), index=True
    )
    bot_user_id: orm.Mapped[str | None] = orm.mapped_column(
        sa.ForeignKey("chat_users.id", ondelete="SET NULL"), index=True
    )

    # Relationships
    web_user: orm.Mapped["User | None"] = orm.relationship(
        "User", foreign_keys=[web_user_username]
    )
    bot_user: orm.Mapped["ChatUser | None"] = orm.relationship(
        "ChatUser", foreign_keys=[bot_user_id]
    )
