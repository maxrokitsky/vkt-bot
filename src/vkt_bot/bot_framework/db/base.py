from __future__ import annotations
import uuid

from sqlalchemy.ext.asyncio import AsyncAttrs
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Model(AsyncAttrs, DeclarativeBase):
    """Base class for models."""


class AutoincrementMixin:
    id: Mapped[int] = mapped_column(
        primary_key=True, index=True, autoincrement=True, unique=True
    )


class UUIDMixin:
    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, index=True, default=uuid.uuid4, unique=True
    )


from vkt_bot.gitlab_plugin import models
from vkt_bot.core import models
