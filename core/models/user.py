
from sqlalchemy import orm

from bot_framework.db.base import Model
from core.models.chat import ChatMembership

from .role import RoleAssignment


class ChatUser(Model):
    """Пользователь."""

    __tablename__ = 'chat_users'

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True, index=True, unique=True)
    role_assignments: orm.Mapped[list[RoleAssignment]] = orm.relationship(back_populates='user')
    chat_memberships: orm.Mapped[list[ChatMembership]] = orm.relationship(back_populates='user')
