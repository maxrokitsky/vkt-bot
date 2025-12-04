"""Утилиты для аудита действий."""

from sqlalchemy.ext.asyncio import AsyncSession

from vkt_bot.core.models.log_entry import ActionType, ActorType, EntityType
from vkt_bot.core.models.user import User, ChatUser
from vkt_bot.core.repositories.log_entry import (
    CreateLogEntrySchema,
    LogEntryRepository,
)


class AuditLogger:
    """Класс для логирования действий в системе."""

    def __init__(self, session: AsyncSession):
        self.session = session
        self.repository = LogEntryRepository(session)

    async def log(
        self,
        action_type: ActionType,
        entity_type: EntityType,
        entity_id: str,
        *,
        actor_type: ActorType = ActorType.SYSTEM,
        actor_id: str | None = None,
        web_user: User | None = None,
        bot_user: ChatUser | None = None,
        description: str | None = None,
        details: dict | None = None,
    ) -> None:
        """
        Логирование действия.

        Args:
            action_type: Тип действия (create, update, delete, assign, unassign)
            entity_type: Тип сущности
            entity_id: ID сущности
            actor_type: Тип актора
            actor_id: ID актора
            web_user: Пользователь панели управления (если применимо)
            bot_user: Пользователь бота (если применимо)
            description: Человекочитаемое описание
            details: Дополнительные детали в формате dict
        """
        schema = CreateLogEntrySchema(
            actor_type=actor_type,
            actor_id=actor_id,
            action_type=action_type,
            entity_type=entity_type,
            entity_id=entity_id,
            description=description,
            details=details,
            web_user_username=web_user.username if web_user else None,
            bot_user_id=bot_user.id if bot_user else None,
        )
        await self.repository.create(schema, commit=False)

    async def log_create(
        self,
        entity_type: EntityType,
        entity_id: str,
        *,
        web_user: User | None = None,
        bot_user: ChatUser | None = None,
        description: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Логирование создания сущности."""
        actor_type = ActorType.WEB_USER if web_user else ActorType.BOT_USER if bot_user else ActorType.SYSTEM
        actor_id = web_user.username if web_user else bot_user.id if bot_user else None

        await self.log(
            action_type=ActionType.CREATE,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            web_user=web_user,
            bot_user=bot_user,
            description=description or f"Created {entity_type.value} {entity_id}",
            details=details,
        )

    async def log_update(
        self,
        entity_type: EntityType,
        entity_id: str,
        *,
        web_user: User | None = None,
        bot_user: ChatUser | None = None,
        description: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Логирование обновления сущности."""
        actor_type = ActorType.WEB_USER if web_user else ActorType.BOT_USER if bot_user else ActorType.SYSTEM
        actor_id = web_user.username if web_user else bot_user.id if bot_user else None

        await self.log(
            action_type=ActionType.UPDATE,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            web_user=web_user,
            bot_user=bot_user,
            description=description or f"Updated {entity_type.value} {entity_id}",
            details=details,
        )

    async def log_delete(
        self,
        entity_type: EntityType,
        entity_id: str,
        *,
        web_user: User | None = None,
        bot_user: ChatUser | None = None,
        description: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Логирование удаления сущности."""
        actor_type = ActorType.WEB_USER if web_user else ActorType.BOT_USER if bot_user else ActorType.SYSTEM
        actor_id = web_user.username if web_user else bot_user.id if bot_user else None

        await self.log(
            action_type=ActionType.DELETE,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            web_user=web_user,
            bot_user=bot_user,
            description=description or f"Deleted {entity_type.value} {entity_id}",
            details=details,
        )

    async def log_assign(
        self,
        entity_type: EntityType,
        entity_id: str,
        *,
        web_user: User | None = None,
        bot_user: ChatUser | None = None,
        description: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Логирование назначения (например, роли)."""
        actor_type = ActorType.WEB_USER if web_user else ActorType.BOT_USER if bot_user else ActorType.SYSTEM
        actor_id = web_user.username if web_user else bot_user.id if bot_user else None

        await self.log(
            action_type=ActionType.ASSIGN,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            web_user=web_user,
            bot_user=bot_user,
            description=description or f"Assigned {entity_type.value} {entity_id}",
            details=details,
        )

    async def log_unassign(
        self,
        entity_type: EntityType,
        entity_id: str,
        *,
        web_user: User | None = None,
        bot_user: ChatUser | None = None,
        description: str | None = None,
        details: dict | None = None,
    ) -> None:
        """Логирование отмены назначения (например, роли)."""
        actor_type = ActorType.WEB_USER if web_user else ActorType.BOT_USER if bot_user else ActorType.SYSTEM
        actor_id = web_user.username if web_user else bot_user.id if bot_user else None

        await self.log(
            action_type=ActionType.UNASSIGN,
            entity_type=entity_type,
            entity_id=entity_id,
            actor_type=actor_type,
            actor_id=actor_id,
            web_user=web_user,
            bot_user=bot_user,
            description=description or f"Unassigned {entity_type.value} {entity_id}",
            details=details,
        )
