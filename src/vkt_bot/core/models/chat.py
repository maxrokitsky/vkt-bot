from __future__ import annotations

import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import orm

from vkteams_client.enums import ChatType
from vkt_bot.db.base import AutoincrementMixin, Model

if TYPE_CHECKING:
    from .user import ChatUser


class Chat(Model):
    """Chat."""

    __tablename__ = "chats"

    id: orm.Mapped[str] = orm.mapped_column(primary_key=True, index=True, unique=True)
    type: orm.Mapped[ChatType] = orm.mapped_column(sa.Enum(ChatType, native_enum=False))
    title: orm.Mapped[str | None] = orm.mapped_column(default=None)
    about: orm.Mapped[str | None] = orm.mapped_column(sa.Text, default=None)
    rules: orm.Mapped[str | None] = orm.mapped_column(sa.Text, default=None)
    #: Ссылка-приглашение: по ней заходят в чат без спроса. Поэтому её
    #: не пишут ни в журнал событий, ни в логи, а наружу отдают только
    #: участникам самого чата и администраторам (``GET /api/chats/{id}``;
    #: в списке чатов её нет вовсе).
    invite_link: orm.Mapped[str | None] = orm.mapped_column(default=None)
    #: Флаги приходят только из ``chats/getInfo``. ``None`` — не
    #: спрашивали: «закрытый» и «неизвестно» тут разное.
    public: orm.Mapped[bool | None] = orm.mapped_column(default=None)
    join_moderation: orm.Mapped[bool | None] = orm.mapped_column(default=None)
    #: Когда последний раз спрашивали ``chats/getInfo``. Метка ставится и
    #: на отказ: обсуждение от группы по ``chatId`` не отличить, и без
    #: неё тред опрашивался бы на каждом сообщении.
    info_updated_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(
        default=None
    )
    memberships: orm.Mapped[list[ChatMembership]] = orm.relationship(
        back_populates="chat"
    )


class ChatMembership(AutoincrementMixin, Model):
    """ChatMembership."""

    __tablename__ = "chat_memberships"

    chat_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("chats.id"))
    chat: orm.Mapped[Chat] = orm.relationship(back_populates="memberships")
    user_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("chat_users.id"))
    user: orm.Mapped[ChatUser] = orm.relationship(back_populates="chat_memberships")
