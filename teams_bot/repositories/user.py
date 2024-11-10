from typing import Any

from pydantic import BaseModel
import sqlalchemy as sa

from bot_framework.repository import AsyncRepository
from teams_bot.models import User
from teams_bot.models.role import Role, RoleAssignment



class CreateUserSchema(BaseModel):
    """CreateUserSchema."""

    id: str


class UserRepository(AsyncRepository[User, str, CreateUserSchema, Any]):
    """User Repository."""

    async def list_by_roles(self, roles: list[str]) -> sa.ScalarResult[User]:
        """Получить список пользователей по ролям."""
        stmt = (
            sa.select(User)
            .join(User.role_assignments)
            .join(RoleAssignment.role)
            .where(sa.func.lower(Role.name).in_([role.lower() for role in roles]))
        )
        return await self.session.scalars(stmt)
