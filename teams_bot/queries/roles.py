from typing import Any
from uuid import UUID
from bot_framework.query import Query
import sqlalchemy as sa

from teams_bot.models.role import Role, RoleAssignment
from teams_bot.models.user import ChatUser


type Statement = sa.Select[Any]


class RoleQuery(Query): ...


class RoleUserQuery(RoleQuery):
    user_id: str | None = None

    def apply(self, statement: Statement) -> Statement:
        if self.user_id:
            statement = statement.join(Role.assignments).join(RoleAssignment.user).where(ChatUser.id == self.user_id)
        return statement


class RoleAssignmentQuery(Query): ...


class RoleAssignmentUserAndRoleQuery(RoleAssignmentQuery):
    user_id: str | None = None
    role_id: UUID | None = None

    def apply(self, statement: Statement) -> Statement:
        if self.user_id:
            statement = statement.where(RoleAssignment.user_id == self.user_id)
        if self.role_id:
            statement = statement.where(RoleAssignment.role_id == self.role_id)
        return statement
