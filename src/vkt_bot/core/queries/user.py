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


class ChatUserSearchQuery(ChatUserQuery):
    """Поиск участника по имени, нику или id.

    Поля сравниваются по отдельности: склеивать имя и фамилию в SQL
    непортируемо, а пользы почти нет — по «Иван» и по «Иванов» находится и так.
    """

    search: str | None = None

    def apply(self, statement: Statement) -> Statement:
        if not self.search:
            return statement
        pattern = f"%{self.search.strip()}%"
        return statement.where(
            sa.or_(
                ChatUser.first_name.ilike(pattern),
                ChatUser.last_name.ilike(pattern),
                ChatUser.nick.ilike(pattern),
                ChatUser.id.ilike(pattern),
            )
        )
