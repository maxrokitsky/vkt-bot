from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import orm

from vkt_bot.db.base import AutoincrementMixin, Model

if TYPE_CHECKING:
    from .user import ChatUser


class LoginToken(AutoincrementMixin, Model):
    """Временный токен для входа в веб-панель."""

    __tablename__ = "login_tokens"

    token: orm.Mapped[str] = orm.mapped_column(index=True, unique=True)
    user_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("chat_users.id"))
    user: orm.Mapped[ChatUser] = orm.relationship()
    expires_at: orm.Mapped[datetime.datetime]
    used: orm.Mapped[bool] = orm.mapped_column(
        default=False, server_default=sa.sql.false()
    )
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now()
    )
