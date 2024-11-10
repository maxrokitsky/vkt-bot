
from sqlalchemy import orm

from bot_framework.db.base import Model
from teams_bot.models.chat import ChatMembership

from .role import RoleAssignment


class User(Model):
    """Пользователь."""

    __tablename__ = 'users'

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True, index=True, unique=True)
    role_assignments: orm.Mapped[list[RoleAssignment]] = orm.relationship(back_populates='user')
    chat_memberships: orm.Mapped[list[ChatMembership]] = orm.relationship(back_populates='user')
