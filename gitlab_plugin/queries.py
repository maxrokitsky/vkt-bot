from typing import Any
import uuid

import sqlalchemy as sa

from bot_framework.query import Query
from gitlab_plugin.models import GlWebhook

type Statement = sa.Select[Any]


class GlWebhookQuery(Query): ...


class GlWebhookById(GlWebhookQuery):
    id: str | uuid.UUID

    def apply(self, statement: Statement) -> Statement:
        return statement.where(GlWebhook.id == self.id)
