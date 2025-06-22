from typing import Any
from uuid import UUID

import sqlalchemy as sa
from pydantic import BaseModel

from vkt_bot.db.repository import AsyncRepository, NotFoundError
from vkt_bot.core.models import Role
from vkt_bot.core.models.role import RoleAssignment


class CreateRoleSchema(BaseModel):
    """CreateRoleSchema."""

    name: str


class RoleRepository(AsyncRepository[Role, UUID, CreateRoleSchema, Any]):
    """Role Repository."""

    async def get_by_name(self, name: str) -> Role:
        """Get Role by name."""
        if obj := await self.session.scalar(
            sa.select(Role).where(sa.func.lower(Role.name) == name.lower())
        ):
            return obj
        raise NotFoundError


class CreateRoleAssignmentSchema(BaseModel):
    """CreateRoleSchema."""

    role_id: UUID
    user_id: str


class RoleAssignmentRepository(
    AsyncRepository[RoleAssignment, int, CreateRoleAssignmentSchema, Any]
):
    """RoleAssignment Repository."""
