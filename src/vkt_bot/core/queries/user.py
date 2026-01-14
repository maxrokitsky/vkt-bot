from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa

from vkt_bot.core.models.role import Role, RoleAssignment
from vkt_bot.core.models.user import ChatUser
from vkt_bot.db.query import Query

type Statement = sa.Select[Any]


class ChatUserQuery(Query): ...


class ChatUserHasRoleQuery(ChatUserQuery):
    roles: Iterable[str]

    def apply(self, statement: Statement) -> Statement:
        return (
            statement.join(ChatUser.role_assignments)
            .join(RoleAssignment.role)
            .where(sa.func.lower(Role.name).in_([role.lower() for role in self.roles]))
        )
