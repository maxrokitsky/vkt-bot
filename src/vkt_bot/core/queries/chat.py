from typing import Any

import sqlalchemy as sa

from vkt_bot.db.query import Query
from vkt_bot.core.models.chat import Chat

type Statement = sa.Select[Any]


class ChatQuery(Query): ...


class ChatByIdQuery(ChatQuery):
    chat_id: str | None = None

    def apply(self, statement: Statement) -> Statement:
        if self.chat_id:
            statement = statement.where(Chat.id == self.chat_id)
        return statement
