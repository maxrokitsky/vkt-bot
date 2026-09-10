from typing import Any

import sqlalchemy as sa
from pydantic import BaseModel

from vkteams_client.enums import ChatType
from vkteams_client.types import Chat as ChatPayload
from vkt_bot.db.repository import AsyncRepository
from vkt_bot.core.models import Chat, ChatMembership


class CreateChatSchema(BaseModel):
    """CreateChatSchema."""

    id: str
    type: ChatType
    title: str | None = None


class CreateChatMembershipSchema(BaseModel):
    """CreateChatMembershipSchema."""

    chat_id: str
    user_id: str


class ChatRepository(AsyncRepository[Chat, str, CreateChatSchema, Any]):
    """Chat Repository."""

    async def upsert(self, payload: ChatPayload, *, title: str | None = None) -> Chat:
        """Создать чат по событию или обновить его название.

        Название приходит не в каждом событии, поэтому пустое значение
        не затирает уже сохранённое.
        """
        new_title = title or payload.title
        chat = await self.get_or_none(payload.chatId)
        if chat is None:
            return await self.create(
                CreateChatSchema(id=payload.chatId, type=payload.type, title=new_title)
            )
        if new_title and chat.title != new_title:
            chat.title = new_title
            self.session.add(chat)
        return chat


class ChatMembershipRepository(
    AsyncRepository[ChatMembership, int, CreateChatMembershipSchema, Any]
):
    """ChatMembership Repository."""

    async def get_or_none_by_pair(
        self, chat_id: str, user_id: str
    ) -> ChatMembership | None:
        """Найти членство по паре чат—пользователь."""
        stmt = sa.select(ChatMembership).where(
            ChatMembership.chat_id == chat_id,
            ChatMembership.user_id == user_id,
        )
        return await self.session.scalar(stmt)

    async def user_ids(self, chat_id: str) -> set[str]:
        """Идентификаторы участников чата."""
        stmt = sa.select(ChatMembership.user_id).where(
            ChatMembership.chat_id == chat_id
        )
        return set((await self.session.scalars(stmt)).all())

    async def add(self, chat_id: str, user_id: str) -> ChatMembership | None:
        """Добавить участника. Повторный вызов ничего не меняет."""
        existing = await self.get_or_none_by_pair(chat_id, user_id)
        if existing:
            return None
        return await self.create(
            CreateChatMembershipSchema(chat_id=chat_id, user_id=user_id)
        )

    async def remove(self, chat_id: str, user_id: str) -> bool:
        """Снять членство. Возвращает True, если строка была."""
        stmt = sa.delete(ChatMembership).where(
            ChatMembership.chat_id == chat_id,
            ChatMembership.user_id == user_id,
        )
        result = await self.session.execute(stmt)
        return bool(result.rowcount)
