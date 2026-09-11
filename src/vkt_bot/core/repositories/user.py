from collections.abc import Iterable
from typing import Any

import sqlalchemy as sa
from pydantic import BaseModel

from vkteams_client.types import Bot, PrivateChatInfo, User
from vkt_bot.core.models import ChatUser
from vkt_bot.core.models.role import Role, RoleAssignment
from vkt_bot.db.repository import AsyncRepository
from vkt_bot.utils.datetime import utcnow


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

    def apply_chat_info(self, user: ChatUser, info: PrivateChatInfo) -> None:
        """Перенести ответ ``chats/getInfo`` в профиль участника.

        Правило то же, что у ``apply_profile``: пустое не затирает
        известное. У аватара это единственно возможное поведение —
        ``photo`` приходит всегда, но картинки за ссылкой может и не
        быть, и «аватар сняли» от «аватара не было» мы не отличаем.
        Поэтому ссылку только ставим, но никогда не убираем.

        ``isBot`` у человека не приходит вовсе, поэтому флаг тоже только
        ставится. Зато бот, сидевший в чате до нашего, перестаёт
        числиться человеком, не дожидаясь, пока где-нибудь засветится.
        """
        fields = {
            "first_name": info.firstName,
            "last_name": info.lastName,
            "nick": info.nick,
            "about": info.about,
            "photo_url": info.photo_url,
        }
        for field, value in fields.items():
            if value and getattr(user, field) != value:
                setattr(user, field, value)
        if info.isBot and not user.is_bot:
            user.is_bot = True
        self.touch_info(user)

    def touch_info(self, user: ChatUser) -> None:
        """Отметить попытку обогащения, ничего больше не меняя.

        Нужно для отказов: без метки их повторяли бы без конца.
        """
        user.info_updated_at = utcnow()
        self.session.add(user)

    async def list_by_ids(self, user_ids: Iterable[str]) -> list[ChatUser]:
        """Участники по идентификаторам — одним запросом.

        Обогащение ростера идёт пачкой, и запрос на каждого из пятидесяти
        участников здесь ни к чему.
        """
        ids = list(user_ids)
        if not ids:
            return []
        stmt = sa.select(ChatUser).where(ChatUser.id.in_(ids))
        return list((await self.session.scalars(stmt)).all())

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
