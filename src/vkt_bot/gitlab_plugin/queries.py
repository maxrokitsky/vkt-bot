from typing import Any
import uuid

import sqlalchemy as sa

from vkt_bot.bot_framework.query import Query
from vkt_bot.gitlab_plugin.models import GlWebhook

type Statement = sa.Select[Any]


class GlWebhookQuery(Query): ...


class GlWebhookById(GlWebhookQuery):
    id: str | uuid.UUID

    def apply(self, statement: Statement) -> Statement:
        return statement.where(GlWebhook.id == self.id)


class GlWebhookByChatId(GlWebhookQuery):
    chat_id: str
    
    def apply(self, statement: Statement) -> Statement:
        return statement.where(GlWebhook.chat_id == self.chat_id)
