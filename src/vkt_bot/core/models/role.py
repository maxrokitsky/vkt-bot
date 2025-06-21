from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import orm

from vkt_bot.bot_framework.db.base import AutoincrementMixin, Model, UUIDMixin

if TYPE_CHECKING:
    from .user import ChatUser


class RoleAssignment(AutoincrementMixin, Model):
    """RoleAssignment."""

    __tablename__ = "role_assignments"

    role_id: orm.Mapped[uuid.UUID] = orm.mapped_column(sa.ForeignKey("roles.id"))
    role: orm.Mapped[Role] = orm.relationship(back_populates="assignments")
    user_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("chat_users.id"))
    user: orm.Mapped[ChatUser] = orm.relationship(back_populates="role_assignments")


class Role(UUIDMixin, Model):
    """Роль."""

    __tablename__ = "roles"

    name: orm.Mapped[str] = orm.mapped_column(index=True)
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(
        server_default=sa.func.now()
    )
    assignments: orm.Mapped[list[RoleAssignment]] = orm.relationship(
        back_populates="role"
    )

    __table_args__ = (sa.Index("name_lower", sa.func.lower(name), unique=True),)
