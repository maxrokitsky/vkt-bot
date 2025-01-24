from typing import Any

import sqlalchemy as sa
from pydantic import BaseModel, EmailStr

from bot_framework.repository import AsyncRepository
from core.models import ChatUser
from core.models.role import Role, RoleAssignment
from core.models.user import User


class CreateUserSchema(BaseModel):
    """CreateUserSchema."""

    username: str
    hashed_password: str
    email: EmailStr


class UserRepository(AsyncRepository[User, str, CreateUserSchema, Any]):
    """User Repository."""


class CreateChatUserSchema(BaseModel):
    """CreateChatUserSchema."""

    id: str


class ChatUserRepository(AsyncRepository[ChatUser, str, CreateChatUserSchema, Any]):
    """Chat User Repository."""

    async def list_by_roles(self, roles: list[str]) -> sa.ScalarResult[ChatUser]:
        """Получить список пользователей по ролям."""
        stmt = (
            sa.select(ChatUser)
            .join(ChatUser.role_assignments)
            .join(RoleAssignment.role)
            .where(sa.func.lower(Role.name).in_([role.lower() for role in roles]))
        )
        return await self.session.scalars(stmt)
