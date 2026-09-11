"""История сообщений чатов.

Сообщения нигде больше не хранятся: у Bot API нет метода вроде
``messages/get``, поэтому единственный источник — то, что мы записали
сами. Задним числом историю не восстановить, и агент обязан говорить об
этом прямо, а не додумывать.
"""

from __future__ import annotations

import datetime

import sqlalchemy as sa
from sqlalchemy import orm

from vkt_bot.db.base import Model


class Message(Model):
    """Сообщение чата.

    Строка живёт независимо от чата и участника: у обсуждения свой
    ``chatId``, которого в ``chats`` нет, — та же причина, что у
    ``events.chat_id``.
    """

    __tablename__ = "messages"
    __table_args__ = (
        # Единственный горячий запрос: последние N сообщений чата.
        sa.Index("ix_messages_chat_id_ts", "chat_id", "ts"),
        # Повторная доставка события и правка не должны плодить строки.
        sa.UniqueConstraint("chat_id", "msg_id", name="uq_messages_chat_msg"),
    )

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, autoincrement=True)

    #: Чат или обсуждение. Без внешнего ключа: тред в ``chats`` не попадает.
    chat_id: orm.Mapped[str] = orm.mapped_column(index=True)
    msg_id: orm.Mapped[str] = orm.mapped_column(sa.String(64))

    #: Автор. У сообщений бота — идентификатор самого бота. Внешнего
    #: ключа нет намеренно, как у ``events.actor_id``: строки
    #: ``ChatUser`` заводит поток событий о составе чата, а не поток
    #: сообщений, и автор реплики в обсуждении может быть ещё неизвестен.
    user_id: orm.Mapped[str | None] = orm.mapped_column(index=True, default=None)

    #: Текста может не быть вовсе: файлы и стикеры приходят без него.
    text: orm.Mapped[str | None] = orm.mapped_column(sa.Text, default=None)

    ts: orm.Mapped[datetime.datetime] = orm.mapped_column(index=True)
    edited_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(default=None)
    #: Удалённое сообщение агенту не отдаётся никогда: человек его убрал,
    #: и всплывать через бота оно не должно.
    deleted_at: orm.Mapped[datetime.datetime | None] = orm.mapped_column(default=None)

    is_outgoing: orm.Mapped[bool] = orm.mapped_column(
        default=False, server_default=sa.sql.false()
    )

    def __repr__(self) -> str:
        return f"<Message {self.chat_id} {self.msg_id}>"
