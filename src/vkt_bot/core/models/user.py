import datetime

import sqlalchemy as sa
from sqlalchemy import orm

from vkt_bot.db.base import Model

from .chat import Chat, ChatMembership
from .role import Role, RoleAssignment


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
    about: orm.Mapped[str | None] = orm.mapped_column(sa.Text, default=None)
    #: Ссылка на аватар из ``chats/getInfo``. Открывается без
    #: авторизации, поэтому годится прямо в ``<img src>``; но картинки
    #: за ней может и не быть — проверить, не скачав, нельзя.
    photo_url: orm.Mapped[str | None] = orm.mapped_column(default=None)
    #: Когда последний раз спрашивали ``chats/getInfo``.
    info_updated_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(
        default=None
    )
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

    @property
    def roles(self) -> list[Role]:
        """Роли участника. Требует загруженных ``role_assignments``."""
        return [assignment.role for assignment in self.role_assignments]

    @property
    def chats(self) -> list[Chat]:
        """Чаты участника. Требует загруженных ``chat_memberships``."""
        return [membership.chat for membership in self.chat_memberships]
