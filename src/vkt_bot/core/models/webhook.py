from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import orm

from vkt_bot.db.base import Model

if TYPE_CHECKING:
    from .chat import Chat
    from .user import ChatUser


class Webhook(Model):
    """Вебхук для отправки сообщений в чат."""

    __tablename__ = "webhooks"

    id: orm.Mapped[str] = orm.mapped_column(
        primary_key=True, default=lambda: str(uuid.uuid4())
    )
    name: orm.Mapped[str] = orm.mapped_column(index=True)
    chat_id: orm.Mapped[str] = orm.mapped_column(
        sa.ForeignKey("chats.id", ondelete="CASCADE"), index=True
    )
    api_key_hash: orm.Mapped[str] = orm.mapped_column(
        sa.String(255), unique=True, index=True
    )
    created_by: orm.Mapped[str] = orm.mapped_column(
        sa.ForeignKey("chat_users.id", ondelete="CASCADE"), index=True
    )
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now()
    )
    updated_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now(), onupdate=sa.func.now()
    )
    is_active: orm.Mapped[bool] = orm.mapped_column(
        default=True, server_default=sa.sql.true()
    )
    webhook_metadata: orm.Mapped[dict] = orm.mapped_column(
        sa.JSON, default=dict, server_default="{}"
    )

    chat: orm.Mapped[Chat] = orm.relationship()
    creator: orm.Mapped[ChatUser] = orm.relationship()
