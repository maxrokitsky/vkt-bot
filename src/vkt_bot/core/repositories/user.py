from typing import Any

import sqlalchemy as sa
from pydantic import BaseModel

from vkt_bot.core.models import ChatUser
from vkt_bot.core.models.role import Role, RoleAssignment
from vkt_bot.db.repository import AsyncRepository


class CreateChatUserSchema(BaseModel):
    """CreateChatUserSchema."""

    id: str


class ChatUserRepository(AsyncRepository[ChatUser, str, CreateChatUserSchema, Any]):
    """ChatUser Repository."""

    async def get_or_create(self, user_id: str) -> ChatUser:
        """Получить пользователя или создать если не существует."""
        user = await self.get_or_none(user_id)
        if user:
            return user
        return await self.create(CreateChatUserSchema(id=user_id))

    async def list_by_roles(self, roles: list[str]) -> sa.ScalarResult[ChatUser]:
        """Получить список пользователей по ролям."""
        stmt = (
            sa.select(ChatUser)
            .join(ChatUser.role_assignments)
            .join(RoleAssignment.role)
            .where(sa.func.lower(Role.name).in_([role.lower() for role in roles]))
        )
        return await self.session.scalars(stmt)
