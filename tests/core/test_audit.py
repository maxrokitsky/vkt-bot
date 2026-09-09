"""``vkt_bot.core.audit.AuditLogger``."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest
import sqlalchemy as sa

from vkt_bot.core.audit import AuditLogger
from vkt_bot.core.models.log_entry import ActionType, ActorType, EntityType, LogEntry

from tests.conftest import table_count

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncSession

    from vkt_bot.core.models import ChatUser


async def entries(session: AsyncSession) -> list[LogEntry]:
    """Все записи аудита."""
    return list((await session.scalars(sa.select(LogEntry))).all())


@pytest.fixture
def audit(session: AsyncSession) -> AuditLogger:
    """Логгер аудита."""
    return AuditLogger(session)


class TestLog:
    """``log``."""

    async def test_writes_entry(
        self, audit: AuditLogger, session: AsyncSession
    ) -> None:
        await audit.log(
            action_type=ActionType.CREATE,
            entity_type=EntityType.ROLE,
            entity_id="role-1",
        )
        await session.commit()

        (entry,) = await entries(session)
        assert entry.action_type is ActionType.CREATE
        assert entry.entity_type is EntityType.ROLE
        assert entry.entity_id == "role-1"

    async def test_default_actor_is_system(
        self, audit: AuditLogger, session: AsyncSession
    ) -> None:
        await audit.log(
            action_type=ActionType.CREATE,
            entity_type=EntityType.ROLE,
            entity_id="role-1",
        )
        await session.commit()

        (entry,) = await entries(session)
        assert entry.actor_type is ActorType.SYSTEM
        assert entry.actor_id is None

    async def test_does_not_commit_by_itself(
        self, audit: AuditLogger, session: AsyncSession
    ) -> None:
        await audit.log(
            action_type=ActionType.CREATE,
            entity_type=EntityType.ROLE,
            entity_id="role-1",
        )
        await session.rollback()

        assert await table_count(session, LogEntry) == 0

    async def test_details_and_description(
        self, audit: AuditLogger, session: AsyncSession
    ) -> None:
        await audit.log(
            action_type=ActionType.UPDATE,
            entity_type=EntityType.CHAT_USER,
            entity_id="u@example.com",
            description="Выдали админку",
            details={"field": "is_superuser", "new_value": True},
        )
        await session.commit()

        (entry,) = await entries(session)
        assert entry.description == "Выдали админку"
        assert entry.details == {"field": "is_superuser", "new_value": True}

    async def test_user_fills_both_id_columns(
        self, audit: AuditLogger, session: AsyncSession, user: ChatUser
    ) -> None:
        """Один и тот же ``user.id`` пишется и в web-, и в bot-колонку."""
        await audit.log(
            action_type=ActionType.CREATE,
            entity_type=EntityType.ROLE,
            entity_id="role-1",
            user=user,
        )
        await session.commit()

        (entry,) = await entries(session)
        assert entry.web_user_username == user.id
        assert entry.bot_user_id == user.id

    async def test_actor_type_is_not_derived_from_user(
        self, audit: AuditLogger, session: AsyncSession, user: ChatUser
    ) -> None:
        """``log`` не меняет ``actor_type`` сам — это делают обёртки."""
        await audit.log(
            action_type=ActionType.CREATE,
            entity_type=EntityType.ROLE,
            entity_id="role-1",
            user=user,
        )
        await session.commit()

        (entry,) = await entries(session)
        assert entry.actor_type is ActorType.SYSTEM


WRAPPERS = [
    ("log_create", ActionType.CREATE, "Created"),
    ("log_update", ActionType.UPDATE, "Updated"),
    ("log_delete", ActionType.DELETE, "Deleted"),
    ("log_assign", ActionType.ASSIGN, "Assigned"),
    ("log_unassign", ActionType.UNASSIGN, "Unassigned"),
]


class TestWrappers:
    """``log_create`` и остальные обёртки."""

    @pytest.mark.parametrize(("method", "action", "prefix"), WRAPPERS)
    async def test_action_type(
        self,
        method: str,
        action: ActionType,
        prefix: str,
        audit: AuditLogger,
        session: AsyncSession,
    ) -> None:
        await getattr(audit, method)(entity_type=EntityType.ROLE, entity_id="role-1")
        await session.commit()

        (entry,) = await entries(session)
        assert entry.action_type is action

    @pytest.mark.parametrize(("method", "action", "prefix"), WRAPPERS)
    async def test_default_description(
        self,
        method: str,
        action: ActionType,
        prefix: str,
        audit: AuditLogger,
        session: AsyncSession,
    ) -> None:
        await getattr(audit, method)(entity_type=EntityType.ROLE, entity_id="role-1")
        await session.commit()

        (entry,) = await entries(session)
        assert entry.description == f"{prefix} role role-1"

    @pytest.mark.parametrize(("method", "action", "prefix"), WRAPPERS)
    async def test_custom_description(
        self,
        method: str,
        action: ActionType,
        prefix: str,
        audit: AuditLogger,
        session: AsyncSession,
    ) -> None:
        await getattr(audit, method)(
            entity_type=EntityType.ROLE, entity_id="role-1", description="Своё"
        )
        await session.commit()

        (entry,) = await entries(session)
        assert entry.description == "Своё"

    @pytest.mark.parametrize(("method", "action", "prefix"), WRAPPERS)
    async def test_without_user_actor_is_system(
        self,
        method: str,
        action: ActionType,
        prefix: str,
        audit: AuditLogger,
        session: AsyncSession,
    ) -> None:
        await getattr(audit, method)(entity_type=EntityType.ROLE, entity_id="role-1")
        await session.commit()

        (entry,) = await entries(session)
        assert entry.actor_type is ActorType.SYSTEM
        assert entry.actor_id is None

    @pytest.mark.parametrize(("method", "action", "prefix"), WRAPPERS)
    async def test_with_user_actor_is_web_user(
        self,
        method: str,
        action: ActionType,
        prefix: str,
        audit: AuditLogger,
        session: AsyncSession,
        user: ChatUser,
    ) -> None:
        await getattr(audit, method)(
            entity_type=EntityType.ROLE, entity_id="role-1", user=user
        )
        await session.commit()

        (entry,) = await entries(session)
        assert entry.actor_type is ActorType.WEB_USER
        assert entry.actor_id == user.id

    @pytest.mark.parametrize(("method", "action", "prefix"), WRAPPERS)
    async def test_web_user_kwarg_is_not_supported(
        self,
        method: str,
        action: ActionType,
        prefix: str,
        audit: AuditLogger,
        user: ChatUser,
    ) -> None:
        """Роутер ``roles.py`` зовёт обёртки с ``web_user=`` — такого имени нет."""
        with pytest.raises(TypeError, match="web_user"):
            await getattr(audit, method)(
                entity_type=EntityType.ROLE, entity_id="role-1", web_user=user
            )


class TestSeveralEntries:
    """Несколько записей в одной транзакции."""

    async def test_all_are_written(
        self, audit: AuditLogger, session: AsyncSession
    ) -> None:
        await audit.log_create(entity_type=EntityType.ROLE, entity_id="role-1")
        await audit.log_assign(entity_type=EntityType.ROLE_ASSIGNMENT, entity_id="ra-1")
        await session.commit()

        assert await table_count(session, LogEntry) == 2

    async def test_timestamps_are_filled(
        self, audit: AuditLogger, session: AsyncSession
    ) -> None:
        await audit.log_create(entity_type=EntityType.ROLE, entity_id="role-1")
        await session.commit()

        (entry,) = await entries(session)
        assert entry.timestamp is not None
