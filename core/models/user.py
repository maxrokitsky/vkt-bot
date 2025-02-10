
import datetime

import sqlalchemy as sa
from sqlalchemy import orm

from bot_framework.db.base import Model
from core.models.chat import ChatMembership

from .role import RoleAssignment


class User(Model):
    """Юзер."""

    __tablename__ = 'users'

    username: orm.Mapped[str] = orm.mapped_column(primary_key=True, index=True, unique=True)
    hashed_password: orm.Mapped[str]
    email: orm.Mapped[str] = orm.mapped_column(index=True)
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(server_default=sa.func.now())
    is_active: orm.Mapped[bool] = orm.mapped_column(default=True, server_default=sa.sql.true())
    is_superuser: orm.Mapped[bool] = orm.mapped_column(default=False, server_default=sa.sql.false())


class ChatUser(Model):
    """Пользователь."""

    __tablename__ = 'chat_users'

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True, index=True, unique=True)
    role_assignments: orm.Mapped[list[RoleAssignment]] = orm.relationship(back_populates='user')
    chat_memberships: orm.Mapped[list[ChatMembership]] = orm.relationship(back_populates='user')
