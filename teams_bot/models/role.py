from __future__ import annotations

import datetime
import uuid
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy import orm

from bot_framework.db.base import Model

if TYPE_CHECKING:
    from .user import User


class RoleAssignment(Model):
    """RoleAssignment."""

    __tablename__ = 'role_assignments'

    id: orm.Mapped[int] = orm.mapped_column(primary_key=True, index=True, autoincrement=True, unique=True)
    role_id: orm.Mapped[uuid.UUID] = orm.mapped_column(sa.ForeignKey("roles.id"))
    role: orm.Mapped[Role] = orm.relationship(back_populates="assignments")
    user_id: orm.Mapped[str] = orm.mapped_column(sa.ForeignKey("users.id"))
    user: orm.Mapped[User] = orm.relationship(back_populates="role_assignments")


class Role(Model):
    """Роль."""

    __tablename__ = 'roles'

    id: orm.Mapped[uuid.UUID] = orm.mapped_column(primary_key=True, index=True, default=uuid.uuid4, unique=True)
    name: orm.Mapped[str] = orm.mapped_column(index=True)
    created_at: orm.Mapped[datetime.datetime] = orm.mapped_column(server_default=sa.func.now())
    assignments: orm.Mapped[list[RoleAssignment]] = orm.relationship(back_populates="role")

    __table_args__ = (
        sa.Index("name_lower", sa.func.lower(name), unique=True),
    )

