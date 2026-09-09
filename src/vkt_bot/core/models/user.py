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
    is_bot: orm.Mapped[bool] = orm.mapped_column(
        default=False, server_default=sa.sql.false()
    )
    first_name: orm.Mapped[str | None] = orm.mapped_column(default=None)
    last_name: orm.Mapped[str | None] = orm.mapped_column(default=None)
    nick: orm.Mapped[str | None] = orm.mapped_column(default=None)
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now()
    )
    role_assignments: orm.Mapped[list[RoleAssignment]] = orm.relationship(
        back_populates="user"
    )
    chat_memberships: orm.Mapped[list[ChatMembership]] = orm.relationship(
        back_populates="user"
    )

    @property
    def display_name(self) -> str:
        """Имя для показа. Пока имя неизвестно — остаётся ``id``."""
        full_name = " ".join(filter(None, (self.first_name, self.last_name)))
        return full_name or self.nick or self.id
