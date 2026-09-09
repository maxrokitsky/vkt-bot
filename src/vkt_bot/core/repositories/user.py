from typing import Any

import sqlalchemy as sa
from pydantic import BaseModel

from vkteams_client.types import Bot, User
from vkt_bot.core.models import ChatUser
from vkt_bot.core.models.role import Role, RoleAssignment
from vkt_bot.db.repository import AsyncRepository


class CreateChatUserSchema(BaseModel):
    """CreateChatUserSchema."""

    id: str
    is_bot: bool = False
    first_name: str | None = None
    last_name: str | None = None
    nick: str | None = None


class ChatUserRepository(AsyncRepository[ChatUser, str, CreateChatUserSchema, Any]):
    """ChatUser Repository."""

    async def get_or_create(self, user_id: str, *, is_bot: bool = False) -> ChatUser:
        """Получить пользователя или создать если не существует.

        ``is_bot`` проставляется, только когда мы точно знаем, что это бот:
        ложное значение не снимает уже выставленный флаг.
        """
        user = await self.get_or_none(user_id)
        if user:
            if is_bot and not user.is_bot:
                user.is_bot = True
                self.session.add(user)
            return user
        return await self.create(CreateChatUserSchema(id=user_id, is_bot=is_bot))

    async def sync_profile(self, member: User | Bot) -> ChatUser:
        """Создать пользователя по данным события и обновить его профиль."""
        user = await self.get_or_create(member.userId, is_bot=isinstance(member, Bot))
        self.apply_profile(user, member)
        return user

    async def update_profile(self, member: User | Bot) -> ChatUser | None:
        """Обновить профиль уже известного пользователя.

        Новых строк не создаёт: кто попадает в базу — решают хендлеры.
        """
        user = await self.get_or_none(member.userId)
        if user is not None:
            self.apply_profile(user, member)
        return user

    def apply_profile(self, user: ChatUser, member: User | Bot) -> None:
        """Перенести имя из события в модель.

        Пустые значения не затирают уже известные: в разных событиях
        приходит разный набор полей.
        """
        fields = {
            "first_name": member.firstName,
            "last_name": getattr(member, "lastName", None),
            "nick": getattr(member, "nick", None),
        }
        changed = False
        for field, value in fields.items():
            if value and getattr(user, field) != value:
                setattr(user, field, value)
                changed = True
        if isinstance(member, Bot) and not user.is_bot:
            user.is_bot = True
            changed = True
        if changed:
            self.session.add(user)

    async def grant_superuser(self, user: ChatUser) -> None:
        """Выдать пользователю права суперпользователя."""
        user.is_superuser = True
        self.session.add(user)

    async def list_by_roles(self, roles: list[str]) -> sa.ScalarResult[ChatUser]:
        """Получить список пользователей по ролям."""
        stmt = (
            sa.select(ChatUser)
            .join(ChatUser.role_assignments)
            .join(RoleAssignment.role)
            .where(sa.func.lower(Role.name).in_([role.lower() for role in roles]))
        )
        return await self.session.scalars(stmt)
