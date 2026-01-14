from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import orm

from vkt_bot.db.base import AutoincrementMixin, Model

if TYPE_CHECKING:
    from .user import ChatUser


class LoginHistory(AutoincrementMixin, Model):
    """История входов пользователей."""

    __tablename__ = "login_history"

    user_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("chat_users.id"))
    user: orm.Mapped[ChatUser] = orm.relationship()
    ip_address: orm.Mapped[str | None]
    user_agent: orm.Mapped[str | None]
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now()
    )
