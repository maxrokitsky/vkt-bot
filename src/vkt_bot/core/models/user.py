import datetime

import sqlalchemy as sa
from sqlalchemy import orm

from vkt_bot.db.base import Model

from .chat import ChatMembership
from .role import RoleAssignment


class ChatUser(Model):
    """Пользователь VK Teams."""

    __tablename__ = "chat_users"

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True, index=True, unique=True)
    is_superuser: orm.Mapped[bool] = orm.mapped_column(
        default=False, server_default=sa.sql.false()
    )
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now()
    )
    role_assignments: orm.Mapped[list[RoleAssignment]] = orm.relationship(
        back_populates="user"
    )
    chat_memberships: orm.Mapped[list[ChatMembership]] = orm.relationship(
        back_populates="user"
    )
