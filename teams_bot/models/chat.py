from __future__ import annotations

from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import orm

from bot_framework.bot.enums import ChatType
from bot_framework.db.base import Model

if TYPE_CHECKING:
    from .user import User

class Chat(Model):
    """Chat."""

    __tablename__ = 'chats'

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True, index=True, unique=True)
    type: orm.Mapped[ChatType] = orm.mapped_column(sa.Enum(ChatType, native_enum=False))
    memberships: orm.Mapped[list[ChatMembership]] = orm.relationship(back_populates="chat")


class ChatMembership(Model):
    """ChatMembership."""

    __tablename__ = 'chat_memberships'

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True, unique=True, autoincrement=True)
    chat_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("chats.id"))
    chat: orm.Mapped[Chat] = orm.relationship(back_populates="memberships")
    user_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("users.id"))
    user: orm.Mapped[User] = orm.relationship(back_populates="chat_memberships")
