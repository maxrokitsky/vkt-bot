from collections.abc import Iterable
from typing import Any

from pydantic import EmailStr
import sqlalchemy as sa

from bot_framework.query import Query
from core.models.role import Role, RoleAssignment
from core.models.user import ChatUser, User

type Statement = sa.Select[Any]


class UserQuery(Query): ...


class UserByUsernameOrEmail(UserQuery):
    username: str
    email: EmailStr

    def apply(self, statement: Statement) -> Statement:
        return statement.where((User.email == self.email) | (User.username == self.username))


class ChatUserQuery(Query): ...


class ChatUserHasRoleQuery(ChatUserQuery):
    roles: Iterable[str]

    def apply(self, statement: Statement) -> Statement:
        return (
            statement.join(ChatUser.role_assignments)
            .join(RoleAssignment.role)
            .where(sa.func.lower(Role.name).in_([role.lower() for role in self.roles]))
        )
