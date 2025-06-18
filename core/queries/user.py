from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa

from bot_framework.query import Query
from core.models.role import Role, RoleAssignment
from core.models.user import ChatUser, User

type Statement = sa.Select[Any]


class UserQuery(Query): ...


class UserByUsernameOrEmail(UserQuery):
    username: str | None = None
    email: str | None = None

    def apply(self, statement: Statement) -> Statement:
        if self.username and self.email:
            return statement.where(
                (sa.func.lower(User.email) == self.email.lower())
                | (sa.func.lower(User.username) == self.username.lower())
            )
        if self.email:
            return statement.where(sa.func.lower(User.email) == self.email.lower())
        if self.username:
            return statement.where(
                sa.func.lower(User.username) == self.username.lower()
            )
        raise Exception


class ChatUserQuery(Query): ...


class ChatUserHasRoleQuery(ChatUserQuery):
    roles: Iterable[str]

    def apply(self, statement: Statement) -> Statement:
        return (
            statement.join(ChatUser.role_assignments)
            .join(RoleAssignment.role)
            .where(sa.func.lower(Role.name).in_([role.lower() for role in self.roles]))
        )
