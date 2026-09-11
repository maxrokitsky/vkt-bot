"""Инструменты про роли."""

from __future__ import annotations

import sqlalchemy as sa
from pydantic_ai import RunContext

from vkt_agent import AgentDeps
from vkt_bot.core.models.role import Role, RoleAssignment
from vkt_bot.core.models.user import ChatUser

from . import registry

LIMIT = 50


@registry.tool
async def user_roles(ctx: RunContext[AgentDeps], user_id: str = "") -> str:
    """Роли участника.

    Роли глобальные: они не привязаны к чату, поэтому носитель роли может
    не состоять в том чате, где о нём спрашивают.

    Args:
        user_id: идентификатор участника; пусто — роли самого спрашивающего.
    """
    deps = ctx.deps
    target = user_id.strip() or deps.actor.user_id
    stmt = (
        sa.select(Role.name)
        .join(RoleAssignment, RoleAssignment.role_id == Role.id)
        .where(RoleAssignment.user_id == target)
        .order_by(Role.name)
    )
    names = list((await deps.session.scalars(stmt)).all())
    if not names:
        return f"У участника {target} ролей нет."
    return f"Роли участника {target}: " + ", ".join(names)


@registry.tool
async def role_members(ctx: RunContext[AgentDeps], role: str) -> str:
    """Кто носит роль.

    Args:
        role: название роли, без решётки.
    """
    deps = ctx.deps
    name = role.strip().lstrip("#")
    stmt = (
        sa.select(ChatUser)
        .join(RoleAssignment, RoleAssignment.user_id == ChatUser.id)
        .join(Role, Role.id == RoleAssignment.role_id)
        .where(sa.func.lower(Role.name) == name.lower())
        .limit(LIMIT)
    )
    rows = (await deps.session.scalars(stmt)).all()
    if not rows:
        return f"Роль «{name}» никому не назначена или не существует."
    people = ", ".join(f"{user.display_name} (id: {user.id})" for user in rows)
    return f"Роль «{name}»: {people}"
