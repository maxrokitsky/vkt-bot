import datetime
from sqlalchemy import orm
import sqlalchemy as sa
from bot_framework.db.base import Model, UUIDMixin
from core.models.chat import Chat
from core.models.user import ChatUser


class GlWebhook(UUIDMixin, Model):
    """GlWebhook."""

    __tablename__ = "gl_webhooks"

    name: orm.Mapped[str] = orm.mapped_column(default="", server_default="")
    hashed_secret: orm.Mapped[str]
    chat_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("chats.id"))
    chat: orm.Mapped[Chat] = orm.relationship()
    created_by_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("chat_users.id"))
    created_by: orm.Mapped[ChatUser] = orm.relationship()
    last_used_at: orm.Mapped[datetime.datetime | None]
