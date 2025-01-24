from typing import Any

import sqlalchemy as sa
from pydantic import BaseModel

from bot_framework.repository import AsyncRepository
from core.models import ChatUser
from core.models.role import Role, RoleAssignment


class CreateChatUserSchema(BaseModel):
    """CreateChatUserSchema."""

    id: str


class ChatUserRepository(AsyncRepository[ChatUser, str, CreateChatUserSchema, Any]):
    """User Repository."""

    async def list_by_roles(self, roles: list[str]) -> sa.ScalarResult[ChatUser]:
        """Получить список пользователей по ролям."""
        stmt = (
            sa.select(ChatUser)
            .join(ChatUser.role_assignments)
            .join(RoleAssignment.role)
            .where(sa.func.lower(Role.name).in_([role.lower() for role in roles]))
        )
        return await self.session.scalars(stmt)
