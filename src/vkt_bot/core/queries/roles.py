from typing import Any
from uuid import UUID

import sqlalchemy as sa

from vkt_bot.db.query import Query
from vkt_bot.core.models.role import Role, RoleAssignment
from vkt_bot.core.models.user import ChatUser

type Statement = sa.Select[Any]


class RoleQuery(Query): ...


class RoleByIdQuery(RoleQuery):
    role_id: str | None = None

    def apply(self, statement: Statement) -> Statement:
        if self.role_id:
            statement = statement.where(Role.id == self.role_id)
        return statement


class RoleByUserQuery(RoleQuery):
    user_id: str | None = None

    def apply(self, statement: Statement) -> Statement:
        if self.user_id:
            statement = (
                statement.join(Role.assignments)
                .join(RoleAssignment.user)
                .where(ChatUser.id == self.user_id)
            )
        return statement


class RoleAssignmentQuery(Query): ...


class RoleAssignmentByUserAndRoleQuery(RoleAssignmentQuery):
    user_id: str | None = None
    role_id: UUID | None = None

    def apply(self, statement: Statement) -> Statement:
        if self.user_id:
            statement = statement.where(RoleAssignment.user_id == self.user_id)
        if self.role_id:
            statement = statement.where(RoleAssignment.role_id == self.role_id)
        return statement
