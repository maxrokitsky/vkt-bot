from typing import Any

import sqlalchemy as sa
from pydantic import BaseModel, EmailStr

from vkt_bot.bot_framework.repository import AsyncRepository
from vkt_bot.core.models import ChatUser
from vkt_bot.core.models.role import Role, RoleAssignment
from vkt_bot.core.models.user import User
from vkt_bot.core.queries.user import UserByUsernameOrEmail
from vkt_bot.core.security import verify_password


class CreateUserSchema(BaseModel):
    """CreateUserSchema."""

    username: str
    hashed_password: str
    email: EmailStr
    is_active: bool
    is_superuser: bool


class UpdateUserSchema(BaseModel):
    """UpdateUserSchema."""

    hashed_password: str
    email: EmailStr
    is_active: bool
    is_superuser: bool


class UserRepository(AsyncRepository[User, str, CreateUserSchema, UpdateUserSchema]):
    """User Repository."""

    async def authenticate(self, email_or_username: str, password: str) -> User | None:
        """Авторизует пользователя."""
        user = await self.query(
            UserByUsernameOrEmail(email=email_or_username, username=email_or_username)
        ).one_or_none()
        if not user:
            return None
        if not verify_password(password, user.hashed_password):
            return None
        return user


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
