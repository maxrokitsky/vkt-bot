from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa

from bot_framework.query import Query
from teams_bot.models.role import Role, RoleAssignment
from teams_bot.models.user import User

type Statement = sa.Select[Any]


class UserQuery(Query): ...


class UserHasRoleQuery(UserQuery):
    roles: Iterable[str]

    def apply(self, statement: Statement) -> Statement:
        return (
            statement.join(User.role_assignments)
            .join(RoleAssignment.role)
            .where(sa.func.lower(Role.name).in_([role.lower() for role in self.roles]))
        )
